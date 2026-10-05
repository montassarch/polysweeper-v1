"""Phone alerts through the free ntfy app (ntfy.sh). The owner's phone subscribes to the topic in
config.json ("ntfy_topic"); empty topic = alerts off. Never raises: an alert must never stop shadow
mode. Rate limit: one alert per kind per hour (state in data/shadow/alerts_state.json, not synced)."""
import json
import os
import time
import urllib.request
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
STATE = CODE / "data" / "shadow" / "alerts_state.json"
EVERY = 3600


def topic():
    if os.environ.get("POLYSWEEPER_NO_ALERTS"):      # set by the tests: never alert the owner's phone
        return ""
    try:
        return str(json.loads((CODE / "config.json").read_text()).get("ntfy_topic") or "").strip()
    except Exception:
        return ""


def send(kind, message, title="PolySweeper", priority="default", every=EVERY, now=None, post=None):
    """Send MESSAGE unless an alert of the same KIND went out in the last EVERY seconds.
    Returns True if sent. POST is for tests."""
    try:
        now = time.time() if now is None else now
        t = topic()
        if not t:
            return False
        try:
            state = json.loads(STATE.read_text())
        except Exception:
            state = {}
        if kind in state and now - state[kind] < every:
            return False
        (post or _post)(t, message, title, priority)
        state[kind] = now
        state = {k: v for k, v in state.items() if now - v < 7 * 86400}
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state))
        return True
    except Exception:
        return False


def _post(t, message, title, priority):
    req = urllib.request.Request(f"https://ntfy.sh/{t}", data=message.encode("utf-8"), method="POST",
                                 headers={"Title": title, "Priority": priority, "User-Agent": "polysweeper"})
    urllib.request.urlopen(req, timeout=10).read()


if __name__ == "__main__":                 # python -m polysweeper.alerts  -> test message
    print("sent" if send("test", "PolySweeper alerts are working", every=0) else "not sent (no topic or no network)")
