"""Live order books from Polymarket's websocket (market channel). Read-only.

Shadow mode reads order books every 15 seconds. That is too slow to see the first seconds after
a match is decided. This feed keeps the subscribed books up to date in real time (a background
thread) and remembers, for the favourite side of each match (best ask or bid 0.85+), every change
of the top of the book and every trade, for the last 20 minutes. The end-window study uses that
to show the seconds around the result.

Standard library only: a small websocket client (RFC 6455) over ssl.
If the feed cannot connect or a message cannot be read, shadow mode carries on as before.
Nothing here can place an order.
"""
from __future__ import annotations

import base64
import collections
import json
import os
import socket
import ssl
import struct
import threading
import time
import urllib.parse

URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
USER_AGENT = "polysweeper-research/0.1 (read-only data collection)"
PING_SECONDS = 10           # the server expects a "PING" text now and then
RESUBSCRIBE_GAP = 60        # new matches: reconnect with the new list at most once a minute
MAX_TOKENS = 500
KEEP_SECONDS = 20 * 60      # history kept per token
FAVOURITE = 0.85            # only keep history while a side's best ask or bid is at/above this
MAX_HISTORY = 4000
MAX_TRADES = 2000
V1 = (0.96, 0.995)          # our buy band
LATE = (0.99501, 0.999)     # the late band


# -- websocket framing -------------------------------------------------------
def _mask(data: bytes, key: bytes) -> bytes:
    n = len(data)
    k = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(k, "big")).to_bytes(n, "big")


def frame(opcode: int, payload: bytes, mask: bool = True) -> bytes:
    """One final frame. Frames from a client must be masked."""
    n = len(payload)
    bit = 0x80 if mask else 0
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([bit | n])
    elif n < 65536:
        head += bytes([bit | 126]) + struct.pack(">H", n)
    else:
        head += bytes([bit | 127]) + struct.pack(">Q", n)
    if not mask:
        return head + payload
    key = os.urandom(4)
    return head + key + _mask(payload, key)


def parse(buf) -> tuple | None:
    """(fin, opcode, payload, bytes used) for the first complete frame in buf, or None."""
    if len(buf) < 2:
        return None
    b1, b2 = buf[0], buf[1]
    n, i = b2 & 0x7F, 2
    if n == 126:
        if len(buf) < 4:
            return None
        n, i = struct.unpack(">H", bytes(buf[2:4]))[0], 4
    elif n == 127:
        if len(buf) < 10:
            return None
        n, i = struct.unpack(">Q", bytes(buf[2:10]))[0], 10
    key = None
    if b2 & 0x80:
        if len(buf) < i + 4:
            return None
        key, i = bytes(buf[i:i + 4]), i + 4
    if len(buf) < i + n:
        return None
    payload = bytes(buf[i:i + n])
    return bool(b1 & 0x80), b1 & 0x0F, _mask(payload, key) if key else payload, i + n


def _read_head(sock) -> tuple[bytes, bytes]:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk or len(data) > 65536:
            raise ConnectionError("no reply")
        data += chunk
    head, rest = data.split(b"\r\n\r\n", 1)
    return head, rest


