"""List end_window watches with >=5 shares at 0.96-0.995 after the result, per-sport counts."""
import json, glob, collections, sys
sys.path.insert(0, "/home/user/polysweeper-v1/code")
from polysweeper.scorecheck import sport_of
D = "/home/user/polysweeper-v1/code/data/shadow/"
ew = [json.loads(l) for l in open(D + "events.jsonl") if '"end_window"' in l]
ew = [r for r in ew if r.get("type") == "end_window"]
live = {}
for f in sorted(glob.glob(D + "daily/*.jsonl")):
    for l in open(f):
        if '"end_window_live"' in l:
            r = json.loads(l); live[r["market_id"]] = r
by = collections.defaultdict(lambda: [0, 0, 0])
hits = []
for r in ew:
    sp = sport_of(r["league"]) or r["league"]
    cut = r.get("closed_because") == "shadow mode stopped" and (r.get("seconds_watched") or 0) < 60
    by[sp][0] += 1
    if r["max_shares_096_0995"] >= 5:
        by[sp][1] += 1; hits.append(r)
    if r.get("live_samples"):
        by[sp][2] += 1
print("sport watches hits(ew) with_live")
for k, v in sorted(by.items(), key=lambda x: -x[1][0]): print(k, v)
for r in hits:
    print(r["market_id"], r["league"], r["title"][:60], "trig", r["first_trigger"], "dec", r["decided_at"], "end", r["ended_at"],
          "win", r["winner_idx"], "score", r["score_at_start"], "sh", r["max_shares_096_0995"], r["closed_because"], r.get("seconds_watched"))
    print("   samples:", [s for s in r["samples"] if s[3] >= 5][:6], "n", len(r["samples"]), "first", r["samples"][:3])
print("LIVE detail hits")
for m, r in live.items():
    h = [s for s in r["samples"] if s[0] >= 0 and s[3] >= 5]
    if h:
        print(m, r["league"], r["title"][:55], "winner", r["winner"], "first>=5 at", h[0][0], "rows", len(h), "max", max(s[3] for s in h),
              "trades in band after", [(t[0], t[1], t[2], t[3]) for t in r["trades"] if t[0] >= 0 and 0.96 <= t[1] <= 0.995][:5])
print("live count", len(live))
