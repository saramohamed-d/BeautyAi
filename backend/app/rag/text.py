"""Small text helpers shared by the demo embedder and keyword search."""

from app.workflows.safety import normalize

# Function words that carry no topic, in English and (normalized) Arabic.
STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "it", "my", "i", "you", "your",
    "with", "what", "how", "can", "do", "does", "be", "this", "that", "have", "has", "me", "about", "from", "at",
    "when", "should", "will", "would", "could", "get", "got", "after", "before", "very", "much", "many", "some",
    "any", "there", "their", "they", "we", "our", "his", "her", "she", "he", "was", "were", "been", "if", "then",
    "than", "so", "not", "no", "yes", "which", "who", "why", "where", "also", "just", "only", "see", "tell", "need",
    "في", "من", "علي", "الي", "عن", "و", "او", "ان", "انا", "انت", "ده", "دي", "هل", "ايه", "اللي", "مع", "عندي", "بس",
    "بعد", "قبل", "كل", "ازاي", "ليه", "امتي", "مش", "لو", "كده", "اوي", "حاجه", "عايزه", "عايز", "ممكن",
})

_AR_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال", "و")
_AR_SUFFIXES = ("ها", "هم", "ات", "ين", "ون", "ي", "ه")


def is_stopword(word: str) -> bool:
    return normalize(word) in STOPWORDS


def light_arabic_stem(word: str) -> str:
    """
    Strips one common prefix and one suffix from a normalized Arabic word
    ("الشعر"/"شعري" → "شعر", "الولاده" → "ولاد"). Deliberately crude: used
    only by the offline demo embedder; Postgres's Arabic analyzer does the
    real stemming for keyword search.
    """
    for prefix in _AR_PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            word = word[len(prefix):]
            break
    for suffix in _AR_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word
