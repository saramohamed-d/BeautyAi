"""
Deterministic, offline stand-in for the chat model ("demo mode").

Lets the whole consultation run locally and in tests without an API key
or cost. It plays the same role the real prompt asks for: pull details
out of the patient's latest message with keyword rules (English and
Egyptian Arabic), ask about the platform's `next_field`, and give a
templated preliminary assessment when the checklist is complete. The UI
labels its answers as demo answers. It is not an AI and must never run
in production (enforced in config).
"""

import re
from functools import lru_cache
from datetime import date, timedelta

from app.agents.schemas import (
    AssistantDraft,
    Assessment,
    BookingRequest,
    ChatTurn,
    Concern,
    ConsultationState,
    IntakeUpdate,
    Specialty,
    empty_intake,
)
from app.rag.types import Reference
from app.workflows.consultation import merge, missing_fields
from app.workflows.safety import is_arabic, normalize

_CONCERN_WORDS: dict[Concern, tuple[str, ...]] = {
    "acne": ("acne", "pimple", "breakout", "حب الشباب", "حبوب"),
    "pigmentation": ("pigment", "melasma", "dark patch", "dark patches", "brown patch", "brown patches", "كلف", "تصبغ"),
    "hair_loss": ("hair loss", "hair fall", "losing hair", "hair is falling", "hair has been falling",
                  "falling out", "shedding", "thinning", "تساقط", "شعري بيقع", "شعري بيخف", "صلع"),
    "anti_aging": ("wrinkle", "aging", "ageing", "fine lines", "sagging", "تجاعيد", "ترهل"),
    "redness": ("redness", "rosacea", "red face", "face gets red", "flushed", "flushing", "flush",
                "احمرار", "بيحمر", "ورديه"),
    "dark_spots": ("dark spot", "sun spot", "spots", "بقع", "نمش"),
}
# (English label, Arabic label) → words. Details are stored in the patient's language.
_AREA_WORDS = {
    # Eyes before face: "around my eyes" is more useful than "face".
    ("around the eyes", "حوالين العين"): ("eye", "eyes", "eyelid", "under eye", "عين", "العين", "عنيا", "جفن"),
    ("face", "الوش"): ("face", "cheek", "forehead", "chin", "nose", "lip", "jaw", "وش", "الوجه", "خد", "خدود", "جبهه", "دقن", "ذقن", "مناخير", "شفايف"),
    ("scalp", "فروة الراس"): ("scalp", "hairline", "crown", "فروه", "راسي", "الراس"),
    ("neck", "الرقبة"): ("neck", "رقبه"),
    ("back", "الضهر"): ("back", "ضهر", "ظهر"),
    ("chest", "الصدر"): ("chest", "صدر"),
    ("arms or hands", "الدراع أو الإيد"): ("arm", "hand", "دراع", "ايد"),
    ("legs", "الرجلين"): ("leg", "رجل"),
    ("body", "الجسم"): ("body", "جسم"),
}
_SYMPTOM_WORDS = {
    ("itching", "هرش"): ("itch", "هرش", "بيهرش", "بتهرش", "بياكل", "بتاكل", "حكه"),
    ("pain", "ألم"): ("pain", "hurt", "sore", "وجع", "بيوجع", "بتوجع", "الم"),
    ("bleeding", "نزيف"): ("bleed", "نزيف", "بتنزف", "بينزف"),
    ("spreading", "انتشار"): ("spread", "بينتشر", "بتنتشر", "بيزيد"),
    ("burning", "حرقان"): ("burning", "حرقان"),
    ("dryness or flaking", "جفاف أو قشر"): ("dry", "flak", "ناشف", "قشر"),
}
_SERIOUS = {"bleeding", "spreading", "pain", "نزيف", "انتشار", "ألم"}
# Not a bare "nothing": "I tried nothing" must not read as "no symptoms".
_NO_SYMPTOMS = ("no symptom", "no other symptom", "nothing else", "none", "no pain", "doesn't itch", "doesnt itch",
                "no itch", "مفيش", "ولا حاجه", "مش بيوجع", "مش بيهرش", "لا وجع", "مفيش اعراض")
_DURATION = re.compile(
    r"(\d+|a|an|one|two|three|few|several|couple of)\s*(day|week|month|year)s?"
    r"|since (last |early )?\w+"
    # Longer words first, so "شهرين" (two months) isn't cut to "شهر".
    r"|(\d+\s*)?(اسبوعين|اسابيع|اسبوع|ايام|يوم|شهرين|شهور|اشهر|شهر|سنتين|سنين|سنه)",
)
_SPECIALTY: dict[Concern, Specialty] = {
    "acne": "Dermatology", "pigmentation": "Dermatology", "hair_loss": "Dermatology",
    "anti_aging": "Aesthetic Medicine", "redness": "Dermatology", "dark_spots": "Dermatology", "other": "Dermatology",
}

