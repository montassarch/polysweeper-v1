"""Row 4 long-history backtest (read-only, public APIs only): do resting bids at 0.98+ in US games ever fill on the LOSER
when they are gated by a rule that can be read LIVE (game clock, lead, inning)?  Extends the 32-day study of 2026-10-08
(lab/late_bids_moneyline.py, lab/row4_clock.py) to as many past games as Gamma lists.

Stages (each resumable, raw files are git-ignored under lab/data/raw/row4h/):
  python3 lab/usports_events.py 400            # event list (moneyline market id, finished stamp, final score)
  python3 lab/row4_history.py tape             # public taker trades of each game in [stamp-30min, stamp+15min], price >= 0.9
  python3 lab/row4_history.py espn             # ESPN play-by-play (wallclock, period, clock, score, extras) for games with fills
  python3 lab/row4_history.py join             # one row per bid-side fill (taker SELL at 0.95+) with the game state -> fills file
The rule tests are in lab/row4_rules.py.
A "fill" = a taker SELL into a resting buy bid (what our resting buy would have competed for). Queue position is NOT modelled here.
"""
import bisect, collections, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

DATA = "https://data-api.polymarket.com"
BASE = "https://site.api.espn.com/apis/site/v2/sports"
PATH = {"CFB": "football/college-football", "NFL": "football/nfl", "NHL": "hockey/nhl", "WNBA": "basketball/wnba",
        "NBA": "basketball/nba", "MLB": "baseball/mlb"}
RAW = ROOT / "lab/data/raw/row4h"
TAPE, PLAYS = RAW / "tape", RAW / "plays"
for d in (TAPE, PLAYS):
    d.mkdir(parents=True, exist_ok=True)


def load_games():
    ev = json.loads((ROOT / "lab/data/raw/usports_events.json").read_text())
    games = []
    for e in ev:
        if e["slug"] != e["game"] or not e.get("finished") or not e.get("start"):
            continue
        ms = [m for m in e["markets"] if m.get("type") == "moneyline"]
        if len(ms) != 1:
            continue
        try:
            px = [float(x) for x in json.loads(ms[0]["final"])]
        except Exception:
            continue
        void = False
        if sorted(px) != [0.0, 1.0]:
            if not (e.get("score") and abs(px[0] - 0.5) < 0.06 and abs(px[1] - 0.5) < 0.06):
                continue
            void = True                                  # a played game that paid ~50/50 (NFL tie): counts as a loss for the buyer
        games.append({"game": e["game"], "sport": e["sport"], "cid": ms[0]["cid"], "fin": e["finished"], "start": e["start"],
                      "score": e.get("score"), "px": px, "outcomes": ms[0].get("outcomes"), "void": void})
    return games


