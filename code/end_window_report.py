"""Summarise the end-window study from data/shadow/events.jsonl (type "end_window")."""
import json, statistics, collections
from pathlib import Path

# Rows written before this time came from the first version, which also recorded matches that
# were already over when first seen and 50/50 cancellations. They are left out. (Later rows never
# include a cancellation: no clear winner means nothing is sampled and no row is written.)
STUDY_START = "2026-10-03T14:12"


def usable(rows):
    """Rows from the fixed version, one per match (the first one)."""
    seen, out = set(), []
    for r in rows:
        if r.get("ts", "") < STUDY_START or r["market_id"] in seen:
            continue
        seen.add(r["market_id"])
        out.append(r)
    return out


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


if __name__ == "__main__":
    main()
