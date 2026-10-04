"""PolySweeper desktop app: a live view of shadow mode (pretend trades, no real money).

Read-only. It reads the files shadow mode writes on this PC, every second:
  code/data/shadow/live.json      what the bot sees right now (matches, live prices, scores, flags)
  code/data/shadow/trades.jsonl   every pretend buy (with the sell orders it took), payout and skip
  code/data/shadow/events.jsonl   match states, after-match study, live feed status
  code/data/shadow/errors.jsonl   problems
  code/data/shadow/autopilot.log  what the autopilot did
It never places an order and never changes a file.

Started by PolySweeper.exe (app/launcher.py) or, for testing, `python app/polysweeper_app.py`.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

APP_VERSION = "1.0"
STUDY_START = "2026-10-03T14:12"        # after-match rows before this came from an older version
BUY_BAND = (0.96, 0.995)
RULE_NAMES = {"price_only": "Price only", "score": "Score check", "confirmed": "Confirmed result"}
SKIP_NAMES = {"skip_bad_book": "junk order book", "skip_thin": "too few shares",
              "skip_score_against": "score says the other side won", "skip_second_buy": "one buy per match"}
FEED_MAX = 400


# ---------------------------------------------------------------------------------------------
# Data (no tkinter here: tested without a screen)
# ---------------------------------------------------------------------------------------------
def parse_iso(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def local_time(ts, with_day=False):
    """'2026-10-03T14:12:05+00:00' -> local clock '15:12:05' (or 'Oct 03 15:12' with_day)."""
    d = parse_iso(ts)
    if d is None:
        return ""
    d = d.astimezone()
    return d.strftime("%b %d %H:%M") if with_day else d.strftime("%H:%M:%S")


def money(x):
    return "-" if x is None else f"{'+' if x >= 0 else '-'}${abs(x):.2f}"


def price(x):
    return "-" if x is None else f"{x:.3f}"


class JsonlTail:
    """Reads only the new complete lines of a growing JSON-lines file."""

    def __init__(self, path):
        self.path = Path(path)
        self.pos = 0
        self.rest = b""

    def read_new(self):
        """(new rows, reset). reset=True when the file shrank or was replaced: start again."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return [], False
        reset = size < self.pos
        if reset:
            self.pos, self.rest = 0, b""
        if size == self.pos:
            return [], reset
        try:
            with self.path.open("rb") as f:
                f.seek(self.pos)
                data = f.read()
                self.pos = f.tell()
        except OSError:
            return [], reset
        lines = (self.rest + data).split(b"\n")
        self.rest = lines.pop()                      # the last piece may still be being written
        rows = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
        return rows, reset


