"""Live probe: how fresh is Flashscore's per-match feed, and what does its change stamp (DD / AO) mean?

Every ~INTERVAL s: refresh the live list (cached 1-4 min, only to discover live match ids), then fetch the small per-match
feed dc_1_<id> for each live tennis / esports match and log any change (status DA, stage DB, change stamp DD, set scores).
At the end, the log shows for each finished match: our first sight of 'finished' (wall clock) and Flashscore's own stamp DD.
Compare later with the Polymarket Sports WebSocket recording (lab/sports_ws_record.py) taken at the same time.
  python3 lab/flashscore_live_probe.py [minutes=90] [interval=8]
Read-only; about 3 small requests per second. Writes lab/data/raw/flashscore_live/<date>.jsonl
"""
import gzip, json, os, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flashscore_fetch import parse, H, BASE  # noqa: E402

OUT = Path(__file__).resolve().parent / "data/raw/flashscore_live"
OUT.mkdir(parents=True, exist_ok=True)
SPORTS = {"2": "tennis", "36": "esports"}


def get(path):
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=H), timeout=20) as r:
            raw = r.read()
            data = gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw
            return data.decode("utf8", "replace"), r.headers.get("Age")
    except Exception:  # noqa: BLE001
        return None, None


def dc(text):
    d = {}
    for kv in (text or "").split("¬"):
        if "÷" in kv:
            k, v = kv.split("÷", 1)
            d.setdefault(k, v)
    return d


minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 90
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 8
stop = time.time() + minutes * 60
names, last, live, nextlist = {}, {}, {}, 0
f = open(OUT / (time.strftime("%Y-%m-%d_%H%M", time.gmtime()) + ".jsonl"), "a", encoding="utf8")
while time.time() < stop:
    t = time.time()
    if t >= nextlist:
        for sid in SPORTS:
            text, _ = get(f"f_{sid}_0_1_en_1")
            if text:
                for m in parse(text):
                    if m.get("AB") == "2":
                        live[m["AA"]] = sid
                    names[m["AA"]] = f"{m.get('AE')} vs {m.get('AF')} | {m.get('_league','')[:40]}"
        nextlist = t + 30
    for mid in list(live):
        text, age = get(f"dc_1_{mid}")
        now = time.time()
        if not text:
            continue
        d = dc(text)
        state = (d.get("DA"), d.get("DB"), d.get("DD"), d.get("DE"), d.get("DF"), d.get("DN"), d.get("DO"))
        if last.get(mid) != state:
            f.write(json.dumps({"t": now, "id": mid, "name": names.get(mid), "sport": SPORTS[live[mid]], "DA": d.get("DA"), "DB": d.get("DB"), "DD": d.get("DD"),
                                "sets": [d.get("DE"), d.get("DF")], "g": [d.get("DN"), d.get("DO")], "age": age}) + "\n")
            f.flush()
            last[mid] = state
        if d.get("DA") == "3":                       # finished: stop polling it
            live.pop(mid, None)
    time.sleep(max(0.0, interval - (time.time() - t)))
f.write(json.dumps({"t": time.time(), "note": "done"}) + "\n")
