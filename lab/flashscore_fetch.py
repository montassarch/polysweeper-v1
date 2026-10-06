"""Fetch Flashscore's public day feeds (tennis = sport 2) and save them raw, for lab study of its result timing.

Flashscore's own web page loads these feeds (header x-fsign is the public value the page itself sends).
Read-only, a handful of requests, gzip on. The list feed is cached by Flashscore's CDN for 1-4 minutes,
but each match row carries its own change timestamp (AO), which is what the study uses.
  python3 lab/flashscore_fetch.py [sport_id=2] [first_offset=0] [last_offset=-7]
"""
import gzip, sys, time, urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent / "data" / "raw" / "flashscore"
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/", "Origin": "https://www.flashscore.com",
     "Accept": "*/*", "Accept-Encoding": "gzip"}
BASE = "https://global.flashscore.ninja/2/x/feed/"


def fetch(path, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=H), timeout=40) as r:
                raw = r.read()
                data = gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw
                return data.decode("utf8", "replace"), r.headers.get("Age")
        except Exception as e:                       # noqa: BLE001  (research script: retry then give up)
            time.sleep(2 * (i + 1))
    return None, None


def parse(text):
    """Return a list of match dicts (key÷value pairs split by the feed's separators)."""
    out, league = [], ""
    for rec in text.split("~"):
        d = {}
        for kv in rec.split("¬"):
            if "÷" in kv:
                k, v = kv.split("÷", 1)
                d[k] = v
        if "ZA" in d:
            league = d["ZA"]
        if "AA" in d:
            d["_league"] = league
            d.pop("AL", None)                        # huge bookmaker blob, not needed
            d.pop("MW", None)
            out.append(d)
    return out


if __name__ == "__main__":
    sport = sys.argv[1] if len(sys.argv) > 1 else "2"
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    lo = int(sys.argv[3]) if len(sys.argv) > 3 else -7
    RAW.mkdir(parents=True, exist_ok=True)
    for off in range(hi, lo - 1, -1):
        text, age = fetch(f"f_{sport}_{off}_1_en_1")
        if text is None:
            print(off, "failed"); continue
        ms = parse(text)
        fin = sum(1 for m in ms if m.get("AB") == "3")
        (RAW / f"sport{sport}_off{off}_{int(time.time())}.txt").write_text(text, encoding="utf8")
        print(f"offset {off}: {len(text)} chars, {len(ms)} matches, {fin} finished, cdn age {age}")
        time.sleep(1.0)
