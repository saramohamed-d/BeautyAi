"""
Sprint 7: deterministic red-flag rules (app/workflows/safety.py).

Positive cases are the phrasings patients actually use (English, MSA,
Egyptian colloquial). Negative cases guard against the false positives
found while writing the rules.
"""

import pytest

from app.models.enums import RiskLevel
from app.workflows.safety import assess, caution_message, emergency_message, normalize

EMERGENCIES = [
    ("I got filler yesterday and now the skin near my nose turned white", "skin_colour_after_filler"),
    ("after my lip filler the area is dusky and blue", "skin_colour_after_filler"),
    ("severe pain after filler injection this morning", "skin_colour_after_filler"),
    ("عملت فيلر امبارح والمكان لونه ازرق", "skin_colour_after_filler"),
    ("بعد الحقن الجلد اتحول أبيض", "skin_colour_after_filler"),
    ("وجع شديد بعد الفيلر", "skin_colour_after_filler"),
    ("I can't see out of my left eye after botox", "vision_loss"),
    ("blurry vision since my filler this morning", "vision_change_after_injection"),
    ("بعد الفيلر عندي زغللة في عيني", "vision_change_after_injection"),
    ("مش شايفة كويس من عيني", "vision_loss"),
    ("I can't breathe and my lips are swelling", "breathing"),
    ("مش قادرة اتنفس بعد الحقن", "breathing"),
    ("زوري بيقفل", "breathing"),
    ("I think I'm having a severe allergic reaction", "anaphylaxis"),
    ("عندي حساسية شديدة", "anaphylaxis"),
    ("I fainted after the session", "chest_pain_or_collapse"),
    ("عندي ألم في صدري", "chest_pain_or_collapse"),
    ("اغمى عليا", "chest_pain_or_collapse"),
    ("my face is drooping on one side", "stroke_signs"),
    ("my skin is peeling everywhere and I have a fever", "severe_skin_reaction"),
    ("جلدي بيقع وعندي سخونية", "severe_skin_reaction"),
    ("I want to kill myself", "self_harm"),
    ("عايزة اموت", "self_harm"),
    ("بفكر انتحر", "self_harm"),
]

CAUTIONS = [
    ("there is pus where they injected the filler", "infection_signs"),
    ("the laser area is hot and swollen", "infection_signs"),
    ("مكان الحقن فيه صديد", "infection_signs"),
    ("my mole is bleeding and getting bigger", "changing_mole"),
    ("الشامة بتكبر ولونها اتغير", "changing_mole"),
    ("I'm pregnant, can I get botox?", "pregnancy"),
    ("انا حامل وعايزة اعمل بوتكس", "pregnancy"),
    ("I'm 16 and want lip filler", "minor"),
    ("I am 9 years old", "minor"),
    ("عندي 16 سنة وعايزة فيلر", "minor"),
    ("the chemical peel burned my face", "burn_after_treatment"),
    ("الليزر عمل حرق في رجلي", "burn_after_treatment"),
]

ORDINARY = [
    "I have acne on my cheeks, what should I do?",
    "I had filler last year and it looks great",
    "blurry vision since years, I wear glasses",  # no recent injection
    "I am 25 years old and want to treat dark spots",
    "I'm 2 weeks after filler and happy with it",
    "I'm 15% sure this is melasma",
    "عندي حبوب في وشي من سنة",
    "الوجع مش مستحمل من البرد",  # "unbearable" must not read as pregnancy
    "عايزة اعمل تنظيف بشرة",
    "What does laser hair removal cost?",
]


@pytest.mark.parametrize("message,flag", EMERGENCIES)
def test_emergencies_are_high(message: str, flag: str) -> None:
    result = assess(message)
    assert result.level == RiskLevel.HIGH, result
    assert flag in result.flags


@pytest.mark.parametrize("message,flag", CAUTIONS)
def test_cautions_are_medium(message: str, flag: str) -> None:
    result = assess(message)
    assert result.level == RiskLevel.MEDIUM, result
    assert flag in result.flags


@pytest.mark.parametrize("message", ORDINARY)
def test_ordinary_messages_are_low(message: str) -> None:
    assert assess(message).level == RiskLevel.LOW, assess(message)


def test_high_wins_over_medium() -> None:
    result = assess("I'm pregnant and can't breathe")
    assert result.level == RiskLevel.HIGH
    assert {"pregnancy", "breathing"} <= set(result.flags)


def test_normalization_unifies_arabic_variants_and_digits() -> None:
    assert normalize("أنا حاملة ١٦ سنة") == normalize("انا حامله 16 سنه")
    assert normalize("مُــشْ") == "مش"


def test_fixed_messages_name_the_ambulance_number_in_both_languages() -> None:
    for lang in ("en", "ar"):
        assert "123" in emergency_message(assess("I can't breathe"), lang)
        assert "123" in emergency_message(assess("I want to kill myself"), lang)
        assert caution_message(("pregnancy",), lang)
