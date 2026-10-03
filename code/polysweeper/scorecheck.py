"""Check 2: Polymarket's own score must agree with the team we buy.

Polymarket event data carries a 'score' field:
  esports  '000-000|2-1|Bo3'   -> maps won by team 1 and team 2, best of 3
  tennis   '6-3, 5-7, 6-2'     -> games per set, player 1 first
Team 1 / team 2 follow the order of the event title ("A vs B").
"""
import re

ESPORTS = {"cs2", "lol", "dota2", "val", "codmw", "r6siege", "ow", "mlbb", "hok", "sc2", "pubg", "lol-wild-rift"}
TENNIS = {"atp", "wta", "itf"}


def sport_of(league):
    return "esports" if league in ESPORTS else "tennis" if league in TENNIS else None

TIEBREAK = re.compile(r"\(.*?\)")


def title_teams(title):
    """'Counter-Strike: A vs B (BO3) - League' -> ('A', 'B'); 'City: A vs B' -> ('A', 'B')."""
    t = title.split(": ", 1)[1] if ": " in title else title
    t = re.split(r" \(BO\d\)| - ", t)[0]
    parts = re.split(r" vs\.? ", t)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else None


def esports_score(score):
    """-> (maps1, maps2, best_of) or None."""
    m = re.fullmatch(r"[^|]*\|(\d+)-(\d+)\|Bo(\d+)", score or "")
    return tuple(int(x) for x in m.groups()) if m else None


def tennis_score(score):
    """-> (sets1, sets2, sets_played) or None. Unfinished last set is not counted."""
    if not score or "|" in score:
        return None
    s1 = s2 = 0
    for part in score.split(","):
        part = TIEBREAK.sub("", part).strip()
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        if (a >= 6 or b >= 6) and abs(a - b) >= 2 or (a, b) in ((7, 6), (6, 7)):
            if a > b: s1 += 1
            else: s2 += 1
    return s1, s2, s1 + s2


def score_winner(event, sport):
    """Index (0/1) in TITLE order of the side the score says has WON, or None if not decided."""
    score = event.get("score")
    if sport == "esports":
        r = esports_score(score)
        if not r:
            return None
        a, b, bo = r
        need = bo // 2 + 1
    elif sport == "tennis":
        r = tennis_score(score)
        if not r:
            return None
        a, b, _ = r
        need = 2          # best of 3; best-of-5 needs 3 and a 2-x lead is not final
        if a + b >= 4 or max(a, b) > 3:
            need = 3
    else:
        return None
    if a >= need and a > b: return 0
    if b >= need and b > a: return 1
    return None


def winner_outcome(event, outcomes, sport):
    """Index into OUTCOMES of the side the score says won, or None (unknown / names don't match)."""
    w = score_winner(event, sport)
    teams = title_teams(event.get("title", ""))
    if w is None or not teams:
        return None
    name = teams[w].lower()
    hits = [i for i, o in enumerate(outcomes) if o.strip().lower() == name]
    return hits[0] if len(hits) == 1 else None


def allows(event, outcomes, idx, sport):
    """Check 2 verdict for buying outcome idx:
       'agree'    score says this side won
       'against'  score says the OTHER side won -> never buy
       'unknown'  no usable score (not decided, missing, names don't match)"""
    w = winner_outcome(event, outcomes, sport)
    if w is None:
        return "unknown"
    return "agree" if w == idx else "against"