class Store:
    """Everything the app shows, built from shadow mode's files and refreshed incrementally."""

    def __init__(self, repo):
        self.repo = Path(repo)
        self.dir = self.repo / "code" / "data" / "shadow"
        self.version = 0                             # bumps when anything changed
        self._start()

    def _start(self):
        self.trades_tail = JsonlTail(self.dir / "trades.jsonl")
        self.events_tail = JsonlTail(self.dir / "events.jsonl")
        self.errors_tail = JsonlTail(self.dir / "errors.jsonl")
        self.entries = collections.OrderedDict()     # key -> entry record
        self.settled = {}                            # key -> settled record
        self.skips = collections.Counter()
        self.skips_today = collections.Counter()
        self.feed = collections.deque(maxlen=FEED_MAX)   # (ts, tag, text), oldest first
        self.feed_count = 0                          # items ever added (the deque forgets old ones)
        self.end_windows = {}                        # market_id -> first usable end_window row
        self.feed_status = None                      # newest live_feed_status row
        self.errors = collections.deque(maxlen=200)
        self.live = None
        self.live_mtime = None
        self.log_lines = []
        self.log_mtime = None

    # -- refresh ------------------------------------------------------------------------------
    def refresh(self):
        """Read whatever is new. Returns True if anything changed."""
        changed = False
        for tail, handle in ((self.trades_tail, self._trade), (self.events_tail, self._event),
                             (self.errors_tail, self._error)):
            rows, reset = tail.read_new()
            if reset:                                # a file was replaced: rebuild everything
                self._start()
                return self.refresh() or True
            for r in rows:
                if isinstance(r, dict):
                    handle(r)
            changed |= bool(rows)
        changed |= self._read_live()
        changed |= self._read_log()
        if changed:
            self.version += 1
        return changed

    def _add(self, item):
        self.feed.append(item)
        self.feed_count += 1

    def _trade(self, r):
        t, key = r.get("type"), r.get("key")
        rule = RULE_NAMES.get(r.get("rule") or "price_only", r.get("rule"))
        if t == "entry":
            self.entries[key] = r
            ev = r.get("event") or {}
            state = "match ENDED" if r.get("event_ended_flag") else "match still in play"
            self._add((r.get("ts"), "buy",
                              f"PRETEND BUY ({rule})  {r.get('outcome')} at {price(r.get('vwap'))}, cost ${r.get('cost', 0):.2f}"
                              f"  |  {r.get('question') or ''}  |  {state}, score {ev.get('score')}"))
        elif t == "settled":
            self.settled[key] = r
            e = self.entries.get(key, {})
            res = r.get("result")
            word = {"win": "WON", "loss": "LOST", "split": "PAID 50/50"}.get(res, str(res))
            self._add((r.get("ts"), "win" if res == "win" else "loss" if res == "loss" else "info",
                              f"PAID OUT: {word} {money(r.get('pnl'))}  {e.get('outcome', '')}  |  {e.get('question', '')}"))
        elif t in SKIP_NAMES:
            self.skips[t] += 1
            if self._is_today(r.get("ts")):
                self.skips_today[t] += 1
            self._add((r.get("ts"), "skip",
                              f"Skipped ({SKIP_NAMES[t]}): {r.get('outcome', '')} at {price(r.get('best_ask'))}"
                              f"  |  {r.get('question') or ''}"))

    def _event(self, r):
        t = r.get("type")
        if t == "live_feed_status":
            self.feed_status = r
        elif t == "end_window":
            if r.get("ts", "") >= STUDY_START and r.get("market_id") not in self.end_windows:
                self.end_windows[r.get("market_id")] = r
            v1, late = r.get("max_shares_096_0995") or 0, r.get("max_shares_0995_0999") or 0
            self._add((r.get("ts"), "info",
                              f"After the result: {r.get('title') or ''}  |  shares for sale at 0.96-0.995: {v1:g}, "
                              f"at 0.995-0.999: {late:g}"))
        elif t == "confirmed":
            self._add((r.get("ts"), "info", f"Result confirmed by {r.get('detail')}  (market {r.get('market_id')})"))

    @staticmethod
    def is_reconnect(r):
        """Live price feed dropped and reconnects by itself: normal, not a problem."""
        return r.get("where") == "live feed"

    def _error(self, r):
        self.errors.append(r)
        if self.is_reconnect(r):
            self._add((r.get("ts"), "skip", f"Live prices: connection dropped, reconnecting by itself ({str(r.get('error'))[:80]})"))
        else:
            self._add((r.get("ts"), "error", f"PROBLEM in {r.get('where')}: {r.get('error')}"))

    def _read_live(self):
        p = self.dir / "live.json"
        try:
            m = p.stat().st_mtime
        except OSError:
            if self.live is not None:
                self.live = None
                return True
            return False
        if m == self.live_mtime:
            return False
        try:
            self.live = json.loads(p.read_text())
            self.live_mtime = m
            return True
        except (OSError, ValueError):                # being rewritten right now: try again next second
            return False

    def _read_log(self):
        p = self.dir / "autopilot.log"
        try:
            m = p.stat().st_mtime
            if m == self.log_mtime:
                return False
            with p.open("rb") as f:
                f.seek(max(0, p.stat().st_size - 65536))
                self.log_lines = f.read().decode("utf-8", "replace").splitlines()[-200:]
            self.log_mtime = m
            return True
        except OSError:
            return False

    # -- views -------------------------------------------------------------------------------
    @staticmethod
    def _is_today(ts):
        d = parse_iso(ts)
        return d is not None and d.astimezone().date() == datetime.now().astimezone().date()

    def bot_state(self, now=None):
        """('running' | 'slow' | 'stopped' | 'no data', seconds since the live file was written)."""
        if not self.live:
            return "no data", None
        age = (now or time.time()) - (self.live.get("t") or 0)
        return ("running" if age < 30 else "slow" if age < 300 else "stopped"), age

    def trade_rows(self):
        """All pretend buys, newest first, with their result."""
        out = []
        for key, e in self.entries.items():
            s = self.settled.get(key)
            out.append({"key": key, "ts": e.get("ts"), "rule": e.get("rule") or "price_only", "league": e.get("league"),
                        "question": e.get("question"), "outcome": e.get("outcome"), "vwap": e.get("vwap"),
                        "cost": e.get("cost"), "shares": e.get("shares"), "result": s.get("result") if s else "open",
                        "pnl": s.get("pnl") if s else None, "settled_ts": s.get("ts") if s else None, "entry": e})
        return out[::-1]

    def kpis(self):
        rows = self.trade_rows()
        done = [r for r in rows if r["result"] != "open"]
        wins = sum(r["result"] == "win" for r in done)
        losses = sum(r["result"] == "loss" for r in done)
        return {"net": sum(r["pnl"] or 0 for r in done),
                "today": sum(r["pnl"] or 0 for r in done if self._is_today(r["settled_ts"])),
                "wins": wins, "losses": losses, "open": len(rows) - len(done),
                "win_rate": (100.0 * wins / (wins + losses)) if wins + losses else None,
                "buys_today": sum(self._is_today(r["ts"]) for r in rows),
                "skips_today": sum(self.skips_today.values()), "buys": len(rows)}

    def by(self, field):
        """Per rule or per league: buys, wins, losses, open, net."""
        out = collections.OrderedDict()
        for r in sorted(self.trade_rows(), key=lambda r: str(r[field])):
            g = out.setdefault(r[field] or "-", {"buys": 0, "wins": 0, "losses": 0, "open": 0, "net": 0.0})
            g["buys"] += 1
            if r["result"] == "open":
                g["open"] += 1
            else:
                g["wins"] += r["result"] == "win"
                g["losses"] += r["result"] == "loss"
                g["net"] += r["pnl"] or 0
        return out

    def equity(self):
        """[(settled time, cumulative P&L)] in payout order."""
        pts, total = [], 0.0
        for s in sorted(self.settled.values(), key=lambda s: s.get("ts") or ""):
            total += s.get("pnl") or 0
            pts.append((s.get("ts"), total))
        return pts

    def matches(self):
        return (self.live or {}).get("markets") or []

    def open_positions(self):
        """Open pretend trades (bought, not paid out yet) with the price the bot sees now for that side."""
        prices = {str(m.get("mid")): m.get("prices") or [] for m in self.matches()}
        out = []
        for r in self.trade_rows():
            if r["result"] != "open":
                continue
            e = r["entry"]
            idx = e.get("token_idx")
            if idx is None:                          # very old records: key is "<market>:<index>"
                idx = int(str(r["key"]).rsplit(":", 1)[-1]) if str(r["key"]).rsplit(":", 1)[-1].isdigit() else 0
            pr = prices.get(str(e.get("market_id"))) or []
            bid = pr[idx][1] if idx < len(pr) and pr[idx] else None
            out.append(dict(r, bid_now=bid, watched=bool(pr)))
        return out

    def after_match(self):
        rows = list(self.end_windows.values())
        live = [r for r in rows if "live_samples" in r]
        return {"n": len(rows),
                "v1": sum((r.get("max_shares_096_0995") or 0) >= 5 for r in rows),
                "late": sum((r.get("max_shares_0995_0999") or 0) >= 5 for r in rows),
                "cut": sum(r.get("closed_because") == "shadow mode stopped" for r in rows),
                "live_n": len(live),
                "live_v1_after": sum((r.get("live_v1_until_s") or -1) > 0 for r in live),
                "live_traded_v1": sum(bool(r.get("live_trades_v1_after")) for r in live),
                "live_traded_late": sum(bool(r.get("live_trades_late_after")) for r in live)}


