import os; os.environ["POLYSWEEPER_NO_ALERTS"] = "1"   # tests must never send phone alerts
"""Desktop app (app/polysweeper_app.py): the data side, tested without a screen."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
import polysweeper_app as pa  # noqa: E402


def write(path, rows, end="\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as f:
        for r in rows:
            f.write((json.dumps(r) if isinstance(r, dict) else r) + end)


class TailTests(unittest.TestCase):
    def test_only_complete_new_lines_and_restart_on_shrink(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            p = Path(d) / "x.jsonl"
            write(p, [{"a": 1}])
            p.open("a").write('{"a": 2')                      # half-written line
            t = pa.JsonlTail(p)
            self.assertEqual(t.read_new(), ([{"a": 1}], False))
            p.open("a").write('}\r\n{"a": 3}\r\n')             # Windows line endings
            self.assertEqual(t.read_new(), ([{"a": 2}, {"a": 3}], False))
            self.assertEqual(t.read_new(), ([], False))
            p.write_text('{"b": 1}\n')                         # replaced by a shorter file
            self.assertEqual(t.read_new(), ([{"b": 1}], True))


class StoreTests(unittest.TestCase):
    def make(self, d):
        sh = Path(d) / "code" / "data" / "shadow"
        write(sh / "trades.jsonl", [
            {"type": "entry", "rule": "price_only", "ts": "2026-10-03T10:00:00+00:00", "key": "m1:0", "market_id": "m1",
             "token_idx": 0, "league": "cs2", "question": "A vs B", "outcome": "A", "vwap": 0.96, "cost": 4.81,
             "shares": 5.0, "fills": [[0.96, 5.0]], "asks_top5": [[0.96, 50.0]], "event": {"score": "1-0"}},
            {"type": "settled", "ts": "2026-10-03T11:00:00+00:00", "key": "m1:0", "rule": "price_only",
             "result": "win", "pnl": 0.19},
            {"type": "entry", "rule": "price_only", "ts": "2026-10-03T12:00:00+00:00", "key": "m2:1", "market_id": "m2",
             "token_idx": 1, "league": "atp", "question": "C vs D", "outcome": "D", "vwap": 0.97, "cost": 4.86, "shares": 5.0},
            {"type": "entry", "ts": "2026-09-30T22:00:00+00:00", "key": "m3:0", "market_id": "m3", "league": "cs2",
             "question": "E vs F", "outcome": "E", "vwap": 0.98, "cost": 4.9, "shares": 5.0},   # oldest format: no rule
            {"type": "settled", "ts": "2026-09-30T22:02:00+00:00", "key": "m3:0", "result": "loss", "pnl": -4.9},
            {"type": "skip_bad_book", "ts": "2026-10-03T12:01:00+00:00", "key": "bad:m9:0", "question": "G vs H",
             "outcome": "G", "best_ask": 0.97, "reason": "x"}])
        write(sh / "events.jsonl", [
            {"type": "end_window", "ts": "2026-10-03T15:00:00+00:00", "market_id": "m1", "title": "A vs B",
             "max_shares_096_0995": 0, "max_shares_0995_0999": 8666, "closed_because": "15 minutes done"},
            {"type": "end_window", "ts": "2026-10-03T13:00:00+00:00", "market_id": "old", "max_shares_096_0995": 9},
            {"type": "live_feed_status", "ts": "2026-10-03T15:05:00+00:00", "connected": True}])
        write(sh / "errors.jsonl", [{"ts": "2026-10-03T15:06:00+00:00", "where": "live feed", "error": "closed"},
                                    {"ts": "2026-10-03T15:07:00+00:00", "where": "settle", "error": "boom"}])
        (sh / "live.json").write_text(json.dumps({"t": 1e12, "markets": [
            {"mid": "m2", "title": "C vs D", "outcomes": ["C", "D"], "prices": [[0.05, 0.03, "live"], [0.98, 0.97, "live"]],
             "hot": True}]}))
        return sh

    def test_numbers(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            self.make(d)
            st = pa.Store(d)
            self.assertTrue(st.refresh())
            k = st.kpis()
            self.assertEqual((k["wins"], k["losses"], k["open"], k["buys"]), (1, 1, 1, 3))
            self.assertAlmostEqual(k["net"], 0.19 - 4.9)
            self.assertEqual([round(v, 2) for _, v in st.equity()], [-4.9, -4.71])        # payout order
            by_rule = st.by("rule")
            self.assertEqual((by_rule["price_only"]["buys"], by_rule["price_only"]["wins"]), (3, 1))
            self.assertEqual(by_rule["price_only"]["losses"], 1)                         # old record counts as price only
            opens = st.open_positions()
            self.assertEqual([(o["key"], o["bid_now"], o["watched"]) for o in opens], [("m2:1", 0.97, True)])
            self.assertEqual(st.after_match()["n"], 1)                                   # the old row is left out
            self.assertEqual(st.after_match()["late"], 1)
            self.assertEqual(st.bot_state(now=1e12 + 5)[0], "running")
            self.assertEqual(st.bot_state(now=1e12 + 3600)[0], "stopped")
            self.assertEqual(sum(not pa.Store.is_reconnect(e) for e in st.errors), 1)    # feed reconnect is not a problem
            tags = [tag for _, tag, _ in st.feed]
            self.assertIn("skip", tags)
            self.assertIn("error", tags)
            self.assertFalse(st.refresh())                                               # nothing new

    def test_new_lines_arrive_live(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            sh = self.make(d)
            st = pa.Store(d)
            st.refresh()
            before = st.feed_count
            write(sh / "trades.jsonl", [{"type": "settled", "ts": "2026-10-03T13:00:00+00:00", "key": "m2:1",
                                         "rule": "price_only", "result": "win", "pnl": 0.14}])
            self.assertTrue(st.refresh())
            self.assertEqual(st.kpis()["open"], 0)
            self.assertEqual(st.feed_count, before + 1)
            self.assertEqual(st.feed[-1][1], "win")


class ShadowLiveFileTests(unittest.TestCase):
    def test_live_file_is_written_and_readable_by_the_app(self):
        import polysweeper.shadow as sh
        from polysweeper.config import Limits
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            sh.OUT = Path(d) / "code" / "data" / "shadow"
            sh.OUT.mkdir(parents=True)
            sh.leagues = lambda: {"cs2": {"series": "1"}}
            s = sh.Shadow(["cs2"], Limits.from_json("config.json"))
            ev = {"id": "e1", "title": "A vs B", "score": "000-000|1-0|Bo3", "live": True, "ended": False,
                  "startTime": "2020-01-01T00:00:00Z"}
            s.markets = {"m1": {"league": "cs2", "event": ev, "tokens": ["ta", "tb"], "outcomes": ["A", "B"],
                                "market": {"question": "A vs B"}}}
            s.last_best = {"m1": {0: (0.97, 0.95), 1: (0.05, 0.03)}}
            s.write_live()
            live = json.loads((sh.OUT / "live.json").read_text())
            m = live["markets"][0]
            self.assertEqual((m["mid"], m["hot"], m["prices"][0][:2], m["prices"][0][2]), ("m1", True, [0.97, 0.95], "book"))
            st = pa.Store(d)
            st.refresh()
            self.assertEqual(st.bot_state()[0], "running")
            self.assertEqual(len(st.matches()), 1)


if __name__ == "__main__":
    unittest.main()
