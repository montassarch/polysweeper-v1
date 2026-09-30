"""Write FAKE test data to data/sample.jsonl (deterministic).

This only exercises the machinery (skips, losses, 50/50, pauses). The win rate
here is invented and means nothing about the real market.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(7)
base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
out = []


def src(name, status="finished", rtype="normal", winner="Team A", end=None, fetched=None):
    return {"source": name, "status": status, "result_type": rtype, "winner": winner,
            "finished_at": end.isoformat() if end else None,
            "fetched_at": fetched.isoformat()}


for i in range(300):
    sport = random.choice(["football", "esports", "tennis"])
    end = base + timedelta(hours=i * 3)
    now = end + timedelta(minutes=random.choice([3, 12, 20, 30]))
    kind = random.random()
    rtype = "normal"
    a_status = b_status = "finished"
    b_winner = "Team A"
    if kind < 0.05:
        rtype = "forfeit"
    elif kind < 0.08:
        b_winner = "Team B"            # sources disagree
    elif kind < 0.10:
        b_status = "live"
    srcs = [src("provider_a", rtype=rtype, end=end, fetched=now, status=a_status),
            src("provider_b", rtype=rtype, end=end, fetched=now, status=b_status, winner=b_winner)]
    settle = "win"
    r = random.random()
    if rtype == "forfeit":
        settle = "split"
    elif r < 0.01:
        settle = "loss"                # rare data/resolution failure
    elif r < 0.02:
        settle = "split"
    out.append({
        "market_id": f"m{i}", "sport": sport, "market_type": random.choice(["moneyline"] * 9 + ["spread"]),
        "outcome_team": "Team A", "ask_price": round(random.uniform(0.95, 0.998), 3),
        "available_size": random.choice([20, 60, 150, 400]), "time": now.isoformat(),
        "mapping_confidence": random.choice([1.0] * 19 + [0.6]),
        "sources": srcs, "settlement": settle,
        "settled_at": (now + timedelta(hours=random.choice([1, 2, 5, 30]))).isoformat(),
        "synthetic": True,
    })

Path("data").mkdir(exist_ok=True)
Path("data/sample.jsonl").write_text("\n".join(json.dumps(r) for r in out) + "\n")
print(f"wrote {len(out)} fake records to data/sample.jsonl")
