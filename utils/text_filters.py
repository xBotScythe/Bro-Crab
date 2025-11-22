# thin wrapper around better_profanity so callsites stay simple
from better_profanity import profanity as _profanity

_profanity.load_censor_words()


def clean_text(value: str):
    return (value or "").strip()


def contains_profanity(text: str):
    return _profanity.contains_profanity(text or "")
