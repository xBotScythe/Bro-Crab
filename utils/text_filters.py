import re
import string
from typing import Iterable

try:
    from better_profanity import profanity as _profanity

    _profanity.load_censor_words()

    def contains_profanity(text: str) -> bool:
        return _profanity.contains_profanity(text or "")

except (ImportError, OSError):
    _DEFAULT = {
        "fuck",
        "shit",
        "bitch",
        "cunt",
        "whore",
        "slut",
        "cock",
        "dick",
        "pussy",
    }
    _PUNCT = re.compile(rf"[{re.escape(string.punctuation)}\s]+")

    def _normalize(value: str) -> str:
        return _PUNCT.sub("", (value or "").casefold())

    def contains_profanity(text: str, banned: Iterable[str] = _DEFAULT) -> bool:
        normalized = _normalize(text)
        return any(word in normalized for word in banned)


def clean_text(value: str) -> str:
    return (value or "").strip()
