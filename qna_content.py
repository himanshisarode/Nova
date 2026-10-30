""""Did You Know?" content (spec.md Feature 14): a fixed set of question/
answer pairs in three sections, kept apart from display code so the
wording can be reviewed on its own. Written once, not AI-generated, not
user-editable; general education, not clinically reviewed.

The original ten were approved 2026-10-27. Level 2 (2026-10-31) adds
cycle-syncing and phase entries from the owner's draft, merged with the
original ten so nothing is said twice (DECISIONS.md, "Did You Know?").
Growing further, or claiming clinical review, is a scope change — amend
spec.md first.
"""
SECTIONS: list[tuple[str, list[dict[str, str]]]] = [
    ("Cycle syncing", [
        {
            "question": "What is cycle syncing?",
            "answer": (
                "Cycle syncing means planning things like exercise, work, rest and social time "
                "around the phases of your menstrual cycle, instead of treating every week the "
                "same. The idea is that hormones shift through the month, so what feels good may "
                "shift too. It comes from wellness circles and is not a medical treatment."
            ),
        },
        {
            "question": "Does cycle syncing actually work?",
            "answer": (
                "Not reliably for everyone. A large review of exercise studies found at most a "
                "very small dip in performance early in the cycle, and said the evidence isn't "
                "strong enough to recommend one plan for everyone. Studies that track mood day by "
                "day find that phase explains only part of how a day feels, and that people differ "
                "a lot. So treat phase tips as ideas to test on yourself, not as rules. That's what "
                "Nova's \"What works for me\" does, using your own log."
            ),
        },
        {
            "question": "Why might energy or mood change across a cycle?",
            "answer": (
                "Estrogen and progesterone rise and fall through the month, and they act on the "
                "brain as well as the reproductive system. Some people notice clear patterns and "
                "others notice nothing at all. Sleep, stress, health and routine usually matter "
                "just as much as the phase you're in."
            ),
        },
    ]),
    ("Your cycle's phases", [
        {
            "question": "What are the phases of the menstrual cycle?",
            "answer": (
                "A cycle runs from the first day of one period to the day before the next. It's "
                "usually described in four phases: your period, the follicular phase (an egg gets "
                "ready), ovulation (the egg is released) and the luteal phase (the body waits to "
                "see if there's a pregnancy). The period overlaps the start of the follicular "
                "phase, so the four aren't separate blocks. Nova's findings group them into three: "
                "period days, the follicular phase including ovulation, and the luteal phase."
            ),
        },
        {
            "question": "What happens during my period?",
            "answer": (
                "If there's no pregnancy, the lining of the uterus is shed as your period. "
                "Estrogen and progesterone are both low at this point. Most periods last between "
                "three and seven days, and cramps, tiredness and headaches are common."
            ),
        },
        {
            "question": "What is the follicular phase?",
            "answer": (
                "It starts on the first day of your period and ends at ovulation. A hormone called "
                "FSH makes follicles in the ovaries grow, and rising estrogen rebuilds the lining "
                "of the uterus. This is the part of the cycle that varies most between people: a "
                "large study of app users found it averaged about 17 days, with a wide range."
            ),
        },
        {
            "question": "When does ovulation happen — is it always day 14?",
            "answer": (
                "A sudden rise in LH, a hormone from the brain, makes an ovary release an egg, "
                "which lives for about 12 to 24 hours. \"Day 14\" only fits a textbook 28-day cycle. "
                "The half after ovulation stays fairly steady, so in longer or shorter cycles "
                "ovulation usually moves, and a cycle that runs long usually just means ovulation "
                "came later. Because sperm can survive up to about five days, the fertile window "
                "runs from about five days before ovulation to a day after. Nova can only estimate it."
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
            "question": "What is the luteal phase?",
            "answer": (
                "After ovulation, the body makes more progesterone to keep the lining of the uterus "
                "ready for a possible pregnancy. If there's no pregnancy, estrogen and progesterone "
                "fall, and that drop brings your period. This phase is steadier than the follicular "
                "one, often 12 to 14 days, with 10 to 17 days considered normal. Premenstrual "
                "symptoms, if you get them, tend to show up here."
            ),
        },
    ]),
    ("Common questions", [
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
            "question": "Can an app tell me exactly which phase I'm in or when I ovulate?",
            "answer": (
                "No. Counting days from your period can only estimate it, because the day of "
                "ovulation varies a lot even between people with the same cycle length. Ovulation "
                "test strips give more reliable timing. Treat any app's phase or fertile-window "
                "estimate, including Nova's, as a window rather than an exact day, and never as "
                "birth control."
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
            "question": "What is PMS, and how is it different from PMDD?",
            "answer": (
                "PMS is a group of physical and emotional symptoms, such as bloating, sore breasts, "
                "irritability and tiredness, that show up in the week or two before a period and "
                "ease once it starts. It's common, and how strong it is varies a lot. PMDD is a "
                "much more severe form, with intense low mood, anxiety or irritability that disrupts "
                "daily life, and it's worth talking to a doctor about. If low mood ever comes with "
                "thoughts of harming yourself, reach out for help straight away."
            ),
        },
        {
            "question": "How long should a period last, and how heavy is too heavy?",
            "answer": (
                "Most periods last three to seven days, and a typical total is around two to three "
                "tablespoons of blood, though your normal may differ from someone else's. Signs "
                "that bleeding may be too heavy include soaking through a pad or tampon every hour "
                "or two, passing clots bigger than a large coin, periods lasting more than seven "
                "days, or feeling tired, dizzy or short of breath; these are worth raising with a "
                "doctor. If you're soaking through a pad or tampon every hour for several hours in "
                "a row, or feel faint, seek care promptly."
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
            "question": "How do periods change with age?",
            "answer": (
                "It can take up to three years after the first period for cycles to become regular. "
                "They usually settle in your 20s, and become less predictable again in the years "
                "before menopause, which happens at around age 51 on average. In one large app "
                "study, cycles got slightly shorter with age, by about a fifth of a day per year "
                "between 25 and 45."
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
        {
            "question": "When is it a good idea to contact a doctor?",
            "answer": (
                "Common reasons include: no period by age 16; no period for three months or more "
                "when you aren't pregnant; cycles regularly shorter than 24 or longer than 38 days; "
                "bleeding for more than seven days, or much heavier or lighter than usual; severe "
                "pain; bleeding between periods; or a period that is at least five days late when "
                "you might be pregnant. If you aren't sure, asking is always fine."
            ),
        },
    ]),
]

# Every entry, in page order (sections flattened).
QNA: list[dict[str, str]] = [item for _, items in SECTIONS for item in items]

# Shown under every answer by the page, identically for all entries.
EDUCATION_LABEL = (
    "General education, not personal medical advice. If this sounds like you, "
    "a doctor or gynecologist is the right person to ask."
)