def connect(url: str, timeout: float = 15):
    """Open a websocket. Returns (socket, bytes already received after the handshake)."""
    u = urllib.parse.urlparse(url)
    secure = u.scheme == "wss"
    host, port = u.hostname, u.port or (443 if secure else 80)
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")) if secure else None
    if proxy:
        p = urllib.parse.urlparse(proxy)
        sock = socket.create_connection((p.hostname, p.port or 80), timeout)
        sock.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
        line = _read_head(sock)[0].split(b"\r\n")[0]
        if b" 200" not in line:
            sock.close()
            raise ConnectionError(f"proxy refused: {line[:80]!r}")
    else:
        sock = socket.create_connection((host, port), timeout)
    if secure:
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((f"GET {u.path or '/'} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                  f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                  f"User-Agent: {USER_AGENT}\r\n\r\n").encode())
    head, rest = _read_head(sock)
    line = head.split(b"\r\n")[0]
    if b" 101" not in line:
        sock.close()
        raise ConnectionError(f"websocket refused: {line[:80]!r}")
    return sock, rest


# -- order books --------------------------------------------------------------
def _levels(rows) -> dict:
    out = {}
    for r in rows or []:
        try:
            p, s = float(r["price"]), float(r["size"])
        except (KeyError, TypeError, ValueError):
            continue
        if s > 0:
            out[p] = s
    return out


def summary(book) -> tuple:
    """(best ask, best bid, shares for sale at 0.96-0.995, shares for sale at 0.995-0.999)."""
    asks, bids = book["asks"], book["bids"]
    return (min(asks) if asks else None, max(bids) if bids else None,
            round(sum(s for p, s in asks.items() if V1[0] <= p <= V1[1]), 2),
            round(sum(s for p, s in asks.items() if LATE[0] <= p <= LATE[1]), 2))


class LiveFeed:
    def __init__(self, url: str = URL, on_error=None):
        self.url = url
        self.on_error = on_error or (lambda where, exc: None)
        self.lock = threading.Lock()
        self.books = {}                 # token -> {"asks": {price: size}, "bids": {price: size}}
        self.hist = {}                  # token -> deque of (t, best ask, best bid, v1 shares, late shares)
        self.trade_log = {}             # token -> deque of (t, price, size, side)
        self.wanted = frozenset()
        self.subscribed = frozenset()
        self.stats = collections.Counter()
        self.connected = False
        self.last_error = None
        self._stop = threading.Event()
        self._thread = None

    # -- used by shadow mode (main thread) -------------------------------------
    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="live-feed", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    @property
    def started(self):
        return self._thread is not None

    def set_tokens(self, tokens):
        with self.lock:
            self.wanted = frozenset(list(dict.fromkeys(str(t) for t in tokens))[:MAX_TOKENS])

    def top(self, token):
        """(best ask, best bid) from the live book, or None if this token has no live book."""
        with self.lock:
            b = self.books.get(str(token))
            return summary(b)[:2] if b is not None else None

    def history(self, token, t_from, t_to):
        """Changes of the top of the book in [t_from, t_to], starting with the state at t_from."""
        with self.lock:
            rows = list(self.hist.get(str(token), ()))
        before = [r for r in rows if r[0] < t_from]
        return before[-1:] + [r for r in rows if t_from <= r[0] <= t_to]

    def trades(self, token, t_from, t_to):
        with self.lock:
            return [r for r in self.trade_log.get(str(token), ()) if t_from <= r[0] <= t_to]

    def status(self):
        with self.lock:
            return {"connected": self.connected, "connects": self.stats["connects"], "errors": self.stats["errors"],
                    "last_error": self.last_error, "messages": self.stats["messages"], "trades": self.stats["trades"],
                    "tokens_wanted": len(self.wanted), "tokens_subscribed": len(self.subscribed),
                    "tokens_with_book": sum(1 for t in self.subscribed if t in self.books)}

    # -- messages ----------------------------------------------------------------
    def handle(self, text: str, now: float):
        self.stats["messages"] += 1
        if not text or text[0] not in "[{":          # "PONG" and other plain replies
            return
        msg = json.loads(text)
        with self.lock:
            for m in msg if isinstance(msg, list) else [msg]:
                if isinstance(m, dict):
                    self._apply(m, now)

    def _apply(self, m, now):
        kind = m.get("event_type")
        if kind == "book":
            tok = str(m.get("asset_id"))
            self.books[tok] = {"bids": _levels(m.get("bids", m.get("buys"))),
                               "asks": _levels(m.get("asks", m.get("sells")))}
            self._note(tok, now)
        elif kind == "price_change":
            changes = m.get("price_changes")
            if changes is None:                          # older format: one token per message
                changes = [dict(c, asset_id=m.get("asset_id")) for c in m.get("changes") or []]
            touched = set()
            for c in changes:
                tok = str(c.get("asset_id"))
                b = self.books.get(tok)
                if b is None:
                    continue                             # no snapshot yet
                side = b["bids"] if str(c.get("side")).upper() == "BUY" else b["asks"]
                try:
                    p, s = float(c["price"]), float(c["size"])   # size = new total at that price
                except (KeyError, TypeError, ValueError):
                    continue
                if s > 0:
                    side[p] = s
                else:
                    side.pop(p, None)
                touched.add(tok)
            for tok in touched:
                self._note(tok, now)
        elif kind == "last_trade_price":
            self.stats["trades"] += 1
            try:
                p, s = float(m.get("price")), float(m.get("size") or 0)
            except (TypeError, ValueError):
                return
            if p >= FAVOURITE:
                tok = str(m.get("asset_id"))
                self.trade_log.setdefault(tok, collections.deque(maxlen=MAX_TRADES)).append(
                    (now, p, s, str(m.get("side") or "")))

    def _note(self, tok, now):
        top = summary(self.books[tok])
        if (top[0] or 0) < FAVOURITE and (top[1] or 0) < FAVOURITE:
            return
        dq = self.hist.setdefault(tok, collections.deque(maxlen=MAX_HISTORY))
        if dq and dq[-1][1:] == top:
            return
        dq.append((now, *top))
        while dq[0][0] < now - KEEP_SECONDS:
            dq.popleft()

    # -- background thread --------------------------------------------------------
    def _run(self):
        sock, buf, frag = None, bytearray(), None
        last_ping = last_connect = 0.0
        backoff = 5
        while not self._stop.is_set():
            try:
                with self.lock:
                    wanted = self.wanted
                now = time.time()
                if wanted and (sock is None or (wanted != self.subscribed and now - last_connect >= RESUBSCRIBE_GAP)):
                    # connect the new subscription first, then drop the old one: no gap in the data
                    new, rest = connect(self.url)
                    new.sendall(frame(1, json.dumps({"assets_ids": sorted(wanted), "type": "market"}).encode()))
                    new.settimeout(1.0)
                    if sock is not None:
                        try:
                            sock.close()
                        except OSError:
                            pass
                    sock, buf, frag = new, bytearray(rest), None
                    last_connect, backoff = now, 5
                    with self.lock:
                        self.subscribed, self.connected = wanted, True
                        self.stats["connects"] += 1
                        for store in (self.books, self.hist, self.trade_log):   # forget matches no longer watched
                            for t in [t for t in store if t not in wanted]:
                                del store[t]
                if sock is None:
                    self._stop.wait(1)
                    continue
                if now - last_ping >= PING_SECONDS:
                    sock.sendall(frame(1, b"PING"))
                    last_ping = now
                try:
                    data = sock.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    raise ConnectionError("feed closed by the server")
                buf += data
                while True:
                    f = parse(buf)
                    if f is None:
                        break
                    fin, op, payload, used = f
                    del buf[:used]
                    if op == 9:                                  # ping -> pong
                        sock.sendall(frame(10, payload))
                    elif op == 8:
                        raise ConnectionError("feed closed by the server")
                    elif op in (1, 2) or (op == 0 and frag is not None):
                        frag = bytearray(payload) if op else frag + payload
                        if fin:
                            text, frag = bytes(frag).decode("utf-8", "replace"), None
                            self.handle(text, time.time())
            except Exception as exc:                             # never stop for good: wait, then retry
                with self.lock:
                    self.connected = False
                    self.stats["errors"] += 1
                    self.last_error = f"{type(exc).__name__}: {exc}"[:200]
                self.on_error("live feed", exc)
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                sock = None
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 300)
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def live_summary(hist, trades, t0, end, min_shares=5):
    """Plain numbers for one end window. Times are seconds relative to t0, the moment shadow mode
    saw the result (negative = before). hist and trades come from LiveFeed.history / .trades."""
    def until(col):                     # last moment >= min_shares were for sale in that band
        last = None
        for i, r in enumerate(hist):
            if r[col] >= min_shares:
                last = hist[i + 1][0] if i + 1 < len(hist) else end
        return None if last is None else round(last - t0, 2)

    def seconds_after(col):             # how long after t0 they were for sale
        total = 0.0
        for i, r in enumerate(hist):
            a, b = max(r[0], t0), min(hist[i + 1][0] if i + 1 < len(hist) else end, end)
            if b > a and r[col] >= min_shares:
                total += b - a
        return round(total, 1)

    after = [t for t in trades if t[0] >= t0]

    def by_price(rows):
        out = {}
        for t in rows:
            k = f"{t[1]:g}"
            out[k] = round(out.get(k, 0) + t[2], 2)
        return out
    in_band = lambda lo, hi: [t for t in after if lo <= t[1] <= hi]
    bid099 = next((r[0] for r in hist if r[2] is not None and r[2] >= 0.99), None)
    return {"live_samples": len(hist),
            "live_v1_until_s": until(3), "live_v1_seconds_after": seconds_after(3),
            "live_late_until_s": until(4), "live_late_seconds_after": seconds_after(4),
            "live_bid099_at_s": None if bid099 is None else round(bid099 - t0, 2),
            "live_trades_v1_after": len(in_band(*V1)),
            "live_trades_v1_shares_after": round(sum(t[2] for t in in_band(*V1)), 2),
            "live_trades_late_after": len(in_band(*LATE)),
            "live_trades_late_shares_after": round(sum(t[2] for t in in_band(*LATE)), 2),
            # each trade after t0 (first 50): seconds after t0, price, size, side; and shares by price
            "live_trades_after": [[round(t[0] - t0, 2), t[1], t[2], t[3] if len(t) > 3 else None] for t in after[:50]],
            "live_trades_after_n": len(after), "live_trades_after_by_price": by_price(after)}
