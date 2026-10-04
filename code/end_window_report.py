"""Summarise the end-window study from data/shadow/events.jsonl (type "end_window")."""
import json, statistics, collections
from pathlib import Path

# Rows written before this time came from the first version, which also recorded matches that
# were already over when first seen and 50/50 cancellations. They are left out. (Later rows never
# include a cancellation: no clear winner means nothing is sampled and no row is written.)
STUDY_START = "2026-10-03T14:12"


def watched(r):
    """Seconds the match was watched after the result (older rows only have seconds_observed)."""
    return r.get("seconds_watched") or r.get("seconds_observed") or 0


def usable(rows):
    """Rows from the fixed version, one per match: the longest watch (a restart can cut the first
    watch short and the match is then watched again; ties keep the first row)."""
    best = {}
    for r in rows:
        if r.get("ts", "") < STUDY_START:
            continue
        m = r["market_id"]
        if m not in best or watched(r) > watched(best[m]):
            best[m] = r
    return list(best.values())


def main(path="data/shadow/events.jsonl"):
    all_rows = [json.loads(l) for l in Path(path).open() if '"end_window"' in l]
    rows = usable(all_rows)
    cut = sum(1 for r in rows if r["closed_because"] == "shadow mode stopped")
    print(f"{len(rows)} matches observed after being decided / ended "
          f"({len(all_rows) - len(rows)} rows left out: written before {STUDY_START}, or repeats)")
    print(f"{cut} of them were cut short because shadow mode restarted\n")
    by = collections.defaultdict(list)
    for r in rows:
        by[r["league"]].append(r)
    def med(x, digits=1):
        return "-" if not x else round(statistics.median(x), digits)
    print(f"{'league':10} {'n':>4} {'start ask':>9} {'with 0.96-0.995 for sale':>24} {'with 0.995-0.999':>16} {'s to 0.999':>10} {'decided->ended s':>16}")
    for lg, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        v1 = sum(1 for r in rs if r["max_shares_096_0995"] >= 5)
        late = sum(1 for r in rs if r["max_shares_0995_0999"] >= 5)
        print(f"{lg:10} {len(rs):4} {med([r['ask_at_start'] for r in rs if r['ask_at_start']], 3):>9} "
              f"{v1:>18} ({100*v1//len(rs)}%) {late:>10} ({100*late//len(rs)}%) "
              f"{med([r['seconds_until_ask_0999'] for r in rs if r['seconds_until_ask_0999'] is not None]):>10} "
              f"{med([r['decided_before_ended_by_s'] for r in rs if r['decided_before_ended_by_s'] is not None]):>16}")

    live_report(rows)


def live_report(rows):
    """Matches recorded with the live feed: what happened in the seconds around the result."""
    lv = [r for r in rows if "live_samples" in r]
    if not lv:
        return
    def med(x):
        return "-" if not x else round(statistics.median(x), 1)
    n = len(lv)
    after_v1 = sum(1 for r in lv if (r["live_v1_until_s"] or -1) > 0)
    after_late = sum(1 for r in lv if (r["live_late_until_s"] or -1) > 0)
    traded_v1 = [r for r in lv if r["live_trades_v1_after"]]
    traded_late = [r for r in lv if r["live_trades_late_after"]]
    print(f"\nLive feed: {n} matches with every book change and trade (times: seconds after shadow mode saw the result)")
    print(f"  5+ shares still for sale at 0.96-0.995 after we saw the result: {after_v1} of {n}, "
          f"median {med([r['live_v1_seconds_after'] for r in lv if r['live_v1_seconds_after']])} s")
    print(f"  5+ shares still for sale at 0.995-0.999 after we saw the result: {after_late} of {n}, "
          f"median {med([r['live_late_seconds_after'] for r in lv if r['live_late_seconds_after']])} s")
    print(f"  last moment 5+ shares were for sale at 0.96-0.995: median "
          f"{med([r['live_v1_until_s'] for r in lv if r['live_v1_until_s'] is not None])} s (negative = gone before we saw it)")
    print(f"  others bought at 0.96-0.995 after we saw the result: {len(traded_v1)} matches, "
          f"{sum(r['live_trades_v1_shares_after'] for r in traded_v1):g} shares")
    print(f"  others bought at 0.995-0.999 after we saw the result: {len(traded_late)} matches, "
          f"{sum(r['live_trades_late_shares_after'] for r in traded_late):g} shares")
    print(f"  winner's best bid reached 0.99: median {med([r['live_bid099_at_s'] for r in lv if r['live_bid099_at_s'] is not None])} s")


if __name__ == "__main__":
    main()
