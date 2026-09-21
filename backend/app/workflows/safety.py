"""
Deterministic red-flag screening for patient chat messages.

Runs on every patient message BEFORE any AI model sees it, in plain code
so it's predictable, testable and can't be talked out of its job by a
cleverly worded message. Covers English, Modern Standard Arabic and
common Egyptian colloquial phrasing.

- HIGH  = possible emergency. The AI is not called at all: the patient
  gets a fixed message directing them to emergency care (Egypt: 123),
  the conversation is escalated and a SafetyEvent needing a human is logged.
- MEDIUM = needs prompt medical attention or extra caution. The AI still
  replies, but a fixed caution is always appended and a SafetyEvent is logged.

Rules deliberately err towards flagging: a false alarm costs a patient
one cautious message; a missed emergency (e.g. vascular occlusion after
filler, which can cause blindness within hours) can cost their sight.

The rules are a first line only. The AI's own risk rating is a second
line (see workflows/chat.py). A clinician should review these rules
before launch (tracked in docs/security.md).
"""

import re
from dataclasses import dataclass, field

from app.models.enums import RiskLevel

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟـ]")  # diacritics + tatweel
_ARABIC_LETTER = re.compile(r"[؀-ۿ]")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize(text: str) -> str:
    """Lower-case, strip Arabic diacritics, unify letter variants and digits, collapse spaces."""
    text = _TASHKEEL.sub("", text.lower()).translate(_ARABIC_DIGITS)
    text = re.sub("[أإآ]", "ا", text).replace("ة", "ه").replace("ى", "ي")
    text = text.replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def is_arabic(text: str) -> bool:
    return bool(_ARABIC_LETTER.search(text))


def _patterns(*sources: str) -> tuple[re.Pattern[str], ...]:
    # Patterns are normalized the same way as messages, so Arabic spelling
    # variants (أ/ا, ة/ه, ى/ي) match either way.
    return tuple(re.compile(normalize(source)) for source in sources)


# Context: a recent injectable / procedure.
INJECTION_CONTEXT = _patterns(
    r"\bfill(er|ers|ed)?\b", r"\binject(ion|ions|ed)?\b", r"\bbotox\b", r"\bneedle\b", r"\bthread(s)? lift\b",
    r"فيلر", r"حقن", r"حقنه", r"بوتوكس", r"بوتكس", r"ابره", r"خيوط",
)
PROCEDURE_CONTEXT = INJECTION_CONTEXT + _patterns(
    r"\blaser\b", r"\bpeel(ing)?\b", r"\bmicroneedling\b", r"\btattoo\b", r"\bprocedure\b", r"\btreatment\b",
    r"ليزر", r"تقشير", r"ديرمابن", r"تاتو", r"جلسه",
)


@dataclass(frozen=True)
class RedFlagRule:
    id: str
    level: RiskLevel
    patterns: tuple[re.Pattern[str], ...]
    # When set, one of these must also appear for the rule to fire.
    context: tuple[re.Pattern[str], ...] = ()


