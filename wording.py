"""Wording checks shared by both LLM call types (and their templates).

Model output is untrusted: these checks decide whether it is shown or
replaced by the template. Rules from spec.md and Appendix A: associative
wording only ("tends to", "in your data"), no medical advice, no claims
about hormones or phase-linked energy/creativity, and only the strategies
local statistics supplied.
"""
import re

import db

# Substrings (lowercased) that reject a sentence outright.
BANNED = (
    # medical / clinical
    "diagnos", "treat", "cure", "medic", "supplement", "dose", "prescri", "symptom",
    "pill", "contracepti", "pregnan", "fertil", "ovulat", "doctor", "clinic",
    # biology-as-cause claims (Appendix A4 wording rules)
    "hormon", "estrogen", "oestrogen", "progesterone", "testosterone",
    "creativ", "intuition", "peak", "because", "boost", "your body needs", "you will",
    # instructions instead of associations
    "should", "must", "need to",
    # food / weight (owner's rule)
    "calorie", "diet", "weight loss", "fasting",
)

# How each strategy can show up in prose. Used to catch mentions of a
# strategy that wasn't supplied.
MENTIONS = {
    "walk": ("walk",),
    "yoga": ("yoga",),
    "strength": ("strength", "weights", "lifting", "gym"),
    "cardio": ("cardio", "running", "a run", "jog", "cycling", "swim", "hiit"),
    "rest_day": ("rest day", "day of rest", "day off"),
    "deep_focus_work": ("deep-focus", "deep focus", "focus work", "focused work"),
    "light_admin": ("admin",),
    "social_plans": ("social",),
    "early_night": ("early night", "early bedtime", "bed early", "early to bed"),
    "journaling": ("journal",),
}
assert set(MENTIONS) == set(db.STRATEGIES)

_NUMBER = re.compile(r"\d+")


def banned_words(text: str) -> list[str]:
    low = text.lower()
    return [w for w in BANNED if w in low]


def strategies_mentioned(text: str) -> set[str]:
    low = f" {text.lower()}"
    return {s for s, words in MENTIONS.items() if any(w in low for w in words)}


def numbers_in(text: str) -> set[int]:
    return {int(n) for n in _NUMBER.findall(text)}


def word_count(text: str) -> int:
    return len(text.split())
