"""
The booking agent: "Book me tomorrow with a dermatologist at 5 PM".

Division of work (spec §14, §18; docs/agents.md):
- The model only UNDERSTANDS the request: it fills a BookingRequest
  (specialty, city, dates, time of day, preferred time, doctor name).
- The platform does everything else in plain code: validates and resolves
  the request (criteria_from_request), searches real bookable slots,
  filters and ranks them (find_options), and words the reply
  (options_message). The model never states times or availability, so
  it can't invent an appointment.
- Nothing is booked here. The patient taps an option to place the usual
  payment-step hold (POST /conversations/{id}/booking/reserve, only for
  options this agent offered), and the appointment is created only when
  they press "Pay & Confirm". Typing "yes, book it" can't book anything.

If nothing matches exactly, the search relaxes step by step (any time of
day → a wider date window → any city) and says so.
"""

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import BookingRequest
from app.core.config import get_settings
from app.models.clinic import Clinic, ClinicStaff
from app.models.doctor import Doctor
from app.models.enums import VerificationStatus
from app.models.scheduling import Availability
from app.services.availability_service import bookable_conditions

MAX_WINDOW_DAYS = 30
DEFAULT_WINDOW_DAYS = 14
MAX_OPTIONS = 3
_CANDIDATE_SLOTS = 300
# Local hours [start, end) for each part of the day.
TIME_OF_DAY_HOURS = {"morning": (6, 12), "afternoon": (12, 17), "evening": (17, 23)}
_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def clinic_zone() -> ZoneInfo:
    return ZoneInfo(get_settings().clinic_timezone)