RULES: tuple[RedFlagRule, ...] = (
    # --- HIGH: possible emergencies ------------------------------------------
    RedFlagRule("breathing", RiskLevel.HIGH, _patterns(
        r"can'?t breathe", r"cannot breathe", r"(trouble|difficulty|hard to|struggling to) breath", r"short(ness)? of breath",
        r"throat (is |feels )?(swell|swollen|clos|tight)", r"(tongue|lips?) (is |are |feels? )?(swell|swollen)",
        r"مش (قادر|قادره|عارف|عارفه) (ا)?تنفس", r"صعوبه (في )?(التنفس|النفس)", r"ضيق (في )?(التنفس|النفس)",
        r"نفسي (مقطوع|بيتقطع)", r"زوري (بيقفل|متورم|وارم)", r"(لساني|شفايفي) (وارم|متورم|ورم)",
    )),
    RedFlagRule("anaphylaxis", RiskLevel.HIGH, _patterns(
        r"anaphyla", r"severe allergic", r"allergic shock",
        r"حساسيه شديده", r"صدمه حساسيه",
    )),
    RedFlagRule("vision_loss", RiskLevel.HIGH, _patterns(
        r"(lost|losing|loss of) (my )?(vision|sight|eyesight)", r"can'?t see", r"cannot see", r"went blind", r"sudden(ly)? blind",
        r"مش (شايف|شايفه)", r"فقدت (النظر|البصر)", r"نظري راح", r"مبقتش (اشوف|شايفه|شايف)", r"عمي مفاجئ",
    )),
    RedFlagRule("vision_change_after_injection", RiskLevel.HIGH, _patterns(
        r"blurr(y|ed) vision", r"double vision", r"vision (is )?(blurr|chang|dark)",
        r"زغلله", r"نظري (مغبش|اتغير|ضعف)", r"بشوف (مغبش|دبل|اتنين)",
    ), context=INJECTION_CONTEXT),
    RedFlagRule("skin_colour_after_filler", RiskLevel.HIGH, _patterns(
        r"(white|pale|blanch|blue|bluish|purple|grey|gray|dusky|mottled|dark|black)(ish)? (patch|area|spot|skin|colou?r)",
        r"skin (turn|went|is|looks) (white|pale|blue|purple|grey|gray|dark|dusky|black)",
        r"turn(ed|ing)? (white|blue|purple|grey|gray|black)",
        r"\b(is|are|looks?|went|became|getting) (\w+ and )?(white|pale|blanched|blue|bluish|purple|grey|gray|dusky|mottled|black)\b",
        r"(severe|unbearable|extreme|intense) pain",
        r"(لونه|لونها|الجلد|المكان|المنطقه) (ابيض|بيضا|ازرق|زرقا|بنفسجي|رمادي|اسود|سودا|غامق|اتغير)",
        r"(اتحول|اتحولت|بقي|بقت|بقى|بقت لونها) (ابيض|بيضا|ازرق|زرقا|بنفسجي|اسود|سودا)",
        r"(شفايفي|وشي|ايدي|الجلد|المكان) .{0,12}(بيضا|ابيض|زرقا|ازرق|سودا|اسود)",
        r"(وجع|الم|ألم) (شديد|جامد|مش مستحمل|فظيع)", r"(بتوجعني|بيوجعني|بتالمني|بيالمني) (جدا|اوي|جامد|بشده)",
    ), context=INJECTION_CONTEXT),
    RedFlagRule("chest_pain_or_collapse", RiskLevel.HIGH, _patterns(
        r"chest pain", r"pain in (my )?chest", r"faint(ed|ing)", r"passed out", r"unconscious", r"seizure", r"convuls",
        r"(الم|وجع) (في )?(صدري|الصدر)", r"(اغمي|اغما) (علي|عليا|عليه)", r"فقدت الوعي", r"تشنجات", r"تشنج",
    )),
    RedFlagRule("stroke_signs", RiskLevel.HIGH, _patterns(
        r"face (is )?droop", r"slurred speech", r"(sudden )?(weakness|numbness) (on|in) one side", r"can'?t move (my )?(arm|leg|face)",
        r"وشي (مايل|اتشل)", r"(كلامي|لساني) (تقيل|مش مفهوم)", r"(نص|نصف) (جسمي|وشي) (مش بيتحرك|تنمل|اتشل)",
    )),
    RedFlagRule("severe_skin_reaction", RiskLevel.HIGH, _patterns(
        r"(blister|peeling|skin (is )?coming off).*(fever|mouth sores|eyes)", r"(fever|mouth sores).*(blister|peeling|skin coming off)",
        r"(فقاقيع|بثور|الجلد بيتقشر|جلدي بيقع).*(سخونيه|حراره|حمي|قرح في (بقي|البق))",
        r"(سخونيه|حراره|حمي).*(فقاقيع|بثور|الجلد بيتقشر|جلدي بيقع)",
    )),
    RedFlagRule("self_harm", RiskLevel.HIGH, _patterns(
        r"suicid", r"kill (myself|me)", r"end (my|it all|my life)", r"want to die", r"self[- ]?harm", r"hurt(ing)? myself",
        r"انتحر", r"انتحار", r"(اموت|اقتل) نفسي", r"(عايز|عايزه|نفسي) (اموت|اخلص من حياتي)", r"(اذي|أذي|اءذي) نفسي",
        r"مش عايز(ه)? (اعيش|اكمل|استمر)", r"(زهقت|تعبت) من (حياتي|الدنيا)", r"مليش نفس اعيش", r"حياتي مش مستاهله",
    )),
    # Fever *and* spreading redness after a procedure is not "keep an eye on
    # it": it needs assessment today, so it outranks `infection_signs`.
    RedFlagRule("spreading_infection", RiskLevel.HIGH, _patterns(
        r"(fever|temperature|\b3[89](\.\d)?\b|\b40(\.\d)?\b).{0,80}(spread|hot|warm|red and (hot|swollen))",
        r"(spread|hot|warm).{0,80}(fever|temperature|\b3[89](\.\d)?\b|\b40(\.\d)?\b)",
        r"(سخونيه|حراره|حمي|\b3[89]\b|\b40\b).{0,80}(بينتشر|بيزيد|سخن|سخنه|حاميه)",
        r"(بينتشر|بيزيد|سخن|سخنه|حاميه).{0,80}(سخونيه|حراره|حمي|\b3[89]\b|\b40\b)",
    ), context=PROCEDURE_CONTEXT),
    # --- MEDIUM: prompt attention or extra caution -----------------------------
    RedFlagRule("not_settling_after_procedure", RiskLevel.MEDIUM, _patterns(
        r"still (red|swollen|sore|painful|bruised|hurting)",
        r"(redness|swelling|bruis\w+|pain) (is )?(still|has ?n'?t|not) (there|gone|going down|settled|improv\w+)",
        r"(\d+|two|three|four|five|several) (days?|weeks?) (later|after|since).{0,40}(red|swollen|sore|pain|bruis)",
        r"لسه (احمرار|متورم|وارم|بيوجع|موجود|موجوده)", r"(الاحمرار|الورم|التورم|الوجع|الالم) لسه",
        r"(الاحمرار|الورم|التورم) (ما ?زال|لسه) (موجود|موجوده|مكانه)",
    ), context=PROCEDURE_CONTEXT),
    RedFlagRule("infection_signs", RiskLevel.MEDIUM, _patterns(
        r"\bpus\b", r"oozing", r"(hot|warm) (and )?(swollen|red)", r"spreading (red|redness|rash)", r"\bfever\b", r"infect",
        r"صديد", r"(سخن|سخنه) و ?(وارم|متورم)", r"احمرار (بيزيد|بينتشر)", r"سخونيه", r"التهاب", r"حراره",
    ), context=PROCEDURE_CONTEXT),
    RedFlagRule("changing_mole", RiskLevel.MEDIUM, _patterns(
        r"(mole|spot|lesion|freckle).*(bleed|grow|getting bigger|chang|irregular|itch)",
        r"(bleed|grow|getting bigger|chang|irregular).*(mole|lesion)",
        r"(شامه|حسنه|وحمه).*(بتنزف|بتكبر|بيكبر|اتغير|لونها|بتهرش|بتاكلني)",
    )),
    RedFlagRule("pregnancy", RiskLevel.MEDIUM, _patterns(
        r"\bpregnan", r"breast ?feeding", r"nursing (my )?baby",
        r"\bحامل\b", r"\b(ال)?حمل\b", r"\b(برضع|بارضع)\b", r"رضاعه", r"\bمرضع(ه)?\b",
    )),
    RedFlagRule("minor", RiskLevel.MEDIUM, _patterns(
        # Teen ages alone ("I'm 16"); single digits only with "years old", so
        # "I'm 2 weeks after filler" doesn't read as a two-year-old.
        r"\bi'?m 1[0-7]\b(?! ?(weeks?|days?|months?|hours?|kg|cm|%))", r"\bi am 1[0-7]\b(?! ?(weeks?|days?|months?|hours?|kg|cm|%))",
        r"\b(1[0-7]|[1-9]) ?(years old|yrs old|y/?o)\b",
        r"(عندي|عمري|سني) (1[0-7]|[1-9]) (سنه|سنين)",
    )),
    RedFlagRule("burn_after_treatment", RiskLevel.MEDIUM, _patterns(
        r"\bburn(ed|t|s|ing)?\b", r"blister",
        r"حرق", r"اتحرق", r"فقاقيع", r"بثور",
    ), context=PROCEDURE_CONTEXT),
)


