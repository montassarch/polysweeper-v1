"""Turn the laptop's feed-race recordings (lab/data/raw/feeds_end_race/*.jsonl, made by lab/feeds_end_race.py) into join times for the
decided-state price-priority test, then replay them against the real public tape:

  python3 lab/feeds_to_joins.py [delay_s=30] [series filter, default atp,wta] > lab/data/raw/joins.jsonl
  LEAGUE=tennis python3 lab/tennis_decided_bids.py replay lab/data/raw/joins.jsonl

For every recorded match the bot is assumed to place its 5-share bid `delay_s` seconds after the FIRST source (365Scores or LiveScore) said
"match over", only if the sources that reported agree with Polymarket's final score (agree flags). The replay reports, for bids at 0.99 /
0.992 / 0.995 / 0.998, whether public taker sells printed at or below the bid before Polymarket's finished stamp (price priority, nobody bids
above us) and whether the filled side won. Read-only; no orders."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
delay = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
want = (sys.argv[2] if len(sys.argv) > 2 else "atp,wta").split(",")
n = skipped = 0
for f in sorted((ROOT / "lab/data/raw/feeds_end_race").glob("*.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        ser = (r.get("series") or "").lower()
        if not any(w in ser for w in want):
            continue
        ts = [t for t, ok in ((r.get("t_365"), r.get("agree_365")), (r.get("t_ls"), r.get("agree_ls"))) if t and ok is not False]
        if not ts:
            skipped += 1
            continue
        print(json.dumps({"event": r["event"], "title": r.get("title"), "join_ts": int(min(ts) + delay),
                          "lead_s": r.get("lead_365_s") or r.get("lead_ls_s")}))
        n += 1
print(f"# {n} joins, {skipped} skipped (no agreeing source)", file=sys.stderr)
