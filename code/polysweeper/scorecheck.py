"""Check 2: Polymarket's own score must agree with the team we buy.

Polymarket event data carries a 'score' field:
  esports  '000-000|2-1|Bo3'   -> maps won by team 1 and team 2, best of 3
  tennis   '6-3, 5-7, 6-2'     -> games per set, player 1 first
  US       '30-13'             -> points/runs/goals (mlb, nfl, cfb, nhl, nba); checked on 883 settled
                                  games (2026-10-05): the higher number was the winner every time
Team 1 / team 2 follow the order of the event title ("A vs B").
"""
import re

ESPORTS = {"cs2", "lol", "dota2", "val", "codmw", "r6siege", "ow", "mlbb", "hok", "sc2", "pubg", "lol-wild-rift"}
TENNIS = {"atp", "wta", "itf"}
US = {"mlb", "nfl", "cfb", "nhl", "nba"}


def sport_of(league):
    return ("esports" if league in ESPORTS else "tennis" if league in TENNIS
            else "us" if league in US else None)


def us_score(score):
    """'30-13' -> (30, 13) or None."""
    m = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", score or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


MLB_INNING = re.compile(r"(Top|Mid|Bot|End) (\d+)(?:st|nd|rd|th)")


def mlb_innings_done(period):
    """Full innings completed per the period text: 'End 8th' -> 8, 'Top 9th' -> 8, 'Bot 9th' -> 8.5
    (the home side is batting in the 9th, top half done), None if unknown."""
    m = MLB_INNING.fullmatch((period or "").strip())
    if not m:
        return None
    half, n = m.group(1), int(m.group(2))
    return {"Top": n - 1, "Mid": n - 0.5, "Bot": n - 0.5, "End": n}[half]

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


TITLE_BO = re.compile(r"\bBO(\d+)\b", re.I)


def series_length(event, score_bo):
    """Best-of N for an esports series: the score's BoN and the title's (BOn) must agree.
    Overwatch scores say Bo3 while the title says (BO5): disagreement -> None (unknown)."""
    title_bo = {int(x) for x in TITLE_BO.findall(event.get("title") or "")}
    if len(title_bo) > 1 or (title_bo and score_bo not in title_bo):
        return None
    return score_bo


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
        bo = series_length(event, bo)
        if not bo:
            return None
        need = bo // 2 + 1
    elif sport == "tennis":
        r = tennis_score(score)
        if not r:
            return None
        a, b, _ = r
        need = 2          # best of 3; best-of-5 needs 3 and a 2-x lead is not final
        if a + b >= 4 or max(a, b) > 3:
            need = 3
    elif sport == "us":
        r = us_score(score)
        if not r or event.get("ended") is not True or r[0] == r[1]:
            return None               # a US score only says who WON once the game is flagged ended
        return 0 if r[0] > r[1] else 1
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


def mlb_big_lead(event, outcomes, idx, lead=7, innings=8):
    """MLB rule: outcome idx leads by LEAD+ runs with at least INNINGS full innings played
    (game still on). True / False."""
    r, done = us_score(event.get("score")), mlb_innings_done(event.get("period"))
    teams = title_teams(event.get("title", ""))
    if not r or done is None or done < innings or not teams:
        return False
    a, b = r
    if abs(a - b) < lead:
        return False
    name = teams[0 if a > b else 1].lower()
    hits = [i for i, o in enumerate(outcomes) if o.strip().lower() == name]
    return hits == [idx]


def allows(event, outcomes, idx, sport):
    """Check 2 verdict for buying outcome idx:
       'agree'    score says this side won
       'against'  score says the OTHER side won -> never buy
       'unknown'  no usable score (not decided, missing, names don't match)"""
    w = winner_outcome(event, outcomes, sport)
    if w is None:
        return "unknown"
    return "agree" if w == idx else "against"
