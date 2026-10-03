"""End-window study: what can be bought in the minutes after a match is decided?

For every watched match, starting at the first moment EITHER Polymarket's score shows the
series/match won ("decided") OR Polymarket flags the match as ended, record for 15 minutes
how the winner's order book looks:
  - best ask and best bid
  - shares for sale at 0.96-0.995 (our V1 window) and at 0.995-0.999 (the late band)
One summary line per match goes to events.jsonl (type "end_window"), so it is synced.
Pure observation: never buys anything.
"""
from __future__ import annotations

import time

from .scorecheck import sport_of, winner_outcome

WINDOW_SECONDS = 15 * 60
MAX_SAMPLES = 150


def ask_shares(asks, lo, hi):
    return round(sum(float(a["size"]) for a in asks if lo <= float(a["price"]) <= hi), 2)


class EndWatch:
    def __init__(self, write, say=print):
        self.write = write          # function(record) -> logs one line
        self.say = say
        self.open = {}
        self.done = set()            # never open a second window for the same match
        self.seen_playing = set()    # matches seen BEFORE they were decided (we saw the transition)

    def observe(self, mid, info, ev_state, stats, now):
        e, outs = info["event"], info["outcomes"]
        sport = sport_of(info["league"])
        decided = winner_outcome(e, outs, sport) if sport else None
        ended = ev_state.get("ended") is True
        rec = self.open.get(mid)
        if rec is None:
            if mid in self.done:
                return
            if decided is None and not ended:
                self.seen_playing.add(mid)
                return
            if mid not in self.seen_playing:     # it was already over when we first saw it: timing unknown
                self.done.add(mid)
                return
            rec = self.open[mid] = {"type": "end_window", "market_id": mid, "league": info["league"],
                                    "title": e.get("title"), "outcomes": outs, "t0": now,
                                    "first_trigger": "score_decided" if decided is not None else "ended_flag",
                                    "decided_at": None, "ended_at": None, "winner_idx": None,
                                    "score_at_start": ev_state.get("score"), "samples": []}
        t = round(now - rec["t0"], 1)
        if decided is not None and rec["decided_at"] is None:
            rec["decided_at"] = t
        if ended and rec["ended_at"] is None:
            rec["ended_at"] = t
        if decided is not None:
            rec["winner_idx"] = decided
        idx = rec["winner_idx"]
        if idx is None and stats:                       # no usable score (e.g. football): the side buyers favour
            idx = max(stats, key=lambda i: stats[i][1] if stats[i][1] is not None else -1)
            if (stats[idx][1] or 0) < 0.90:             # no clear winner yet (or a 50/50 cancellation): don't sample
                idx = None
        if idx in stats and len(rec["samples"]) < MAX_SAMPLES:
            best_ask, best_bid, asks, _ = stats[idx]
            s = [t, best_ask, best_bid, ask_shares(asks, 0.96, 0.995), ask_shares(asks, 0.99501, 0.999), idx]
            if not rec["samples"] or rec["samples"][-1][1:] != s[1:]:
                rec["samples"].append(s)
        if now - rec["t0"] >= WINDOW_SECONDS:
            self.close(mid, "15 minutes done", now)

    def close(self, mid, reason, now=None):
        self.done.add(mid)
        rec = self.open.pop(mid, None)
        if not rec or not rec["samples"]:
            return
        smp = rec["samples"]
        hit999 = next((s[0] for s in smp if s[1] is not None and s[1] >= 0.999), None)
        rec.update({
            "closed_because": reason,
            "seconds_observed": smp[-1][0],                     # time of the LAST CHANGE seen in the book
            "seconds_watched": round((time.time() if now is None else now) - rec["t0"], 1),   # how long the window really ran
            "ask_at_start": smp[0][1],
            "lowest_ask_seen": min((s[1] for s in smp if s[1] is not None), default=None),
            "max_shares_096_0995": max(s[3] for s in smp),
            "max_shares_0995_0999": max(s[4] for s in smp),
            "seconds_until_ask_0999": hit999,
            "decided_before_ended_by_s": (rec["ended_at"] - rec["decided_at"])
                                          if rec["ended_at"] is not None and rec["decided_at"] is not None else None,
        })
        self.write(rec)
        self.say(f"end window: {(rec['title'] or '')[:50]} | start ask {rec['ask_at_start']} | "
                 f"shares at 0.96-0.995: {rec['max_shares_096_0995']:g} | at 0.995-0.999: {rec['max_shares_0995_0999']:g} | "
                 f"ask 0.999 after {hit999}s | decided->ended {rec['decided_before_ended_by_s']}s")

    def close_missing(self, current_mids):
        for mid in [m for m in self.open if m not in current_mids]:
            self.close(mid, "market closed or no longer watched")

    def close_all(self):
        for mid in list(self.open):
            self.close(mid, "shadow mode stopped")
