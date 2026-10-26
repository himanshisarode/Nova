""""Did You Know?" content (spec.md Feature 14): ten fixed question/answer
pairs, kept apart from display code so the wording can be reviewed on its
own. Written once, not AI-generated, not user-editable; general
education, not clinically reviewed. Approved 2026-10-27.

Growing past ten items, or claiming clinical review, is a scope change —
amend spec.md first.
"""
QNA: list[dict[str, str]] = [
    {
        "question": 'Is a "normal" cycle exactly 28 days?',
        "answer": (
            "Not usually! 28 days is an average, not a rule. For adults, cycles anywhere from "
            "about 24 to 38 days are considered typical, and it's common for your own cycle to "
            "shift by up to about a week from month to month. Cycles in the first few years "
            "after periods start, and in the years before menopause, often vary even more."
        ),
    },
    {
        "question": "Can you get pregnant during your period?",
        "answer": (
            "It's less likely, but it's possible. Sperm can survive for up to about five days, "
            "so if you have a short cycle or a long period, ovulation can come soon enough "
            "afterwards for sex during your period to lead to pregnancy. A period is never a "
            "reliable form of contraception, and neither are Nova's estimates."
        ),
    },
    {
        "question": "Does ovulation always happen on day 14?",
        "answer": (
            'No. "Day 14" assumes a 28-day cycle with ovulation exactly in the middle. The '
            "second half of the cycle, after ovulation, tends to be fairly steady at about 12–14 "
            "days, so if your cycles are longer or shorter, ovulation usually moves too. It can "
            "also vary from one cycle to the next. That's why Nova shows the fertile window as "
            "an estimate, not a fixed date."
        ),
    },
    {
        "question": "Is a twinge of pain in the middle of my cycle normal?",
        "answer": (
            "Often, yes. Many people feel a dull ache or sharp twinge on one side of the lower "
            'belly around ovulation, sometimes called mittelschmerz ("middle pain"). It usually '
            "lasts from a few minutes to a day or two and is harmless. Pain that's severe, lasts "
            "longer, or comes with fever or vomiting is different, and worth getting checked."
        ),
    },
    {
        "question": "Does Nova work if I'm on hormonal birth control?",
        "answer": (
            "Not really. The pill, patch, ring, injection, implant and hormonal IUD all change "
            "or pause the natural cycle that Nova's predictions are built on. The bleed you get "
            "on the pill, for example, is a withdrawal bleed, not a true period. You're welcome "
            "to keep logging, but treat the predictions as not meaningful while you're on it. "
            "(The copper IUD has no hormones, so your natural cycle continues.)"
        ),
    },
    {
        "question": "Does the colour of period blood mean anything?",
        "answer": (
            "On its own, usually not. Bright red, dark red and brown are all common. Brown is "
            "often just older blood, especially at the start or end of a period. What matters "
            "more is change alongside other signs: bleeding between periods, a strong unusual "
            "smell, unusual discharge, or fever. Those are worth mentioning to a doctor."
        ),
    },
    {
        "question": "Can stress, travel or illness delay a period?",
        "answer": (
            "Yes. Stress, travel, illness, big changes in sleep, exercise or weight can all "
            "affect the hormones that trigger ovulation, and a delayed ovulation means a later "
            "period. One late cycle is usually nothing to worry about. If there's any chance you "
            "could be pregnant, a test is the quickest way to know. If your periods stop for "
            "three months or more, check in with a doctor."
        ),
    },
    {
        "question": "Are PCOS and endometriosis rare?",
        "answer": (
            "No, both are common, each affecting roughly 1 in 10 women and people who "
            "menstruate. They're also often diagnosed late, sometimes years after symptoms "
            "start. Signs that can point to PCOS include periods that are very irregular or far "
            "apart, acne, and extra hair growth. Signs that can point to endometriosis include "
            "period pain that stops you doing everyday things, pain during sex, and pain with "
            "bowel movements. Period pain that disrupts your life isn't something you just have "
            "to put up with."
        ),
    },
    {
        "question": "Is a heavy flow always a problem?",
        "answer": (
            "Not on its own. Flow varies a lot from person to person. Signs that bleeding may be "
            "too heavy include soaking through a pad or tampon every hour or two, passing clots "
            "bigger than a large coin, periods lasting more than seven days, or feeling tired, "
            "dizzy or short of breath. Any of these, or heavy periods that simply affect your "
            "life, are worth raising with a doctor. If you're soaking through a pad or tampon "
            "every hour for several hours in a row, or feel faint, seek care promptly."
        ),
    },
    {
        "question": "Does fertility suddenly drop at a certain age?",
        "answer": (
            "No. It declines gradually, not at a cliff edge on a particular birthday. It usually "
            "starts to decline in the early 30s, more noticeably after about 35, and more steeply "
            "after 40, but there's a lot of variation between people. Age affects sperm too, more "
            "slowly. If you're trying to conceive, the usual advice is to see a doctor after 12 "
            "months of trying, or after 6 months if you're 35 or over."
        ),
    },
]

# Shown under every answer by the page, identically for all entries.
EDUCATION_LABEL = (
    "General education, not personal medical advice. If this sounds like you, "
    "a doctor or gynecologist is the right person to ask."
)