_TEXT = {
    "en": {
        "concern": "Hi! I'm Beauty AI. What's the main skin, hair or beauty concern you'd like help with?",
        "body_area": "Where exactly is it, for example your face, scalp or body?",
        "duration": "How long have you had it?",
        "symptoms": "Does it itch, hurt, bleed or spread, or do you have no other symptoms?",
        "ack": "Thanks for telling me about {concern}. ",
        "assessment": (
            "From what you describe ({details}), this may be related to {concern}. This is a preliminary guide, "
            "not a diagnosis: {specialist} can confirm it in person."
        ),
        "offer": "Would you like me to find {specialist} with an available appointment?",
        "intro": "Thank you, that's everything I need. Here's your consultation summary.",
        "checking": "Let me check what's available.",
        "after": "I've shared your consultation summary. Would you like me to find a doctor, or do you have another question?",
        "library": "You can read more in our library: “{title}”.",
        "prepare": ["When it started and how it has changed", "Products and medicines you use", "Photos of how it looked at its worst"],
        "watch": ["Bleeding, fast spreading or severe pain", "Fever, warmth or pus"],
    },
    "ar": {
        "concern": "أهلاً! أنا BeautyAI. إيه المشكلة الأساسية في البشرة أو الشعر أو التجميل اللي حابة نتكلم فيها؟",
        "body_area": "فين بالظبط؟ مثلاً في الوش ولا فروة الراس ولا الجسم؟",
        "duration": "بقالها قد إيه؟",
        "symptoms": "بتهرش أو بتوجع أو بتنزف أو بتنتشر، ولا مفيش أعراض تانية؟",
        "ack": "شكراً إنك قولتيلي عن {concern}. ",
        "assessment": (
            "من كلامك ({details})، ممكن يكون الموضوع له علاقة بـ{concern}. ده توجيه مبدئي مش تشخيص، "
            "و{specialist} يقدر يأكد حضورياً."
        ),
        "offer": "تحبي أدورلك على {specialist} عنده موعد متاح؟",
        "intro": "شكراً ليكي، كده عندي كل اللي محتاجاه. ده ملخص استشارتك.",
        "checking": "ثانية أشوف المواعيد المتاحة.",
        "after": "شاركتك ملخص الاستشارة. تحبي أدورلك على دكتور، ولا عندك سؤال تاني؟",
        "library": "تقدري تقري أكتر في مكتبتنا: «{title}».",
        "prepare": ["إمتى بدأت وإزاي اتغيرت", "المنتجات والأدوية اللي بتستخدميها", "صور وقت ما كانت في أسوأ حالاتها"],
        "watch": ["نزيف أو انتشار سريع أو ألم شديد", "سخونية أو سخونة في المكان أو صديد"],
    },
}
_LABELS = {
    "en": {"acne": "acne", "pigmentation": "pigmentation", "hair_loss": "hair loss", "anti_aging": "signs of ageing",
           "redness": "redness", "dark_spots": "dark spots", "other": "your concern"},
    "ar": {"acne": "حب الشباب", "pigmentation": "التصبغات", "hair_loss": "تساقط الشعر", "anti_aging": "علامات التقدم في السن",
           "redness": "الاحمرار", "dark_spots": "البقع الداكنة", "other": "المشكلة"},
}
_SPECIALIST = {"en": {"Dermatology": "a dermatologist", "Aesthetic Medicine": "an aesthetic medicine doctor"},
               "ar": {"Dermatology": "دكتور جلدية", "Aesthetic Medicine": "دكتور طب تجميل"}}


_ARABIC_WORD = re.compile(r"[\u0621-\u064a]")
# What counts as a word edge. Arabic *punctuation* (؟ ، ؛) sits inside the
# Arabic Unicode block, so only letters and digits count as "inside a word";
# otherwise a word before "؟" would never end (Sprint 16 evaluation).
_EDGE = r"[^\w\u0621-\u064a\u0660-\u0669]"


