"""Score-source atlas (read-only): every Polymarket sports/esports league, its resolution source, and whether
that source can be read by a program.

Step 1 (leagues): Gamma /sports -> for each league's series, open events: how many, how many start within
  -1..+7 days, total volume. Tells us which of the 475 leagues matter.
Step 2 (sources): for each unique resolution URL: HTTP status, time, size, blocked (Cloudflare/403), and hints
  of machine-readable data in the page (__NEXT_DATA__, JSON-LD, embedded JSON, api/feed URLs).
Output: lab/results/source-atlas-leagues.json, lab/results/source-atlas-sources.json
  py lab/source_atlas.py [leagues|sources|all]
"""
import json, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

RES = ROOT / "lab/results"
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/128.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}


def league_row(lg):
    now, evs, off = time.time(), [], 0
    for sid in str(lg.get("series") or "").split(","):
        if not sid.strip():
            continue
        off = 0
        while off < 1000:
            page = get_json(f"{GAMMA}/events?series_id={sid.strip()}&active=true&closed=false&limit=100&offset={off}") or []
            evs += page
            if len(page) < 100:
                break
            off += 100
    soon = [e for e in evs if -86400 <= (parse_ts(e.get("startTime")) or 0) - now <= 7 * 86400]
    return {"sport": lg["sport"], "name": lg.get("name"), "series": lg.get("series"), "tags": lg.get("tags"),
            "resolution": lg.get("resolution"), "open_events": len(evs), "next_7d": len(soon),
            "volume_7d": round(sum(float(e.get("volume") or 0) for e in soon)),
            "example": soon[0]["title"] if soon else (evs[0]["title"] if evs else None)}


def leagues():
    sports = get_json(f"{GAMMA}/sports") or []
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(league_row, sports))
    rows.sort(key=lambda r: (-r["next_7d"], -r["open_events"]))
    (RES / "source-atlas-leagues.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print("leagues", len(rows), "with matches in next 7 days:", sum(1 for r in rows if r["next_7d"]))
    return rows


HINTS = {
    "next_data": r'id="__NEXT_DATA__"', "nuxt": r"__NUXT__|window\.__NUXT", "json_ld": r"application/ld\+json",
    "initial_state": r"__INITIAL_STATE__|__PRELOADED_STATE__|__APOLLO_STATE__",
    "api_url": r"https?://[a-z0-9.-]*(?:api|feed|data|stats|live)[a-z0-9.-]*\.[a-z]{2,}[^\"' ]{0,80}",
    "score_word": r"(?i)\b(score|result|fixture|livescore|match-?centre|full.?time)\b",
}


def probe(url):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=BROWSER)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(3_000_000).decode("utf-8", "replace")
            code, ctype, final = r.status, r.headers.get("Content-Type", ""), r.geturl()
    except urllib.error.HTTPError as e:
        body = e.read(200_000).decode("utf-8", "replace") if e.fp else ""
        code, ctype, final = e.code, e.headers.get("Content-Type", ""), url
    except Exception as e:  # noqa: BLE001
        return {"url": url, "status": "error", "error": str(e)[:120], "secs": round(time.time() - t0, 1)}
    blocked = code in (401, 403, 429, 503) or "cf-chl" in body or "Just a moment..." in body or "captcha" in body.lower()[:5000]
    hints = {k: len(re.findall(p, body)) for k, p in HINTS.items()}
    apis = sorted(set(m.split("?")[0] for m in re.findall(HINTS["api_url"], body)))[:8]
    return {"url": url, "final": final, "status": code, "secs": round(time.time() - t0, 1), "bytes": len(body),
            "ctype": ctype.split(";")[0], "blocked": blocked, "hints": {k: v for k, v in hints.items() if k != "api_url"},
            "api_urls": apis}


def sources():
    lg = json.loads((RES / "source-atlas-leagues.json").read_text(encoding="utf-8"))
    urls = sorted({r["resolution"] for r in lg if r.get("resolution")})
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(probe, urls))
    users = {}
    for r in lg:
        users.setdefault(r.get("resolution"), []).append(r["sport"])
    for r in rows:
        r["leagues"] = users.get(r["url"], [])
        r["domain"] = urlparse(r["url"]).netloc.replace("www.", "")
    (RES / "source-atlas-sources.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for r in rows if r.get("status") == 200 and not r.get("blocked"))
    print("sources", len(rows), "open (200, not blocked):", ok)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("leagues", "all"):
        leagues()
    if what in ("sources", "all"):
        sources()