def local_today(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(clinic_zone()).date()


@dataclass(frozen=True)
class BookingCriteria:
    specialty: str | None
    city: str | None
    day_from: date
    day_to: date  # inclusive
    time_of_day: str  # morning | afternoon | evening | any
    preferred_time: time | None
    doctor_name: str | None


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def criteria_from_request(
    request: BookingRequest, *, fallback_specialty: str | None, now: datetime | None = None
) -> BookingCriteria:
    """Validates the model's request: no past dates, at most MAX_WINDOW_DAYS, sane times."""
    today = local_today(now)
    requested_from = _parse_date(request.date_from)  # an unreadable date counts as none
    day_from = max(requested_from or today, today)
    day_to = _parse_date(request.date_to) or (
        day_from if requested_from else today + timedelta(days=DEFAULT_WINDOW_DAYS)
    )
    day_to = min(max(day_to, day_from), day_from + timedelta(days=MAX_WINDOW_DAYS))
    preferred = None
    if request.preferred_time and (match := _HHMM.match(request.preferred_time.strip())):
        preferred = time(int(match.group(1)), int(match.group(2)))
    time_of_day = request.time_of_day
    if time_of_day == "any" and preferred is not None:
        time_of_day = next((part for part, (start, end) in TIME_OF_DAY_HOURS.items() if start <= preferred.hour < end), "any")
    return BookingCriteria(
        specialty=request.specialty or fallback_specialty,
        city=(request.city or "").strip() or None,
        day_from=day_from,
        day_to=day_to,
        time_of_day=time_of_day,
        preferred_time=preferred,
        doctor_name=(request.doctor_name or "").strip() or None,
    )


async def _candidates(
    db: AsyncSession, criteria: BookingCriteria, patient_id: UUID | None, now: datetime
) -> list[tuple[Availability, Doctor, Clinic]]:
    zone = clinic_zone()
    window_start = datetime.combine(criteria.day_from, time.min, zone)
    window_end = datetime.combine(criteria.day_to + timedelta(days=1), time.min, zone)
    query = (
        select(Availability, Doctor, Clinic)
        .join(Doctor, Doctor.id == Availability.doctor_id)
        .join(Clinic, Clinic.id == Availability.clinic_id)
        .where(
            *bookable_conditions(now, patient_id),
            Availability.start_time >= window_start,
            Availability.start_time < window_end,
            Doctor.is_active.is_(True),
            Doctor.verification_status == VerificationStatus.VERIFIED,
            Clinic.is_active.is_(True),
        )
        .order_by(Availability.start_time)
        .limit(_CANDIDATE_SLOTS)
    )
    if criteria.specialty:
        query = query.where(Doctor.specialty.ilike(f"%{criteria.specialty}%"))
    if criteria.city:
        query = query.where(Clinic.city.ilike(f"%{criteria.city}%"))
    if criteria.doctor_name:
        # "Dr. Nada" / "د. ندى": match on the name without the title.
        name = re.sub(r"^(dr\.?|doctor|د\.?|دكتوره?)\s*", "", criteria.doctor_name, flags=re.IGNORECASE)
        query = query.where(Doctor.full_name.ilike(f"%{name}%"))
    rows = (await db.execute(query)).all()

    if criteria.time_of_day == "any":
        return list(rows)
    start_hour, end_hour = TIME_OF_DAY_HOURS[criteria.time_of_day]
    return [row for row in rows if start_hour <= row.Availability.start_time.astimezone(zone).hour < end_hour]


def _rank(rows: list, criteria: BookingCriteria) -> list:
    """Soonest first, or closest to the preferred time; one slot per doctor before any second slot."""
    zone = clinic_zone()

    def key(row) -> tuple:
        local = row.Availability.start_time.astimezone(zone)
        if criteria.preferred_time is None:
            return (local,)
        minutes = local.hour * 60 + local.minute
        target = criteria.preferred_time.hour * 60 + criteria.preferred_time.minute
        return (local.date(), abs(minutes - target), local)

    ordered = sorted(rows, key=key)
    seen: set[UUID] = set()
    first_per_doctor = [r for r in ordered if not (r.Doctor.id in seen or seen.add(r.Doctor.id))]
    rest = [r for r in ordered if r not in first_per_doctor]
    return (first_per_doctor + rest)[:MAX_OPTIONS]


# Relaxation ladder: what to loosen, in order, when nothing matches.
_RELAXATIONS = (
    ("time_of_day", lambda c: replace(c, time_of_day="any", preferred_time=None)),
    ("dates", lambda c: replace(c, day_to=max(c.day_to, c.day_from + timedelta(days=DEFAULT_WINDOW_DAYS)))),
    ("city", lambda c: replace(c, city=None)),
)


async def find_options(
    db: AsyncSession, criteria: BookingCriteria, *, patient_id: UUID | None, now: datetime | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Returns (options, what was relaxed to find them)."""
    now = now or datetime.now(timezone.utc)
    relaxed: list[str] = []
    current = criteria
    rows = await _candidates(db, current, patient_id, now)
    for name, loosen in _RELAXATIONS:
        if rows:
            break
        loosened = loosen(current)
        if loosened == current:
            continue
        current, rows = loosened, await _candidates(db, loosened, patient_id, now)
        relaxed.append(name)

    chosen = _rank(rows, current)
    fees = await _fees(db, {(row.Doctor.id, row.Clinic.id) for row in chosen})
    options = [
        {
            "availability_id": str(row.Availability.id),
            "start_time": row.Availability.start_time.isoformat(),
            "end_time": row.Availability.end_time.isoformat(),
            "doctor": {
                "id": str(row.Doctor.id), "full_name": row.Doctor.full_name, "specialty": row.Doctor.specialty,
                "rating": float(row.Doctor.rating) if row.Doctor.rating is not None else None,
            },
            "clinic": {"id": str(row.Clinic.id), "name": row.Clinic.name, "city": row.Clinic.city},
            # What the patient will pay for this consultation (null: the clinic confirms it).
            "consultation_fee": fees.get((row.Doctor.id, row.Clinic.id)),
        }
        for row in chosen
    ]
    return options, relaxed


async def _fees(db: AsyncSession, pairs: set[tuple[UUID, UUID]]) -> dict[tuple[UUID, UUID], float]:
    if not pairs:
        return {}
    rows = await db.execute(
        select(ClinicStaff.doctor_id, ClinicStaff.clinic_id, ClinicStaff.consultation_fee).where(
            ClinicStaff.doctor_id.in_({d for d, _ in pairs}),
            ClinicStaff.consultation_fee.is_not(None),
            ClinicStaff.is_active.is_(True),
        )
    )
    return {(d, c): float(fee) for d, c, fee in rows if (d, c) in pairs}


def criteria_payload(criteria: BookingCriteria) -> dict[str, Any]:
    return {
        "specialty": criteria.specialty, "city": criteria.city,
        "date_from": criteria.day_from.isoformat(), "date_to": criteria.day_to.isoformat(),
        "time_of_day": criteria.time_of_day,
        "preferred_time": criteria.preferred_time.strftime("%H:%M") if criteria.preferred_time else None,
        "doctor_name": criteria.doctor_name,
    }


# --- Reply text (written by the platform, not the model) ---------------------------------

_MESSAGES = {
    "en": {
        "found": "Here are the best matching times I found. Tap one to reserve it for {minutes} minutes; you'll confirm it on the next screen.",
        "relaxed": "I couldn't find a time matching exactly what you asked ({relaxed}), so here are the closest options. Tap one to reserve it for {minutes} minutes; you'll confirm it on the next screen.",
        "none": "I couldn't find any open appointments for that. You can try other dates, or browse doctors directly.",
        "relaxations": {"time_of_day": "time of day", "dates": "dates", "city": "city"},
    },
    "ar": {
        "found": "دي أنسب المواعيد اللي لقيتها. اختاري واحد عشان أحجزهولك لمدة {minutes} دقايق، وهتأكدي الحجز في الشاشة اللي بعدها.",
        "relaxed": "مالقيتش موعد مطابق بالظبط للي طلبتيه ({relaxed})، فدي أقرب الاختيارات. اختاري واحد عشان أحجزهولك لمدة {minutes} دقايق، وهتأكدي الحجز في الشاشة اللي بعدها.",
        "none": "مالقيتش مواعيد متاحة للطلب ده. ممكن تجربي تواريخ تانية، أو تتصفحي الأطباء مباشرة.",
        "relaxations": {"time_of_day": "الوقت", "dates": "التاريخ", "city": "المدينة"},
    },
}


def options_message(options: list[dict[str, Any]], relaxed: list[str], lang: str) -> str:
    text = _MESSAGES[lang]
    minutes = get_settings().slot_hold_minutes
    if not options:
        return text["none"]
    if relaxed:
        separator = "، " if lang == "ar" else ", "
        return text["relaxed"].format(relaxed=separator.join(text["relaxations"][r] for r in relaxed), minutes=minutes)
    return text["found"].format(minutes=minutes)


def offered_option(extra_data_list: list[dict[str, Any] | None], availability_id: UUID) -> dict[str, Any] | None:
    """The option with this slot among everything the agent offered in the conversation, if any."""
    for extra in extra_data_list:
        for option in ((extra or {}).get("booking") or {}).get("options", []):
            if option["availability_id"] == str(availability_id):
                return option
    return None


# --- Reserving an offered option -------------------------------------------------------------

_HOLD_MESSAGES = {
    "en": "Reserved for you: {doctor} at {clinic}, {when}. It's held for {minutes} minutes; confirm it on the payment screen.",
    "ar": "اتحجز ليكي مؤقتاً: {doctor} في {clinic}، {when}. محجوز لمدة {minutes} دقايق؛ أكّدي الحجز في شاشة الدفع.",
}


def hold_message(doctor_name: str, clinic_name: str, start: datetime, lang: str) -> str:
    local = start.astimezone(clinic_zone())
    when = local.strftime("%A %d %B, %I:%M %p").replace(" 0", " ") if lang == "en" else local.strftime("%d/%m الساعة %H:%M")
    return _HOLD_MESSAGES[lang].format(
        doctor=doctor_name, clinic=clinic_name, when=when, minutes=get_settings().slot_hold_minutes
    )