# ---------------------------------------------------------------- stage 1: tape
def pull_tape(g):
    f = TAPE / f"{g['game']}.json"
    if f.exists():
        return 0
    rows, off, ok = [], 0, False
    while off <= 10000:
        page = get_json(f"{DATA}/trades?market={g['cid']}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            ok = True
            break
        rows += page
        if min(t["timestamp"] for t in page) < g["fin"] - 1800 - 600 or len(page) < 500:
            ok = True
            break
        off += 500
    keep = [[t["timestamp"], t["side"], float(t["price"]), float(t["size"]), t["outcomeIndex"], (t.get("proxyWallet") or "")[:10]]
            for t in rows if g["fin"] - 1800 <= t["timestamp"] <= g["fin"] + 900 and float(t["price"]) >= 0.9]
    f.write_text(json.dumps({"ok": ok, "n_all": len(rows), "trades": keep}))
    return len(rows)


def stage_tape():
    games = load_games()
    print("games with one resolved moneyline + stamp:", len(games), dict(collections.Counter(g["sport"] for g in games)), flush=True)
    todo = [g for g in games if not (TAPE / f"{g['game']}.json").exists()]
    print("tape to pull:", len(todo), flush=True)
    n = 0
    with ThreadPoolExecutor(6) as pool:
        for _ in pool.map(pull_tape, todo):
            n += 1
            if n % 200 == 0:
                print("tape", n, "of", len(todo), time.strftime("%H:%M:%S"), flush=True)
    print("tape done", flush=True)


# ---------------------------------------------------------------- stage 2: ESPN
_sb = {}


def scoreboard(sport, date, groups=None):
    k = (sport, date, groups)
    if k not in _sb:
        extra = f"&groups={groups}" if groups else ""
        s = get_json(f"{BASE}/{PATH[sport]}/scoreboard?dates={date}&limit=400{extra}") or {}
        _sb[k] = s.get("events", [])
    return _sb[k]


def clock_s(c):
    c = (c or {}).get("displayValue") if isinstance(c, dict) else c
    if not c:
        return None
    try:
        if ":" in c:
            m, s = c.split(":")
            return int(m) * 60 + float(s)
        return float(c)
    except ValueError:
        return None


def compact_plays(sport, s):
    plays = list(s.get("plays") or [])
    if not plays:
        for d in (s.get("drives", {}).get("previous") or []):
            plays += d.get("plays", [])
        cur = s.get("drives", {}).get("current")
        if cur:
            plays += cur.get("plays", [])
    if sport == "MLB":
        return compact_mlb(plays)
    out = []
    for p in plays:
        if not p.get("wallclock"):
            continue
        try:
            ts = datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        per = (p.get("period") or {}).get("number")
        hs, as_ = p.get("homeScore"), p.get("awayScore")
        txt = (p.get("text") or "").lower()
        if sport in ("CFB", "NFL"):
            st = p.get("start") or {}
            ex = [(st.get("team") or {}).get("id"), st.get("down"), st.get("distance"), st.get("yardsToEndzone"),
                  1 if "kneel" in txt else 0, 1 if "timeout" in txt else 0, 1 if p.get("scoringPlay") else 0]
        elif sport == "NHL":
            ex = [((p.get("strength") or {}).get("abbreviation") or ""), (p.get("team") or {}).get("id"), 1 if p.get("scoringPlay") else 0]
        else:
            ex = [(p.get("team") or {}).get("id"), 1 if p.get("scoringPlay") else 0]
        out.append([ts, per, clock_s(p.get("clock")), hs, as_] + ex)
    out.sort(key=lambda x: x[0])
    return out


def compact_mlb(plays):
    """MLB: keep the raw rows ([ts, atBatId, type text, half, inning, outs, home, away, scoring]); the state is built at join time
    (mlb_states). Reason: ESPN stamps every row of a plate appearance with the score and outs AFTER the appearance (a read at the first
    pitch would leak the result) and some rows (wild pitch, 'End Inning', substitutions) carry wrong outs."""
    out = []
    for p in plays:
        if not p.get("wallclock"):
            continue
        try:
            ts = datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        per = p.get("period") or {}
        out.append([ts, p.get("atBatId"), (p.get("type") or {}).get("text"), per.get("type"), per.get("number"), p.get("outs"),
                    p.get("homeScore"), p.get("awayScore"), 1 if p.get("scoringPlay") else 0])
    out.sort(key=lambda x: x[0])
    return out


def mlb_states(rows):
    """state after each plate appearance, valid from the appearance's END row: [ts, inning, None, home, away, top, outs, scoring]"""
    by = {}
    for r in rows:
        ab = r[1]
        if ab is None or r[3] not in ("Top", "Bottom"):
            continue
        e = by.setdefault(ab, {"end": None, "res": None})
        if r[2] == "End Batter/Pitcher":
            if e["end"] is None or r[0] >= e["end"][0]:
                e["end"] = r
        elif r[2] == "Play Result":
            if e["res"] is None or r[0] >= e["res"][0]:
                e["res"] = r
    states = []
    for e in by.values():
        r = e["end"] or e["res"]
        if r is not None and r[4] is not None:
            states.append([r[0], r[4], None, r[6], r[7], 1 if r[3] == "Top" else 0, r[5], r[8]])
    states.sort(key=lambda x: x[0])
    fixed, prev = [], None
    for st in states:
        if prev and prev[1] == st[1] and prev[5] == st[5] and st[6] is not None and prev[6] is not None and st[6] < prev[6]:
            st = st[:6] + [prev[6]] + st[7:]
        fixed.append(st)
        prev = st
    return fixed


def match_espn(g):
    """-> (espn event dict from the scoreboard) or None; match = same final score, start within 45 min, completed"""
    if not g.get("score"):
        return None
    try:
        a, h = [int(x) for x in g["score"].split("-")]
    except ValueError:
        return None
    d0 = datetime.fromtimestamp(g["start"], timezone.utc)
    groups = (None,) if g["sport"] != "CFB" else ("80", "81")
    for dd in (d0, d0 - timedelta(days=1), d0 + timedelta(days=1)):
        for grp in groups:
            for x in scoreboard(g["sport"], dd.strftime("%Y%m%d"), grp):
                comp = x["competitions"][0]
                cs = {c["homeAway"]: c for c in comp["competitors"]}
                try:
                    sa, sh = int(cs["away"]["score"]), int(cs["home"]["score"])
                except (KeyError, ValueError):
                    continue
                gt = datetime.fromisoformat(x["date"].replace("Z", "+00:00")).timestamp()
                if (sa, sh) == (a, h) and abs(gt - g["start"]) < 2700 and x["status"]["type"]["completed"]:
                    return x, cs
    return None


def pull_plays(g):
    f = PLAYS / f"{g['game']}.json"
    if f.exists():
        return 0
    m = match_espn(g)
    if not m:
        f.write_text(json.dumps({"espn": None}))
        return 0
    x, cs = m
    s = get_json(f"{BASE}/{PATH[g['sport']]}/summary?event={x['id']}") or {}
    pl = compact_plays(g["sport"], s)
    f.write_text(json.dumps({"espn": x["id"], "home_id": cs["home"]["team"]["id"], "away_id": cs["away"]["team"]["id"],
                             "home_name": cs["home"]["team"].get("name"), "away_name": cs["away"]["team"].get("name"),
                             "home_won": int(cs["home"]["score"]) > int(cs["away"]["score"]), "plays": pl}))
    return len(pl)


def has_fill(g):
    f = TAPE / f"{g['game']}.json"
    if not f.exists():
        return False
    d = json.loads(f.read_text())
    return any(t[1] == "SELL" and t[2] >= 0.95 and t[0] < g["fin"] for t in d["trades"])


def stage_espn():
    only = {x for x in os.environ.get("ESPN_SPORTS", "").split(",") if x}
    games = [g for g in load_games() if has_fill(g) and (not only or g["sport"] in only)]
    todo = [g for g in games if not (PLAYS / f"{g['game']}.json").exists()]
    print("games with a fill:", len(games), "ESPN to pull:", len(todo), flush=True)
    n = 0
    with ThreadPoolExecutor(int(os.environ.get("ESPN_THREADS", 4))) as pool:
        for _ in pool.map(pull_plays, todo):
            n += 1
            if n % 200 == 0:
                print("espn", n, "of", len(todo), time.strftime("%H:%M:%S"), flush=True)
    ok = sum(1 for g in games if (PLAYS / f"{g['game']}.json").exists() and json.loads((PLAYS / f"{g['game']}.json").read_text()).get("espn"))
    print("espn done; matched", ok, "of", len(games), flush=True)


# ---------------------------------------------------------------- stage 3: join
REG = {"CFB": 4, "NFL": 4, "NHL": 3, "WNBA": 4, "NBA": 4, "MLB": 9}


def stage_join():
    games = load_games()
    rows, per_game = [], {}
    for g in games:
        f = TAPE / f"{g['game']}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        fills = [t for t in d["trades"] if t[1] == "SELL" and t[2] >= 0.95 and t[0] < g["fin"]]
        if not fills:
            continue
        pf = PLAYS / f"{g['game']}.json"
        pj = json.loads(pf.read_text()) if pf.exists() else {"espn": None}
        pl = pj.get("plays") or []
        endt = pl[-1][0] if pl else None
        if g["sport"] == "MLB" and pl:
            pl = mlb_states(pl)
        ts_list = [p[0] for p in pl]
        per_game[g["game"]] = {"sport": g["sport"], "fin": g["fin"], "complete": d["ok"], "espn": bool(pj.get("espn")), "endt": endt}
        for t in fills:
            oi = t[4]
            on_loser = int(g["px"][oi] < 0.99)                 # lost, or a tie/void paying ~0.5
            r = {"sport": g["sport"], "game": g["game"], "day": datetime.fromtimestamp(g["fin"], timezone.utc).strftime("%Y-%m-%d"),
                 "sb": g["fin"] - t[0], "price": t[2], "shares": t[3], "w": t[5], "on_loser": on_loser, "ok": d["ok"],
                 "val": g["px"][oi], "void": int(g["void"])}
            if pl:
                if g["void"]:
                    nm = (g["outcomes"] and json.loads(g["outcomes"])[oi]) or ""
                    if nm and nm == pj.get("home_name"):
                        buyer_home = True
                    elif nm and nm == pj.get("away_name"):
                        buyer_home = False
                    else:
                        rows.append(r)
                        continue
                else:
                    home_won = pj["home_won"]
                    buyer_home = home_won != bool(on_loser)   # side the buyer held: winner unless the fill is on the loser
                r.update(buyer_home=int(buyer_home), home_id=pj["home_id"], away_id=pj["away_id"], to_end=round(endt - t[0]))
                for delta in (0, 45):                          # state as seen `delta` seconds earlier (ESPN stamps can run early)
                    i = bisect.bisect_right(ts_list, t[0] - delta) - 1
                    if i < 0:
                        continue
                    p = pl[i]
                    hs, as_ = p[3], p[4]
                    if hs is not None and as_ is not None and p[1] is not None:
                        r[f"s{delta}"] = {"period": p[1], "clock": p[2], "lead": (hs - as_) if buyer_home else (as_ - hs), "ex": p[5:]}
            rows.append(r)
    (RAW / "fills.json").write_text(json.dumps({"rows": rows, "games": per_game}))
    print("fills", len(rows), "games with fills", len(per_game), "with a state", sum(1 for r in rows if "s0" in r),
          "games matched to ESPN", sum(1 for v in per_game.values() if v["espn"]), flush=True)


if __name__ == "__main__":
    {"tape": stage_tape, "espn": stage_espn, "join": stage_join}[sys.argv[1]]()
