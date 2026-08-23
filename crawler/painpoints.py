import math

HIGH_WEIGHT = 2.0
MEDIUM_WEIGHT = 1.0

HIGH_KEYWORDS = [
    "struggling", "struggle with", "frustrated", "frustrating", "so stuck",
    "overwhelmed", "burned out", "burnt out", "hate that", "tired of",
    "can't afford", "cant afford", "cannot afford", "too expensive",
    "wasting money", "wasting time", "waste of money", "waste of time",
    "no idea how", "don't know how", "dont know how", "have no clue",
    "advice needed", "need advice", "need help", "please help",
    "any tips", "any advice", "wish there was", "wish there were",
    "is there a tool", "is there an app", "is there a way",
    "looking for a solution", "looking for alternatives",
    "giving up", "about to quit", "want to quit", "losing my mind",
    "driving me crazy", "driving me insane", "nightmare",
    "pain point", "biggest challenge", "biggest problem", "biggest struggle",
    "keeps failing", "always failing", "ruining my", "killing me",
    "how do you deal", "how do i deal", "how to deal with", "how do you cope",
]

MEDIUM_KEYWORDS = [
    "difficult", "difficulty", "hard to", "annoying", "annoyed",
    "confused", "confusing", "worried", "worry about", "anxious",
    "anxiety", "stress", "stressed", "stressful", "exhausted",
    "expensive", "pricey", "slow", "complicated", "tedious",
    "manual process", "manually", "not working", "doesn't work",
    "doesnt work", "didn't work", "broke down", "broken",
    "failed", "failure", "feeling lost", "stuck at", "stuck on",
    "problem with", "issue with", "trouble with", "trouble finding",
    "alternative to", "recommendation for", "recommendations for",
    "how can i", "how do i", "what should i do", "why can't i",
    "why does my", "best way to", "anyone else", "am i the only one",
]


def analyze_text(text):
    if not text:
        return 0.0, []
    t = text.lower()
    matched = []
    score = 0.0
    for kw in HIGH_KEYWORDS:
        if kw in t:
            matched.append(kw)
            score += HIGH_WEIGHT
    for kw in MEDIUM_KEYWORDS:
        if kw not in matched and kw in t:
            matched.append(kw)
            score += MEDIUM_WEIGHT
    return round(score, 2), matched


def engagement_boost(num_comments, ups):
    return math.log10(max(ups or 0, 1)) + math.log10(max(num_comments or 0, 1))


def final_score(raw_score, num_comments, ups):
    if raw_score <= 0:
        return 0.0
    return round(raw_score * (1 + 0.15 * engagement_boost(num_comments, ups)), 2)
