"""Summarise the end-window study from data/shadow/events.jsonl (type "end_window")."""
import json, statistics, collections
from pathlib import Path

rows = [json.loads(l) for l in Path("data/shadow/events.jsonl").open() if '"end_window"' in l]
print(f"{len(rows)} matches observed after being decided / ended\n")
by = collections.defaultdict(list)
for r in rows:
    by[r["league"]].append(r)
med = lambda x: round(statistics.median(x), 1) if x else None
print(f"{'league':10} {'n':>4} {'start ask':>9} {'with 0.96-0.995 for sale':>24} {'with 0.995-0.999':>16} {'s to 0.999':>10} {'decided->ended s':>16}")
for lg, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    v1 = sum(1 for r in rs if r["max_shares_096_0995"] >= 5)
    late = sum(1 for r in rs if r["max_shares_0995_0999"] >= 5)
    print(f"{lg:10} {len(rs):4} {med([r['ask_at_start'] for r in rs if r['ask_at_start']]) or '-':>9} "
          f"{v1:>18} ({100*v1//len(rs)}%) {late:>10} ({100*late//len(rs)}%) "
          f"{med([r['seconds_until_ask_0999'] for r in rs if r['seconds_until_ask_0999'] is not None]) or '-':>10} "
          f"{med([r['decided_before_ended_by_s'] for r in rs if r['decided_before_ended_by_s'] is not None]) or '-':>16}")