def _word(word: str) -> re.Pattern[str]:
    """
    A keyword matcher that respects word edges, plurals and Arabic prefixes.

    Substring matching used to read "it**chin**g" as the body area "chin"
    (found by the Sprint 16 evaluation), but plain edges are too strict
    the other way: "cheeks" must still match "cheek", and "الذقن" must
    match "ذقن". Edges are checked against spaces and punctuation rather
    than `\b`, which doesn't behave well around Arabic letters.
    """
    escaped = re.escape(normalize(word))
    arabic = bool(_ARABIC_WORD.search(word))
    prefix = r"(?:ال|و|وال|ب|بال|ل|لل|ف|فال)?" if arabic else ""
    # Arabic attaches possessives and objects ("وشي" = my face, "احجزيلي" =
    # book me); English pluralises.
    suffix = r"(?:ي|ها|هم|هن|ك|كم|نا|يلي|لي|لنا|له|لها)?" if arabic else r"(?:s|es)?"
    return re.compile(rf"(?:^|{_EDGE}){prefix}{escaped}{suffix}(?:$|{_EDGE})")


@lru_cache(maxsize=2048)
def _matcher(word: str) -> re.Pattern[str]:
    return _word(word)


def _has(text: str, words: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(_matcher(word).search(padded) for word in words)


def extract(message: str) -> IntakeUpdate:
    """Keyword extraction from one patient message, recorded in the patient's language."""
    text = normalize(message)
    lang = 1 if is_arabic(message) else 0
    update = empty_intake().model_dump()
    concern = next((c for c, words in _CONCERN_WORDS.items() if _has(text, words)), None)
    if concern:
        update["concern"], update["concern_detail"] = concern, message.strip()[:80]
    area = next((labels[lang] for labels, words in _AREA_WORDS.items() if _has(text, words)), None)
    update["body_area"] = area or (("scalp", "فروة الراس")[lang] if concern == "hair_loss" else None)
    if duration := _DURATION.search(text):
        update["duration"] = duration.group(0)
    # "no pain or itching" is a denial, not a report of itching: the denial
    # is checked first (Sprint 16 evaluation).
    if _has(text, _NO_SYMPTOMS):
        update["symptoms"] = []
    elif symptoms := [labels[lang] for labels, words in _SYMPTOM_WORDS.items() if _has(text, words)]:
        update["symptoms"] = symptoms
    return IntakeUpdate.model_validate(update)


_BOOKING_WORDS = ("book", "appointment", "find me a doctor", "find me a slot", "available time", "slot",
                  "see a doctor", "see a dermatologist", "see a specialist", "visit a doctor",
                  "احجز", "حجز", "موعد", "ميعاد", "معاد", "دكتور متاح", "اشوف دكتور", "اروح لدكتور")
_YES = ("yes", "sure", "ok", "okay", "please do", "ايوه", "اه", "ماشي", "تمام", "ياريت", "يا ريت")
_TODAY = ("today", "النهارده", "انهارده", "اليوم")
_TOMORROW = ("tomorrow", "بكره", "بكرا")
_PARTS = {
    "morning": ("morning", "الصبح", "صباحا"),
    "afternoon": ("afternoon", "بعد الضهر", "العصر"),
    "evening": ("evening", "tonight", "night", "بالليل", "مساء", "بليل"),
}
_CITIES = {"Cairo": ("cairo", "القاهره"), "Giza": ("giza", "الجيزه"), "Alexandria": ("alexandria", "اسكندريه")}
_SPECIALTY_WORDS = {
    "Dermatology": ("dermatolog", "dermatologist", "dermatology", "skin doctor", "جلديه", "جلد"),
    "Aesthetic Medicine": ("aesthetic", "aesthetics", "cosmetic", "cosmetics", "تجميل"),
}
# "with Dr Amira", "مع د. أميرة": the name the patient asked for. The
# honorific must be its own word — "ميعاد الصبح" ends in "د" too.
_DOCTOR_NAME = re.compile(
    r"(?:^|[^\w])(?:dr\.?|doctor)\s+([a-z]+(?:\s+[a-z]+)?)"
    r"|(?:^|[^\u0621-\u064a])(?:د\.|دكتوره|دكتور)\s*([\u0621-\u064a]+(?:\s+[\u0621-\u064a]+)?)"
)
# Words that follow a name but aren't part of it.
_NOT_NAMES = {
    "please", "now", "today", "tomorrow", "available", "appointment", "who", "any",
    "لو", "سمحتي", "سمحت", "من", "في", "على", "عشان", "بكره", "النهارده", "الصبح", "بالليل",
    # A specialty is not a name: "دكتور جلديه" is "a dermatologist".
    "جلديه", "جلدية", "جلد", "تجميل", "dermatologist", "dermatology", "aesthetic", "cosmetic",
}


def _doctor_name(text: str) -> str | None:
    for match in _DOCTOR_NAME.finditer(text):
        name = (match.group(1) or match.group(2) or "").strip()
        words: list[str] = []
        for word in name.split():
            if word in _NOT_NAMES:
                break  # the name ended; the rest is politeness
            words.append(word)
        if words:
            return " ".join(words)
    return None


# A clock time only with "at", "الساعه" or am/pm, so "6 months" is never read as 6 o'clock.
_CLOCK = re.compile(r"(?:\bat\s+|الساعه\s*)(\d{1,2})(?::(\d{2}))?\s*(am|pm|ص|م)?|\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b")


def extract_booking(message: str, today_iso: str, offer_pending: bool) -> BookingRequest | None:
    """A booking request if the message asks for one (or says yes to the booking offer)."""
    text = normalize(message)
    asked = _has(text, _BOOKING_WORDS) or (offer_pending and any(re.search(rf"\b{w}\b", text) for w in map(normalize, _YES)))
    if not asked:
        return None
    today = date.fromisoformat(today_iso[:10]) if today_iso else date.today()
    day = today if _has(text, _TODAY) else today + timedelta(days=1) if _has(text, _TOMORROW) else None
    part = next((p for p, words in _PARTS.items() if _has(text, words)), "any")
    preferred = None
    if match := _CLOCK.search(text):
        hour = int(match.group(1) or match.group(4))
        minute = int(match.group(2) or match.group(5) or 0)
        suffix = match.group(3) or match.group(6)
        # Clinics don't open at 5 am: a bare 1-8 means afternoon/evening.
        if (suffix in ("pm", "م") or (suffix is None and 1 <= hour <= 8)) and hour < 12:
            hour += 12
        if hour < 24:
            preferred = f"{hour:02d}:{minute:02d}"
    return BookingRequest(
        specialty=next((s for s, words in _SPECIALTY_WORDS.items() if _has(text, words)), None),
        city=next((c for c, words in _CITIES.items() if _has(text, words)), None),
        date_from=day.isoformat() if day else None,
        date_to=day.isoformat() if day else None,
        time_of_day=part,
        preferred_time=preferred,
        doctor_name=_doctor_name(text),
    )


class DemoProvider:
    name = "demo"
    model = "demo-rules-v5"

    async def respond(
        self,
        *,
        instructions: str,
        history: list[ChatTurn],
        references: list[Reference],
        consultation: ConsultationState,
        user_ref: str,
    ) -> AssistantDraft:
        latest = next((t.content for t in reversed(history) if t.role == "user"), "")
        lang = "ar" if is_arabic(latest) else "en"
        text, labels = _TEXT[lang], _LABELS[lang]
        update = extract(latest)
        data = merge(consultation.data, update)
        concern = data.concern

        cited = next((i for i, r in enumerate(references, 1) if r.language == lang), 1 if references else None)
        library = f"\n\n{text['library'].format(title=references[cited - 1].title)}" if cited and concern else ""
        cited_sources = [cited] if cited and concern else []

        def draft(reply: str, assessment: Assessment | None = None, booking: BookingRequest | None = None) -> AssistantDraft:
            return AssistantDraft(reply=reply, intake_update=update, assessment=assessment, booking_request=booking,
                                  risk_level="low", cited_sources=cited_sources)

        # A booking request wins over the consultation questions (the platform searches and words the reply).
        if booking := extract_booking(latest, consultation.today, offer_pending=consultation.assessment_done):
            return draft(text["checking"], booking=booking)

        if consultation.assessment_done:
            return draft(text["after"] + library)

        missing = missing_fields(data)
        if missing and not consultation.ready_for_assessment:
            ack = text["ack"].format(concern=labels[concern]) if update.concern and missing[0] != "concern" else ""
            return draft(ack + text[missing[0]] + library)

        specialty = _SPECIALTY[concern or "other"]
        specialist = _SPECIALIST[lang][specialty]
        details = ", ".join(filter(None, [data.body_area, data.duration, ", ".join(data.symptoms or [])]))
        serious = _SERIOUS & set(data.symptoms or [])
        assessment = Assessment(
            summary=text["assessment"].format(details=details, concern=labels[concern or "other"], specialist=specialist),
            suggested_specialty=specialty,
            urgency="soon" if serious else "routine",
            visit_preparation=text["prepare"],
            watch_for=text["watch"],
        )
        # The app shows the assessment as a card; the reply just introduces it.
        return draft(f"{text['intro']} {text['offer'].format(specialist=specialist)}{library}", assessment)
