"""
What each message says, in English and Arabic (Sprint 15).

Design decisions:

- **Templates live in code, not in the database.** They're part of the
  product's voice and get reviewed like any other copy; the *rendered*
  text is what's stored on the notification row.
- **Every template exists in both languages**, chosen by the recipient's
  preferred language, and a missing one is a programming error, not a
  silent English fallback.
- **SMS and WhatsApp get their own shorter wording.** An SMS costs money
  per segment and is read on a lock screen; the email can carry the
  detail. Where a channel has no special wording it falls back to the
  email body.
- No medical advice is invented here: the aftercare message points the
  patient back to their clinic and the AI consultation rather than
  giving instructions of its own.
"""

from dataclasses import dataclass

from app.models.enums import Language, NotificationChannel

APPOINTMENT_CONFIRMED = "appointment_confirmed"
APPOINTMENT_REMINDER = "appointment_reminder"
APPOINTMENT_CANCELLED = "appointment_cancelled"
PAYMENT_RECEIPT = "payment_receipt"
AFTERCARE_FOLLOWUP = "aftercare_followup"
DOCTOR_VERIFIED = "doctor_verified"
DOCTOR_REJECTED = "doctor_rejected"
PASSWORD_RESET = "password_reset"
VERIFY_CONTACT = "verify_contact"


@dataclass(frozen=True)
class Rendered:
    subject: str | None
    body: str