# ---------------------------------------------------------------------------------------------
# Window (tkinter: part of Python, bundled into PolySweeper.exe)
# ---------------------------------------------------------------------------------------------
C = {"bg": "#0e1318", "panel": "#151c24", "panel2": "#1b2430", "line": "#283342", "fg": "#e6edf3",
     "muted": "#8b98a5", "green": "#3fb950", "red": "#f85149", "amber": "#d29922", "blue": "#58a6ff",
     "purple": "#bc8cff", "sel": "#1f3a5f"}


class App:
    def __init__(self, repo, selftest=None, seconds=10):
        import tkinter as tk
        from tkinter import font as tkfont, ttk
        self.tk, self.ttk = tk, ttk
        self.store = Store(repo)
        self.selftest, self.seconds = selftest, seconds
        self.problems = []                           # exceptions caught while refreshing (shown, logged)
        self.drawn = {"version": -1, "feed": 0, "equity": None}
        self.root = root = tk.Tk()
        root.title("PolySweeper — shadow mode (pretend trades, no real money)")
        root.geometry("1400x880")
        root.minsize(1060, 680)
        root.configure(bg=C["bg"])
        try:
            if getattr(sys, "frozen", False):
                root.iconbitmap(default=sys.executable)
        except Exception:
            pass
        fams = set(tkfont.families(root))
        ui = next((f for f in ("Segoe UI", "Inter", "DejaVu Sans", "Helvetica") if f in fams), "TkDefaultFont")
        mono = next((f for f in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New") if f in fams), "TkFixedFont")
        self.f = {"ui": (ui, 10), "small": (ui, 9), "bold": (ui, 10, "bold"), "title": (ui, 15, "bold"),
                  "kpi": (ui, 18, "bold"), "mono": (mono, 9)}
        self._style()
        self._build()
        root.after(200, self.tick)
        tab = os.environ.get("POLYSWEEPER_TAB")
        if tab and tab.isdigit():
            self.nb.select(int(tab))
        if selftest:
            root.after(int(seconds * 1000), self.finish_selftest)

    # -- look ------------------------------------------------------------------------------
    def _style(self):
        s = self.ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["fg"], fieldbackground=C["panel"], font=self.f["ui"],
                    bordercolor=C["line"], lightcolor=C["line"], darkcolor=C["line"])
        s.configure("TFrame", background=C["bg"])
        s.configure("Panel.TFrame", background=C["panel"])
        s.configure("TLabel", background=C["bg"], foreground=C["fg"])
        s.configure("Muted.TLabel", foreground=C["muted"], font=self.f["small"])
        s.configure("Panel.TLabel", background=C["panel"])
        s.configure("Head.TLabel", background=C["panel"], foreground=C["fg"], font=self.f["bold"])
        s.configure("Treeview", background=C["panel"], fieldbackground=C["panel"], foreground=C["fg"],
                    rowheight=24, borderwidth=0, font=self.f["ui"])
        s.map("Treeview", background=[("selected", C["sel"])], foreground=[("selected", C["fg"])])
        s.configure("Treeview.Heading", background=C["panel2"], foreground=C["muted"], relief="flat", font=self.f["small"])
        s.map("Treeview.Heading", background=[("active", C["line"])])
        s.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
        s.configure("TNotebook.Tab", background=C["panel"], foreground=C["muted"], padding=(16, 7), font=self.f["bold"])
        s.map("TNotebook.Tab", background=[("selected", C["panel2"])], foreground=[("selected", C["fg"])])
        s.configure("Vertical.TScrollbar", background=C["panel2"], troughcolor=C["panel"], arrowcolor=C["muted"])
        s.configure("TPanedwindow", background=C["bg"])

    def _tree(self, parent, cols, widths, height=10, anchors=None):
        ttk = self.ttk
        box = ttk.Frame(parent, style="Panel.TFrame")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=height, selectmode="browse")
        for c, w in zip(cols, widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, minwidth=36, stretch=c.startswith(("Match", "Side", "Group")),
                        anchor=(anchors or {}).get(c, "w"))
        sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, color in (("win", C["green"]), ("loss", C["red"]), ("open", C["amber"]), ("hot", C["amber"]),
                           ("band", C["green"]), ("ended", C["muted"]), ("plain", C["fg"])):
            tree.tag_configure(tag, foreground=color)
        return box, tree

    def _text(self, parent, height=10):
        tk, ttk = self.tk, self.ttk
        box = ttk.Frame(parent, style="Panel.TFrame")
        t = tk.Text(box, height=height, bg=C["panel"], fg=C["fg"], insertbackground=C["fg"], relief="flat",
                    wrap="word", font=self.f["mono"], padx=10, pady=8, highlightthickness=0, borderwidth=0)
        sb = ttk.Scrollbar(box, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set, state="disabled")
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, color in (("buy", C["blue"]), ("win", C["green"]), ("loss", C["red"]), ("skip", C["muted"]),
                           ("info", C["purple"]), ("error", C["red"]), ("time", C["muted"]), ("head", C["fg"]),
                           ("good", C["green"]), ("warn", C["amber"])):
            t.tag_configure(tag, foreground=color)
        t.tag_configure("head", font=self.f["bold"])
        return box, t

    def _section(self, parent, title, note=""):
        ttk = self.ttk
        fr = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 8, 10, 4))
        ttk.Label(fr, text=title, style="Head.TLabel").pack(side="left")
        if note:
            ttk.Label(fr, text="   " + note, style="Muted.TLabel", background=C["panel"]).pack(side="left")
        return fr

    # -- layout ------------------------------------------------------------------------------
    def _build(self):
        tk, ttk, root = self.tk, self.ttk, self.root
        head = ttk.Frame(root, padding=(16, 12, 16, 6))
        head.pack(fill="x")
        ttk.Label(head, text="PolySweeper", font=self.f["title"]).pack(side="left")
        ttk.Label(head, text="   shadow mode · pretend trades only · no real money · this app never places orders",
                  style="Muted.TLabel").pack(side="left", pady=(6, 0))
        self.clock = ttk.Label(head, style="Muted.TLabel")
        self.clock.pack(side="right")
        chips = ttk.Frame(root, padding=(16, 0, 16, 8))
        chips.pack(fill="x")
        self.chip = {}
        for name in ("Bot", "Live prices", "2-second checks", "Autopilot", "Problems"):
            lab = tk.Label(chips, text=name, bg=C["panel2"], fg=C["muted"], font=self.f["small"], padx=10, pady=4)
            lab.pack(side="left", padx=(0, 8))
            self.chip[name] = lab
        kp = ttk.Frame(root, padding=(16, 0, 16, 10))
        kp.pack(fill="x")
        self.kpi = {}
        for key, cap in (("net", "Net result (all pretend trades)"), ("today", "Paid out today"),
                         ("wl", "Wins / losses"), ("rate", "Win rate"), ("open", "Open pretend trades"),
                         ("buys", "Pretend buys today"), ("skips", "Skipped today")):
            box = tk.Frame(kp, bg=C["panel"], padx=14, pady=8, highlightbackground=C["line"], highlightthickness=1)
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            val = tk.Label(box, text="-", bg=C["panel"], fg=C["fg"], font=self.f["kpi"], anchor="w")
            val.pack(fill="x")
            tk.Label(box, text=cap, bg=C["panel"], fg=C["muted"], font=self.f["small"], anchor="w").pack(fill="x")
            self.kpi[key] = val

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=16)
        self.nb = nb
        # Live tab
        live = ttk.Frame(nb)
        nb.add(live, text="Live")
        pane = ttk.Panedwindow(live, orient="horizontal")
        pane.pack(fill="both", expand=True, pady=(8, 0))
        left = ttk.Frame(pane, style="Panel.TFrame")
        right = ttk.Frame(pane, style="Panel.TFrame")
        pane.add(left, weight=5)
        pane.add(right, weight=3)
        self.matches_head = self._section(left, "Watched matches", "live prices · best ask / best bid · updates every second")
        self.matches_head.pack(fill="x")
        box, self.t_matches = self._tree(left, ("League", "Match", "Score", "State", "Side A", "Side B", "Flags"),
                                         (56, 210, 112, 54, 150, 150, 118), height=14)
        box.pack(fill="both", expand=True, padx=(8, 8))
        self._section(left, "Open pretend trades", "waiting for the market to pay out").pack(fill="x")
        box, self.t_open = self._tree(left, ("Bought", "Match", "Side", "At", "Now", "If it wins", "If it loses"),
                                      (96, 240, 130, 52, 52, 72, 72), height=5)
        box.pack(fill="both", expand=False, padx=(8, 8), pady=(0, 8))
        self._section(right, "Activity", "newest first: buys, sell orders taken, payouts, skips, problems").pack(fill="x")
        box, self.t_feed = self._text(right, height=20)
        box.pack(fill="both", expand=True, padx=(8, 8), pady=(0, 8))
        # Trades tab
        tr = ttk.Frame(nb)
        nb.add(tr, text="Trades")
        self._section(tr, "Every pretend buy", "click one to see the sell orders it took").pack(fill="x", pady=(8, 0))
        box, self.t_trades = self._tree(tr, ("Time", "Rule", "League", "Match", "Side", "Avg price", "Cost", "Result", "P&L"),
                                        (110, 110, 70, 330, 160, 80, 70, 70, 80), height=14,
                                        anchors={"Avg price": "e", "Cost": "e", "P&L": "e"})
        box.pack(fill="both", expand=True, padx=8)
        self.t_trades.bind("<<TreeviewSelect>>", self.show_trade)
        box, self.t_detail = self._text(tr, height=9)
        box.pack(fill="x", padx=8, pady=8)
        # Performance tab
        pf = ttk.Frame(nb)
        nb.add(pf, text="Performance")
        self._section(pf, "Running total of all pretend payouts", "every point is one payout").pack(fill="x", pady=(8, 0))
        self.canvas = tk.Canvas(pf, bg=C["panel"], height=280, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8)
        self.canvas.bind("<Configure>", lambda e: self.draw_equity(force=True))
        row = ttk.Frame(pf)
        row.pack(fill="x", pady=8)
        cols = ("Group", "Buys", "Wins", "Losses", "Open", "Net")
        box, self.t_rule = self._tree(row, cols, (150, 60, 60, 60, 60, 80), height=4,
                                      anchors={c: "e" for c in cols[1:]})
        box.pack(side="left", fill="both", expand=True, padx=(8, 4))
        box, self.t_league = self._tree(row, cols, (150, 60, 60, 60, 60, 80), height=4,
                                        anchors={c: "e" for c in cols[1:]})
        box.pack(side="left", fill="both", expand=True, padx=(4, 8))
        # After-match tab
        am = ttk.Frame(nb)
        nb.add(am, text="After the match")
        box, self.t_after = self._text(am, height=20)
        box.pack(fill="both", expand=True, padx=8, pady=8)
        # System tab
        sy = ttk.Frame(nb)
        nb.add(sy, text="System")
        box, self.t_sys = self._text(sy, height=11)
        box.pack(fill="x", padx=8, pady=(8, 4))
        self._section(sy, "Autopilot log", "newest at the bottom").pack(fill="x")
        box, self.t_log = self._text(sy, height=12)
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.footer = ttk.Label(root, style="Muted.TLabel", padding=(16, 6))
        self.footer.pack(fill="x")

    # -- refresh -----------------------------------------------------------------------------
    def tick(self):
        try:
            self.store.refresh()
            self.update_all()
        except Exception as exc:                      # never close the window over a refresh problem
            self.problem(exc)
        self.root.after(1000, self.tick)

    def problem(self, exc):
        msg = f"{type(exc).__name__}: {exc}"
        self.problems.append(msg)
        try:
            log = Path(self.store.repo) / "app" / "bin" / "app-error.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {traceback.format_exc()}\n")
        except OSError:
            pass

    def update_all(self):
        st = self.store
        now = datetime.now().astimezone()
        self.clock.configure(text=now.strftime("%a %d %b  %H:%M:%S") + f"  (UTC {datetime.now(timezone.utc):%H:%M})")
        self.update_chips()
        self.update_matches()
        self.update_open()
        if self.drawn["version"] != st.version:
            self.drawn["version"] = st.version
            self.update_kpis()
            self.update_feed()
            self.update_trades()
            self.update_groups()
            self.draw_equity()
            self.update_after()
            self.update_system()
        state, age = st.bot_state()
        self.footer.configure(text=f"Data folder: {st.dir}    ·    live file {('%.0f s old' % age) if age is not None else 'missing'}"
                                   f"    ·    app v{APP_VERSION}    ·    read-only"
                                   + (f"    ·    {len(self.problems)} display problem(s), see app/bin/app-error.log"
                                      if self.problems else ""))

    def set_chip(self, name, text, color):
        self.chip[name].configure(text=text, fg=C["bg"] if color != "muted" else C["muted"],
                                  bg=C[color] if color != "muted" else C["panel2"])

    def update_chips(self):
        st = self.store
        state, age = st.bot_state()
        self.set_chip("Bot", {"running": "Bot: running", "slow": f"Bot: no update for {age:.0f} s",
                              "stopped": "Bot: STOPPED", "no data": "Bot: no live file yet"}[state],
                      {"running": "green", "slow": "amber", "stopped": "red", "no data": "muted"}[state])
        lv = st.live or {}
        lf = lv.get("live_feed") or {}
        if not lv:
            self.set_chip("Live prices", "Live prices: -", "muted")
        elif not lv.get("live_on"):
            self.set_chip("Live prices", "Live prices: off", "muted")
        elif lf.get("connected"):
            agree = lv.get("agree_pct")
            self.set_chip("Live prices", f"Live prices: connected · {lf.get('tokens_with_book', 0)} books"
                          + (f" · {agree:.0f}% match" if agree is not None else ""), "green")
        else:
            self.set_chip("Live prices", "Live prices: reconnecting", "amber")
        hot = sum(1 for m in st.matches() if m.get("hot"))
        cnt = lv.get("counters") or {}
        self.set_chip("2-second checks", f"2-second checks: {hot} match(es) near the end · {cnt.get('fast_rechecks', 0)} caught",
                      "blue" if hot else "muted")
        last = next((l for l in reversed(st.log_lines) if "autopilot:" in l), "")
        bad = any(w in last for w in ("FAILED", "could not"))
        self.set_chip("Autopilot", "Autopilot: " + (last.split("autopilot:", 1)[1].strip()[:60] if last else "no log yet"),
                      "red" if bad else "green" if last else "muted")
        today = [e for e in st.errors if Store._is_today(e.get("ts"))]
        real = sum(1 for e in today if not Store.is_reconnect(e))
        self.set_chip("Problems", f"Problems today: {real}" + (f" · {len(today) - real} feed reconnects" if len(today) > real else ""),
                      "red" if real else "green")

    def update_kpis(self):
        k = self.store.kpis()
        def put(key, text, color="fg"):
            self.kpi[key].configure(text=text, fg=C[color])
        put("net", money(k["net"]), "green" if k["net"] >= 0 else "red")
        put("today", money(k["today"]), "green" if k["today"] >= 0 else "red")
        put("wl", f"{k['wins']} / {k['losses']}", "red" if k["losses"] else "green")
        put("rate", "-" if k["win_rate"] is None else f"{k['win_rate']:.1f}%")
        put("open", str(k["open"]), "amber" if k["open"] else "fg")
        put("buys", str(k["buys_today"]))
        put("skips", str(k["skips_today"]))

    def update_matches(self):
        t, seen = self.t_matches, set()
        rows = self.store.matches()
        self.matches_head.winfo_children()[1].configure(
            text=f"   {len(rows)} matches · live prices · best ask / best bid · updates every second")
        for i, m in enumerate(rows):
            iid = str(m.get("mid"))
            seen.add(iid)
            outs, prices = m.get("outcomes") or [], m.get("prices") or []
            def side(j):
                if j >= len(outs):
                    return ""
                p = prices[j] if j < len(prices) else [None, None, None]
                return f"{str(outs[j])[:18]}  {price(p[0])} / {price(p[1])}"
            flags = []
            if m.get("hot"):
                flags.append("NEAR END")
            if m.get("window"):
                flags.append("WATCHING RESULT")
            if any(p and p[0] is not None and BUY_BAND[0] <= p[0] <= BUY_BAND[1] for p in prices):
                flags.append("IN BUY BAND")
            state = "ended" if m.get("ended") else "live" if m.get("live") else "not live"
            tag = "ended" if m.get("ended") else "band" if "IN BUY BAND" in flags else "hot" if m.get("hot") else "plain"
            vals = (str(m.get("league") or "").upper(), m.get("title") or m.get("question") or "", m.get("score") or "",
                    state, side(0), side(1), " · ".join(flags))
            if t.exists(iid):
                if t.item(iid, "values") != tuple(str(v) for v in vals):
                    t.item(iid, values=vals, tags=(tag,))
                if t.index(iid) != i:
                    t.move(iid, "", i)
            else:
                t.insert("", i, iid=iid, values=vals, tags=(tag,))
        for iid in set(t.get_children()) - seen:
            t.delete(iid)

    def update_open(self):
        t = self.t_open
        rows = self.store.open_positions()
        t.delete(*t.get_children())
        for p in rows:
            cost, shares = p.get("cost") or 0, p.get("shares") or 0
            now = price(p.get("bid_now")) if p.get("watched") else "match over"
            t.insert("", "end", values=(local_time(p.get("ts"), True), p.get("question") or "", p.get("outcome") or "",
                                        price(p.get("vwap")), now, money(shares - cost), money(-cost)), tags=("open",))

    def update_feed(self):
        st, t = self.store, self.t_feed
        items = list(st.feed)
        fresh = st.feed_count - self.drawn["feed"]
        t.configure(state="normal")
        if fresh < 0 or fresh > FEED_MAX // 2:       # first draw, or the data was reloaded: redraw
            t.delete("1.0", "end")
            new = items[-200:]
        else:
            new = items[len(items) - fresh:] if fresh else []
        for ts, tag, text in new:                    # newest goes on top
            t.insert("1.0", text + "\n\n", (tag,))
            t.insert("1.0", local_time(ts, True) + "  ", ("time",))
        lines = int(t.index("end-1c").split(".")[0])
        if lines > FEED_MAX * 3:
            t.delete(f"{FEED_MAX * 3}.0", "end")
        t.configure(state="disabled")
        self.drawn["feed"] = st.feed_count

    def update_trades(self):
        t = self.t_trades
        sel = t.selection()
        t.delete(*t.get_children())
        for r in self.store.trade_rows():
            tag = {"win": "win", "loss": "loss", "open": "open"}.get(r["result"], "plain")
            t.insert("", "end", iid=r["key"], tags=(tag,), values=(
                local_time(r["ts"], True), RULE_NAMES.get(r["rule"], r["rule"]), str(r["league"] or "").upper(),
                r["question"] or "", r["outcome"] or "", price(r["vwap"]),
                f"${r['cost']:.2f}" if r["cost"] is not None else "-", r["result"], money(r["pnl"])))
        if sel and t.exists(sel[0]):
            t.selection_set(sel[0])

    def show_trade(self, _event=None):
        sel = self.t_trades.selection()
        if not sel:
            return
        e = self.store.entries.get(sel[0])
        if not e:
            return
        s = self.store.settled.get(sel[0])
        ev = e.get("event") or {}
        t = self.t_detail
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", f"{e.get('question')}\n", ("head",))
        t.insert("end", f"Pretend buy of {e.get('shares'):g} shares of {e.get('outcome')} · rule: "
                        f"{RULE_NAMES.get(e.get('rule') or 'price_only')} · {local_time(e.get('ts'), True)}\n")
        t.insert("end", f"Why: match {'ENDED' if e.get('event_ended_flag') else 'still in play'}, score {ev.get('score')}, "
                        f"score check: {e.get('score_check')}" + (f", result source: {e.get('confirm')}" if e.get("confirm") else "") + "\n")
        book = ", ".join(f"{sz:g} @ {px:.3f}" for px, sz in (e.get("asks_top5") or []))
        fills = " + ".join(f"{sh:g} @ {px:.3f}" for px, sh in (e.get("fills") or []))
        t.insert("end", f"Sell orders on the book: {book or '-'}\n")
        t.insert("end", f"Sell orders taken: {fills or '-'}  ->  average {price(e.get('vwap'))}, fee ${e.get('fee', 0):.4f}, "
                        f"cost ${e.get('cost', 0):.2f}\n", ("buy",))
        if s:
            t.insert("end", f"Result: {s.get('result')}  {money(s.get('pnl'))}  (paid out {local_time(s.get('ts'), True)})\n",
                     ("win" if s.get("result") == "win" else "loss",))
        else:
            t.insert("end", "Result: waiting for the market to pay out\n", ("warn",))
        t.configure(state="disabled")

    def update_groups(self):
        for tree, field in ((self.t_rule, "rule"), (self.t_league, "league")):
            tree.delete(*tree.get_children())
            for name, g in self.store.by(field).items():
                label = RULE_NAMES.get(name, name) if field == "rule" else str(name).upper()
                tree.insert("", "end", tags=("win" if g["net"] >= 0 else "loss",),
                            values=(label, g["buys"], g["wins"], g["losses"], g["open"], money(g["net"])))
        self.t_rule.heading("Group", text="By rule")
        self.t_league.heading("Group", text="By league")

    def draw_equity(self, force=False):
        pts = self.store.equity()
        key = (len(pts), self.canvas.winfo_width(), self.canvas.winfo_height())
        if not force and key == self.drawn["equity"]:
            return
        self.drawn["equity"] = key
        cv = self.canvas
        cv.delete("all")
        w, h = max(cv.winfo_width(), 200), max(cv.winfo_height(), 120)
        if not pts:
            cv.create_text(w / 2, h / 2, text="No payouts yet", fill=C["muted"], font=self.f["ui"])
            return
        vals = [0.0] + [v for _, v in pts]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1:
            hi, lo = hi + 0.5, lo - 0.5
        pad_l, pad_r, pad_t, pad_b = 64, 20, 20, 30
        x = lambda i: pad_l + (w - pad_l - pad_r) * i / max(1, len(vals) - 1)
        y = lambda v: pad_t + (h - pad_t - pad_b) * (hi - v) / (hi - lo)
        for v in (lo, 0.0, hi):
            cv.create_line(pad_l, y(v), w - pad_r, y(v), fill=C["line"], dash=(2, 4) if v else ())
            cv.create_text(pad_l - 8, y(v), text=money(v), fill=C["muted"], anchor="e", font=self.f["small"])
        coords = [c for i, v in enumerate(vals) for c in (x(i), y(v))]
        last = vals[-1]
        cv.create_line(*coords, fill=C["green"] if last >= 0 else C["red"], width=2)
        for i, v in enumerate(vals[1:], 1):
            if v < vals[i - 1] - 1:                   # a loss: mark it
                cv.create_oval(x(i) - 4, y(v) - 4, x(i) + 4, y(v) + 4, outline=C["red"], width=2)
        cv.create_text(w - pad_r, pad_t, text=f"now {money(last)} after {len(pts)} payouts", fill=C["fg"],
                       anchor="ne", font=self.f["bold"])
        cv.create_text(pad_l, h - 10, text=local_time(pts[0][0], True), fill=C["muted"], anchor="w", font=self.f["small"])
        cv.create_text(w - pad_r, h - 10, text=local_time(pts[-1][0], True), fill=C["muted"], anchor="e", font=self.f["small"])

    def _fill(self, t, parts):
        t.configure(state="normal")
        t.delete("1.0", "end")
        for text, tag in parts:
            t.insert("end", text, (tag,) if tag else ())
        t.configure(state="disabled")

    def update_after(self):
        a = self.store.after_match()
        self._fill(self.t_after, [
            ("After the result: is anything left to buy?\n\n", "head"),
            (f"Matches watched after their result: {a['n']}  ({a['cut']} cut short by a restart)\n", None),
            (f"With 5+ shares for sale at 0.96-0.995 (our buy band): {a['v1']}\n", "good" if a["v1"] else "warn"),
            (f"With 5+ shares for sale at 0.995-0.999 (late band): {a['late']}\n\n", None),
            ("Second by second (live feed)\n", "head"),
            (f"Matches with live detail: {a['live_n']}\n", None),
            (f"Still something at 0.96-0.995 after the bot saw the result: {a['live_v1_after']}\n", None),
            (f"Other traders bought at 0.96-0.995 after the result: {a['live_traded_v1']} matches\n", None),
            (f"Other traders bought at 0.995-0.999 after the result: {a['live_traded_late']} matches\n\n", None),
            ("What it means: if these stay at zero, faster bots clear the winner's sell orders before we can know "
             "the result, so buying after the match does not work for us.\n", "time")])

    def update_system(self):
        st = self.store
        lv = st.live or {}
        lf = lv.get("live_feed") or {}
        fs = st.feed_status or {}
        state, age = st.bot_state()
        cnt = lv.get("counters") or {}
        self._fill(self.t_sys, [
            ("Bot (shadow mode)\n", "head"),
            (f"  state: {state}" + (f", live file {age:.0f} s old" if age is not None else "") +
             f" · started {local_time(lv.get('started'), True)} · version {lv.get('version', '-')}\n", None),
            (f"  watching {len(st.matches())} matches · open pretend trades {len(lv.get('pending') or [])} · "
             f"snapshots {cnt.get('snapshots', 0)} · 2-second reads {cnt.get('fast_reads', 0)} · "
             f"score lines {cnt.get('score_rows', 0)} · errors {cnt.get('errors', 0)}\n\n", None),
            ("Live prices (Polymarket websocket)\n", "head"),
            (f"  connected: {lf.get('connected')} · connects {lf.get('connects')} · messages {lf.get('messages')} · "
             f"books {lf.get('tokens_with_book')}/{lf.get('tokens_subscribed')} · match with normal reads "
             f"{lv.get('agree_pct')}% · last error: {lf.get('last_error')}\n", None),
            (f"  last hourly status line: {local_time(fs.get('ts'), True)} · connected {fs.get('connected')} · "
             f"agree {fs.get('book_checks_agree_pct')}%\n\n", None),
            (f"Problems recorded by the bot (errors.jsonl): {sum(not Store.is_reconnect(e) for e in st.errors)}"
             f"   ·   live price reconnects (normal): {sum(Store.is_reconnect(e) for e in st.errors)}\n",
             "warn" if any(not Store.is_reconnect(e) for e in st.errors) else "good")]
            + [(f"  {local_time(e.get('ts'), True)}  {e.get('where')}: {str(e.get('error'))[:160]}\n",
                "skip" if Store.is_reconnect(e) else "error") for e in list(st.errors)[-6:]])
        self._fill(self.t_log, [("\n".join(st.log_lines[-120:]) or "No autopilot log yet.", None)])
        self.t_log.see("end")

    # -- self-test (used by the build on Windows) ----------------------------------------------
    def finish_selftest(self):
        st = self.store
        k = st.kpis()
        first = self.t_trades.get_children()[:1]
        if first:                                    # also check the trade detail panel
            self.t_trades.selection_set(first[0])
            self.show_trade()
        detail = self.t_detail.get("1.0", "end").strip()
        out = {"ok": not self.problems, "problems": self.problems, "version": APP_VERSION,
               "data_dir": str(st.dir), "bot_state": st.bot_state()[0],
               "matches_shown": len(self.t_matches.get_children()), "open_shown": len(self.t_open.get_children()),
               "trades_shown": len(self.t_trades.get_children()), "feed_items": len(st.feed),
               "detail_lines": len(detail.splitlines()) if detail else 0,
               "equity_points": len(st.equity()),
               "kpis": {key: (round(v, 4) if isinstance(v, float) else v) for key, v in k.items()},
               "chips": {n: lab.cget("text") for n, lab in self.chip.items()}}
        Path(self.selftest).mkdir(parents=True, exist_ok=True)
        (Path(self.selftest) / "selftest.json").write_text(json.dumps(out, indent=2))
        self.exit_code = 0 if out["ok"] else 1
        self.root.destroy()

    def run(self):
        self.exit_code = 0
        self.root.mainloop()
        return self.exit_code


def main(repo, argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    selftest = None
    if "--selftest" in argv:
        i = argv.index("--selftest")
        selftest = argv[i + 1] if i + 1 < len(argv) else "selftest"
    seconds = float(os.environ.get("POLYSWEEPER_SELFTEST_SECONDS", "10"))
    return App(repo, selftest=selftest, seconds=seconds).run()


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent))