@dataclass(frozen=True)
class SafetyAssessment:
    level: RiskLevel
    flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_emergency(self) -> bool:
        return self.level == RiskLevel.HIGH


def assess(message: str) -> SafetyAssessment:
    text = normalize(message)
    matched = [
        rule
        for rule in RULES
        if any(p.search(text) for p in rule.patterns) and (not rule.context or any(c.search(text) for c in rule.context))
    ]
    if not matched:
        return SafetyAssessment(RiskLevel.LOW)
    level = RiskLevel.HIGH if any(r.level == RiskLevel.HIGH for r in matched) else RiskLevel.MEDIUM
    return SafetyAssessment(level, tuple(r.id for r in matched))


# --- Fixed responses (never written by the AI) ------------------------------------

EMERGENCY_NUMBER = "123"

_EMERGENCY = {
    "en": (
        "What you describe could be a medical emergency. Please call {number} (ambulance) now or go to the "
        "nearest emergency department. If this started after an injection or treatment, also call the clinic "
        "that treated you right away. I can't help with emergencies in this chat. A member of our team has "
        "been notified."
    ),
    "ar": (
        "اللي بتوصفيه ممكن يكون حالة طارئة. من فضلك اتصلي بالإسعاف على {number} دلوقتي أو روحي لأقرب طوارئ. "
        "لو ده بدأ بعد حقن أو جلسة، كلمي العيادة اللي عملتلك الإجراء فوراً كمان. مقدرش أساعد في الحالات الطارئة "
        "هنا في الشات، وتم إبلاغ فريقنا."
    ),
}
_SELF_HARM = {
    "en": (
        "I'm really sorry you're feeling this way, and I'm glad you said something. You deserve support right now. "
        "If you might act on these thoughts, please call {number} or go to the nearest emergency department, and "
        "reach out to someone you trust to stay with you. A member of our team has been notified."
    ),
    "ar": (
        "أنا آسفة جداً إنك حاسة كده، وكويس إنك اتكلمتي. إنتي تستاهلي دعم دلوقتي. لو ممكن تأذي نفسك، من فضلك "
        "اتصلي على {number} أو روحي لأقرب طوارئ، وكلمي حد بتثقي فيه يكون معاكي. تم إبلاغ فريقنا."
    ),
}
_CAUTION = {
    "infection_signs": {
        "en": "Signs of infection after a procedure need a doctor's check within 24 hours. If you have a high fever or the redness is spreading fast, go to an emergency department.",
        "ar": "علامات الالتهاب بعد أي إجراء محتاجة كشف دكتور خلال 24 ساعة. لو عندك سخونية عالية أو الاحمرار بينتشر بسرعة، روحي الطوارئ.",
    },
    "changing_mole": {
        "en": "A mole that bleeds, grows or changes should be examined by a dermatologist soon, in person.",
        "ar": "الشامة اللي بتنزف أو بتكبر أو بتتغير لازم يكشف عليها دكتور جلدية قريب، كشف حضوري.",
    },
    "pregnancy": {
        "en": "Many cosmetic treatments and skin medicines aren't recommended during pregnancy or breastfeeding. Please check with your doctor before any treatment.",
        "ar": "علاجات تجميلية وأدوية جلدية كتير مش مناسبة أثناء الحمل أو الرضاعة. من فضلك استشيري دكتورك قبل أي علاج.",
    },
    "minor": {
        "en": "For anyone under 18, cosmetic treatments need a parent or guardian and a doctor's in-person assessment.",
        "ar": "لأي حد أقل من 18 سنة، العلاجات التجميلية محتاجة موافقة ولي الأمر وكشف حضوري عند الدكتور.",
    },
    "burn_after_treatment": {
        "en": "A burn or blistering after a treatment should be seen by a doctor soon. Contact the clinic that treated you.",
        "ar": "الحرق أو الفقاقيع بعد جلسة لازم دكتور يشوفها قريب. كلمي العيادة اللي عملتلك الجلسة.",
    },
    "model_flagged": {
        "en": "Based on what you've shared, please see a doctor soon. If symptoms are severe or getting worse quickly, call {number} or go to an emergency department.",
        "ar": "بناءً على اللي قولتيه، من فضلك اكشفي عند دكتور قريب. لو الأعراض شديدة أو بتزيد بسرعة، اتصلي على {number} أو روحي الطوارئ.",
    },
}


def emergency_message(assessment: SafetyAssessment, language: str) -> str:
    template = _SELF_HARM if assessment.flags == ("self_harm",) else _EMERGENCY
    return template[language].format(number=EMERGENCY_NUMBER)


def caution_message(flags: tuple[str, ...], language: str) -> str:
    notes = [_CAUTION[f][language].format(number=EMERGENCY_NUMBER) for f in flags if f in _CAUTION]
    return "\n\n".join(dict.fromkeys(notes))  # de-duplicated, in rule order
