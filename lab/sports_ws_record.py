"""Record Polymarket's Sports WebSocket (free, no login) to measure how early it reports results.

Every message is saved with the local receive time to lab/data/raw/sports_ws/<UTC date>.jsonl.
Compare later with shadow mode's end-window records (same PC clock): lab/sports_ws_lag.py.
Run: py -3 lab/sports_ws_record.py [hours]   (default 6). Reconnects on its own. Measuring only.
"""
import datetime, json, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from polysweeper.livefeed import connect, frame, parse  # noqa: E402

URL = "wss://sports-api.polymarket.com/ws"
OUT = os.path.join(os.path.dirname(__file__), "data", "raw", "sports_ws")


def write(rec):
    os.makedirs(OUT, exist_ok=True)
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(OUT, day + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def run(seconds):
    stop, backoff = time.time() + seconds, 2
    while time.time() < stop:
        try:
            sock, buf = connect(URL)
            buf = bytearray(buf)
            sock.settimeout(30)
            write({"t": time.time(), "note": "connected"})
            backoff, parts = 2, b""
            while time.time() < stop:
                got = parse(buf)
                if got is None:
                    chunk = sock.recv(65536)
                    if not chunk:
                        raise ConnectionError("closed by server")
                    buf += chunk
                    continue
                fin, op, payload, used = got
                del buf[:used]
                if op == 9:
                    sock.sendall(frame(10, payload))
                    continue
                if op == 8:
                    raise ConnectionError("close frame")
                if op in (0, 1, 2):
                    parts += payload
                    if not fin:
                        continue
                    text, parts = parts.decode("utf-8", "replace"), b""
                    if text.strip().lower() == "ping":
                        sock.sendall(frame(1, b"pong"))
                        continue
                    now = time.time()
                    try:
                        msg = json.loads(text)
                    except ValueError:
                        write({"t": now, "raw": text[:500]})
                        continue
                    for m in msg if isinstance(msg, list) else [msg]:
                        write({"t": now, "m": m})
        except Exception as e:  # keep recording whatever happens
            write({"t": time.time(), "note": f"error {type(e).__name__}: {str(e)[:120]}"})
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run(float(sys.argv[1] if len(sys.argv) > 1 else 6) * 3600)