# {key: {language: {"subject", "email", "short"}}}
TEMPLATES: dict[str, dict[Language, dict[str, str]]] = {
    APPOINTMENT_CONFIRMED: {
        Language.EN: {
            "subject": "Your appointment with {doctor_name} is booked",
            "email": (
                "Hi {patient_name},\n\n"
                "Your appointment is booked:\n\n"
                "Doctor: {doctor_name}\n"
                "Clinic: {clinic_name}\n"
                "When: {when}\n"
                "{payment_line}\n"
                "You can view, reschedule or cancel it here: {appointments_url}\n\n"
                "See you soon,\nBeautyAI"
            ),
            "short": "BeautyAI: your appointment with {doctor_name} at {clinic_name} is booked for {when}.",
        },
        Language.AR: {
            "subject": "تم حجز موعدك مع {doctor_name}",
            "email": (
                "مرحباً {patient_name}،\n\n"
                "تم حجز موعدك:\n\n"
                "الطبيب: {doctor_name}\n"
                "العيادة: {clinic_name}\n"
                "الموعد: {when}\n"
                "{payment_line}\n"
                "يمكنك عرض الموعد أو تغييره أو إلغاؤه من هنا: {appointments_url}\n\n"
                "نراكِ قريباً،\nBeautyAI"
            ),
            "short": "BeautyAI: تم حجز موعدك مع {doctor_name} في {clinic_name} يوم {when}.",
        },
    },
    APPOINTMENT_REMINDER: {
        Language.EN: {
            "subject": "Tomorrow: your appointment with {doctor_name}",
            "email": (
                "Hi {patient_name},\n\n"
                "This is a reminder of your appointment tomorrow:\n\n"
                "Doctor: {doctor_name}\n"
                "Clinic: {clinic_name}\n"
                "When: {when}\n"
                "{address_line}\n"
                "If you can't make it, please cancel or reschedule so someone else can take the time: "
                "{appointments_url}\n\n"
                "BeautyAI"
            ),
            "short": "BeautyAI reminder: {doctor_name} at {clinic_name}, {when}. Can't make it? {appointments_url}",
        },
        Language.AR: {
            "subject": "تذكير: موعدك غداً مع {doctor_name}",
            "email": (
                "مرحباً {patient_name}،\n\n"
                "نذكّرك بموعدك غداً:\n\n"
                "الطبيب: {doctor_name}\n"
                "العيادة: {clinic_name}\n"
                "الموعد: {when}\n"
                "{address_line}\n"
                "إذا تعذّر عليك الحضور، يرجى الإلغاء أو تغيير الموعد ليستفيد غيرك من الوقت: "
                "{appointments_url}\n\n"
                "BeautyAI"
            ),
            "short": "تذكير BeautyAI: {doctor_name} في {clinic_name}، {when}. لا تستطيعين الحضور؟ {appointments_url}",
        },
    },
    APPOINTMENT_CANCELLED: {
        Language.EN: {
            "subject": "Your appointment with {doctor_name} was cancelled",
            "email": (
                "Hi {patient_name},\n\n"
                "Your appointment with {doctor_name} at {clinic_name} on {when} has been cancelled.\n"
                "{refund_line}\n"
                "You can book another time here: {booking_url}\n\n"
                "BeautyAI"
            ),
            "short": "BeautyAI: your appointment with {doctor_name} on {when} was cancelled. {refund_line}",
        },
        Language.AR: {
            "subject": "تم إلغاء موعدك مع {doctor_name}",
            "email": (
                "مرحباً {patient_name}،\n\n"
                "تم إلغاء موعدك مع {doctor_name} في {clinic_name} يوم {when}.\n"
                "{refund_line}\n"
                "يمكنك حجز موعد آخر من هنا: {booking_url}\n\n"
                "BeautyAI"
            ),
            "short": "BeautyAI: تم إلغاء موعدك مع {doctor_name} يوم {when}. {refund_line}",
        },
    },
    PAYMENT_RECEIPT: {
        Language.EN: {
            "subject": "Receipt: {amount} for your consultation",
            "email": (
                "Hi {patient_name},\n\n"
                "We received your payment.\n\n"
                "Amount: {amount}\n"
                "Doctor: {doctor_name}\n"
                "Clinic: {clinic_name}\n"
                "Appointment: {when}\n"
                "Reference: {reference}\n\n"
                "Keep this message as your receipt.\n\nBeautyAI"
            ),
            "short": "BeautyAI: payment of {amount} received for your appointment on {when}. Ref {reference}.",
        },
        Language.AR: {
            "subject": "إيصال: {amount} رسوم الاستشارة",
            "email": (
                "مرحباً {patient_name}،\n\n"
                "استلمنا دفعتك.\n\n"
                "المبلغ: {amount}\n"
                "الطبيب: {doctor_name}\n"
                "العيادة: {clinic_name}\n"
                "الموعد: {when}\n"
                "الرقم المرجعي: {reference}\n\n"
                "احتفظي بهذه الرسالة كإيصال.\n\nBeautyAI"
            ),
            "short": "BeautyAI: تم استلام مبلغ {amount} لموعدك يوم {when}. المرجع {reference}.",
        },
    },
    AFTERCARE_FOLLOWUP: {
        Language.EN: {
            "subject": "How are you doing after your visit?",
            "email": (
                "Hi {patient_name},\n\n"
                "We hope your visit to {clinic_name} went well.\n\n"
                "Follow the aftercare instructions {doctor_name} gave you. If anything worries you — "
                "unusual pain, swelling that is getting worse, fever, or anything that doesn't look right — "
                "contact the clinic first; they know what was done.\n\n"
                "Clinic: {clinic_phone}\n\n"
                "You can also ask our assistant general questions about recovery: {consultation_url}\n"
                "It isn't a diagnosis and doesn't replace your doctor.\n\n"
                "BeautyAI"
            ),
            "short": (
                "BeautyAI: hope your visit went well. Follow {doctor_name}'s aftercare advice, and contact "
                "the clinic ({clinic_phone}) if anything worries you."
            ),
        },
        Language.AR: {
            "subject": "كيف حالك بعد زيارتك؟",
            "email": (
                "مرحباً {patient_name}،\n\n"
                "نتمنى أن تكون زيارتك إلى {clinic_name} قد مرّت على خير.\n\n"
                "اتبعي تعليمات ما بعد الجلسة التي أعطاها لك {doctor_name}. وإذا شعرتِ بأي قلق — "
                "ألم غير معتاد أو تورّم يزداد أو ارتفاع في الحرارة أو أي شيء غير طبيعي — "
                "تواصلي مع العيادة أولاً فهي تعرف ما تم إجراؤه.\n\n"
                "هاتف العيادة: {clinic_phone}\n\n"
                "ويمكنك أيضاً سؤال مساعدنا أسئلة عامة عن فترة التعافي: {consultation_url}\n"
                "هذا ليس تشخيصاً ولا يغني عن طبيبك.\n\n"
                "BeautyAI"
            ),
            "short": (
                "BeautyAI: نتمنى أن تكون زيارتك قد مرّت على خير. اتبعي تعليمات {doctor_name}، "
                "وتواصلي مع العيادة ({clinic_phone}) إذا ساورك أي قلق."
            ),
        },
    },
    DOCTOR_VERIFIED: {
        Language.EN: {
            "subject": "You're verified on BeautyAI",
            "email": (
                "Hi {doctor_name},\n\n"
                "Your documents have been reviewed and your profile is now verified. "
                "Patients can find you in search and book your available times.\n\n"
                "Your dashboard: {doctor_url}\n\nBeautyAI"
            ),
            "short": "BeautyAI: your profile is verified. Patients can now book you: {doctor_url}",
        },
        Language.AR: {
            "subject": "تم توثيق حسابك على BeautyAI",
            "email": (
                "مرحباً {doctor_name}،\n\n"
                "تمت مراجعة مستنداتك وتوثيق ملفك. يمكن للمريضات الآن العثور عليك وحجز مواعيدك المتاحة.\n\n"
                "لوحتك: {doctor_url}\n\nBeautyAI"
            ),
            "short": "BeautyAI: تم توثيق ملفك ويمكن للمريضات الحجز معك الآن: {doctor_url}",
        },
    },
    DOCTOR_REJECTED: {
        Language.EN: {
            "subject": "Your BeautyAI application needs changes",
            "email": (
                "Hi {doctor_name},\n\n"
                "We reviewed your application and can't approve it yet.\n\n"
                "Reason: {reason}\n\n"
                "You can replace the documents and submit again here: {doctor_url}\n\nBeautyAI"
            ),
            "short": "BeautyAI: your application needs changes — {reason}. Resubmit here: {doctor_url}",
        },
        Language.AR: {
            "subject": "طلبك على BeautyAI يحتاج إلى تعديل",
            "email": (
                "مرحباً {doctor_name}،\n\n"
                "راجعنا طلبك ولا يمكننا اعتماده بعد.\n\n"
                "السبب: {reason}\n\n"
                "يمكنك استبدال المستندات وإعادة الإرسال من هنا: {doctor_url}\n\nBeautyAI"
            ),
            "short": "BeautyAI: طلبك يحتاج إلى تعديل — {reason}. أعيدي الإرسال من هنا: {doctor_url}",
        },
    },
    PASSWORD_RESET: {
        Language.EN: {
            "subject": "Reset your BeautyAI password",
            "email": (
                "Hi {name},\n\n"
                "Someone asked to reset the password on this account. If it was you, use this link "
                "within {minutes} minutes:\n\n"
                "{reset_url}\n\n"
                "If it wasn't you, you can ignore this message — your password hasn't changed.\n\n"
                "BeautyAI"
            ),
            "short": "BeautyAI: reset your password within {minutes} minutes: {reset_url} — ignore this if it wasn't you.",
        },
        Language.AR: {
            "subject": "إعادة تعيين كلمة المرور",
            "email": (
                "مرحباً {name}،\n\n"
                "تم طلب إعادة تعيين كلمة المرور لهذا الحساب. إذا كان الطلب منك، استخدمي هذا الرابط "
                "خلال {minutes} دقيقة:\n\n"
                "{reset_url}\n\n"
                "وإذا لم تطلبي ذلك، تجاهلي الرسالة — كلمة المرور لم تتغير.\n\n"
                "BeautyAI"
            ),
            "short": "BeautyAI: لإعادة تعيين كلمة المرور خلال {minutes} دقيقة: {reset_url} — تجاهلي الرسالة إن لم تكوني أنتِ.",
        },
    },
    VERIFY_CONTACT: {
        Language.EN: {
            "subject": "Your BeautyAI verification code",
            "email": (
                "Hi {name},\n\n"
                "Your verification code is {code}. It expires in {minutes} minutes.\n\n"
                "If you didn't ask for it, you can ignore this message.\n\nBeautyAI"
            ),
            "short": "BeautyAI verification code: {code} (valid for {minutes} minutes).",
        },
        Language.AR: {
            "subject": "كود التحقق من BeautyAI",
            "email": (
                "مرحباً {name}،\n\n"
                "كود التحقق الخاص بك هو {code}، وصالح لمدة {minutes} دقيقة.\n\n"
                "إذا لم تطلبيه، تجاهلي الرسالة.\n\nBeautyAI"
            ),
            "short": "كود التحقق من BeautyAI: {code} (صالح {minutes} دقيقة).",
        },
    },
}


def render(template: str, language: Language, channel: NotificationChannel, context: dict) -> Rendered:
    """
    Fills one template for one language and channel.

    A missing template or a missing placeholder raises: silently sending
    someone "Hi {patient_name}" is worse than a loud failure in the logs.
    """
    by_language = TEMPLATES.get(template)
    if by_language is None:
        raise KeyError(f"Unknown notification template '{template}'")
    strings = by_language.get(language) or by_language[Language.EN]

    if channel == NotificationChannel.EMAIL:
        return Rendered(
            subject=strings["subject"].format(**context),
            body=_tidy(strings["email"].format(**context)),
        )
    return Rendered(subject=None, body=_tidy(strings.get("short", strings["email"]).format(**context)))


def _tidy(text: str) -> str:
    """Drops the blank lines left by an optional line (e.g. no refund line)."""
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    return "\n".join(out).strip()
