import unittest
from datetime import datetime, timedelta, timezone

from polysweeper.backtest import run
from polysweeper.config import Limits
from polysweeper.decide import decide
from polysweeper.fees import net_edge, taker_fee
from polysweeper.killswitch import KillSwitch
from polysweeper.models import Candidate, SourceResult
from polysweeper.risk import RiskState, size_shares
from polysweeper.verifier import verify

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def src(name, status="finished", rtype="normal", winner="Team A", ended=-30, fetched=-1):
    return SourceResult(name, status, rtype, winner,
                        T0 + timedelta(minutes=ended), T0 + timedelta(minutes=fetched))


def cand(**kw):
    base = dict(market_id="m1", sport="football", market_type="moneyline",
                outcome_team="Team A", ask_price=0.98, available_size=100.0, time=T0,
                sources=(src("a"), src("b")))
    base.update(kw)
    return Candidate(**base)


class FeeTests(unittest.TestCase):
    def test_fee_matches_source_example(self):
        # source: ~$0.05 per 100 shares at 0.99 in sports (rate 0.05)
        self.assertAlmostEqual(taker_fee(100, 0.99, 0.05), 0.0495, places=4)

    def test_net_edge_positive_but_below_gross(self):
        gross = 1 / 0.985 - 1
        self.assertLess(net_edge(0.985, 0.05), gross)
        self.assertGreater(net_edge(0.985, 0.05), 0.014)


class VerifierTests(unittest.TestCase):
    args = dict(now=T0, min_sources=2, confirm_minutes=10, max_data_age_minutes=15)

    def test_two_agreeing_sources_ok(self):
        v = verify([src("a"), src("b")], **self.args)
        self.assertTrue(v.ok)
        self.assertEqual(v.winner, "team a")

    def test_one_source_not_enough(self):
        self.assertFalse(verify([src("a")], **self.args).ok)

    def test_same_source_twice_counts_once(self):
        self.assertFalse(verify([src("a"), src("a")], **self.args).ok)

    def test_disagreement_blocks(self):
        self.assertFalse(verify([src("a"), src("b", winner="Team B")], **self.args).ok)

    def test_live_blocks(self):
        self.assertFalse(verify([src("a"), src("b", status="live")], **self.args).ok)

    def test_forfeit_blocks(self):
        self.assertFalse(verify([src("a"), src("b", rtype="forfeit")], **self.args).ok)

    def test_too_early_blocks(self):
        self.assertFalse(verify([src("a", ended=-5), src("b", ended=-5)], **self.args).ok)

    def test_stale_data_blocks(self):
        self.assertFalse(verify([src("a", fetched=-60), src("b")], **self.args).ok)


class DecideTests(unittest.TestCase):
    def setUp(self):
        self.limits = Limits()
        self.state = RiskState(self.limits)
        self.kill = KillSwitch()

    def test_buy_when_everything_ok(self):
        d = decide(cand(), self.limits, self.state, self.kill)
        self.assertEqual(d.action, "BUY")
        self.assertLessEqual(d.cost, self.limits.max_stake_per_trade + 1e-9)

    def test_skip_loser_token(self):
        d = decide(cand(outcome_team="Team B"), self.limits, self.state, self.kill)
        self.assertEqual(d.action, "SKIP")

    def test_skip_price_too_high_and_too_low(self):
        for p in (0.999, 0.90):
            self.assertEqual(decide(cand(ask_price=p), self.limits, self.state, self.kill).action, "SKIP")

    def test_skip_disabled_sport_and_market_type(self):
        self.assertEqual(decide(cand(sport="tennis"), self.limits, self.state, self.kill).action, "SKIP")
        self.assertEqual(decide(cand(market_type="spread"), self.limits, self.state, self.kill).action, "SKIP")

    def test_skip_uncertain_mapping(self):
        self.assertEqual(decide(cand(mapping_confidence=0.6), self.limits, self.state, self.kill).action, "SKIP")

    def test_kill_switch_blocks(self):
        self.kill.activate("test")
        d = decide(cand(), self.limits, self.state, self.kill)
        self.assertEqual(d.action, "SKIP")
        self.assertIn("kill switch", d.reasons[0])

    def test_thin_book_blocks(self):
        d = decide(cand(available_size=2), self.limits, self.state, self.kill)
        self.assertEqual(d.action, "SKIP")

    def test_loss_pauses_bot(self):
        pos = self.state.open_position("x", "football", 2, 0.98, 0.0, T0)
        self.state.settle(pos, "loss")
        self.assertTrue(self.state.paused)
        self.assertEqual(decide(cand(), self.limits, self.state, self.kill).action, "SKIP")

    def test_daily_loss_limit(self):
        self.limits.pause_on_loss = False
        self.state.daily_pnl = -3.0
        self.assertEqual(decide(cand(), self.limits, self.state, self.kill).action, "SKIP")

    def test_open_exposure_cap(self):
        for i in range(8):
            pos = self.state.open_position(f"x{i}", "esports", 2, 1.0, 0.0, T0)
        self.assertEqual(decide(cand(sport="football"), self.limits, self.state, self.kill).action, "SKIP")

    def test_sizing_never_exceeds_stake_cap(self):
        shares = size_shares(self.limits, self.state, "football", 0.97, 1000)
        self.assertLessEqual(shares * 0.97, self.limits.max_stake_per_trade)


class BacktestTests(unittest.TestCase):
    def rec(self, i, settlement="win", hours=0):
        c = cand(market_id=f"m{i}", time=T0 + timedelta(hours=i * 4),
                 sources=(src("a", ended=-30 + i * 240, fetched=-1 + i * 240),
                          src("b", ended=-30 + i * 240, fetched=-1 + i * 240)))
        return c, settlement, c.time + timedelta(hours=2)

    def test_all_wins_make_money(self):
        r = run([self.rec(i) for i in range(5)], Limits())
        self.assertEqual(r.wins, 5)
        self.assertGreater(r.realized_pnl, 0)
        self.assertGreater(r.final_equity, 50.0)

    def test_loss_costs_at_most_stake_and_pauses_same_day(self):
        recs = [self.rec(0, "loss"), self.rec(1)]  # 4h apart, same day
        r = run(recs, Limits())
        self.assertEqual(r.losses, 1)
        self.assertGreaterEqual(r.worst_loss, -2.0 - 1e-9)
        self.assertEqual(r.trades, 1)  # second trade blocked by the pause

    def test_split_counts(self):
        r = run([self.rec(0, "split")], Limits())
        self.assertEqual(r.splits, 1)
        self.assertLess(r.realized_pnl, 0)


if __name__ == "__main__":
    unittest.main()


class ShadowBookTests(unittest.TestCase):
    def test_walk_book_fills_across_levels(self):
        from polysweeper.shadow import walk_book
        asks = [{"price": "0.97", "size": "3"}, {"price": "0.98", "size": "10"}, {"price": "0.999", "size": "50"}]
        vwap, worst, avail = walk_book(asks, 5, 0.995)
        self.assertAlmostEqual(vwap, (3 * 0.97 + 2 * 0.98) / 5)
        self.assertEqual(worst, 0.98)
        self.assertEqual(avail, 13)

    def test_walk_book_thin_returns_none(self):
        from polysweeper.shadow import walk_book
        vwap, worst, avail = walk_book([{"price": "0.97", "size": "2"}, {"price": "0.999", "size": "50"}], 5, 0.995)
        self.assertIsNone(vwap)
        self.assertEqual(avail, 2)


class DashboardTests(unittest.TestCase):
    def test_builds_with_no_data(self):
        import tempfile
        from pathlib import Path
        from polysweeper.dashboard import build
        with tempfile.TemporaryDirectory() as d:
            data = build(Path(d) / "none", Path(d) / "no.json", Path(d) / "no.json")
        self.assertEqual(data["shadow"]["by_rule"]["confirmed"]["kpi"]["entries"], 0)
        self.assertIsNone(data["backtest"])

    def test_counts_entries_and_results(self):
        import json, tempfile
        from pathlib import Path
        from polysweeper.dashboard import build_shadow
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            rows = [
                {"type": "entry", "ts": "2026-10-01T10:00:00+00:00", "key": "a:0", "vwap": 0.97, "event_ended_flag": True},
                {"type": "entry", "ts": "2026-10-01T11:00:00+00:00", "key": "b:0", "vwap": 0.98, "event_ended_flag": False},
                {"type": "settled", "ts": "2026-10-01T12:00:00+00:00", "key": "a:0", "result": "win", "pnl": 0.15},
                {"type": "skip_thin", "ts": "2026-10-01T10:00:00+00:00", "key": "c:0"},
            ]
            (p / "trades.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            s = build_shadow(p)
        k = s["by_rule"]["price_only"]["kpi"]
        self.assertEqual(k["entries"], 2)
        self.assertEqual(k["settled"], 1)
        self.assertEqual(k["wins"], 1)
        self.assertEqual(k["thin"], 1)
        self.assertEqual(s["by_rule"]["price_only"]["timing"]["ended"]["wins"], 1)
        self.assertEqual(s["by_rule"]["confirmed"]["kpi"]["entries"], 0)


class OpenDotaTests(unittest.TestCase):
    def game(self, mid, sid, st, rad, dire, rwin, stype=1):
        return {"match_id": mid, "series_id": sid, "series_type": stype, "start_time": st, "duration": 2400,
                "radiant_name": rad, "dire_name": dire, "radiant_win": rwin, "league_name": "L"}

    def test_complete_bo3_has_winner_and_end(self):
        from polysweeper.results_opendota import build_series
        games = [self.game(1, 9, 1000, "A", "B", True), self.game(2, 9, 4000, "B", "A", False)]
        s = build_series(games)
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["winner"], "A")
        self.assertEqual(s[0]["end"], 4000 + 2400)

    def test_incomplete_bo3_is_skipped(self):
        from polysweeper.results_opendota import build_series
        self.assertEqual(build_series([self.game(1, 9, 1000, "A", "B", True)]), [])

    def test_team_name_matching(self):
        from polysweeper.results_opendota import same_team
        self.assertTrue(same_team("Team Spirit", "Spirit"))
        self.assertTrue(same_team("Natus Vincere", "natus vincere"))
        self.assertFalse(same_team("OG", "Liquid"))

    def test_price_at_uses_last_known(self):
        from polysweeper.dota_end_test import price_at
        h = [[100, 0.5], [200, 0.9], [300, 0.99]]
        self.assertIsNone(price_at(h, 50))
        self.assertEqual(price_at(h, 250), 0.9)


class FootballResultTests(unittest.TestCase):
    def test_extra_time_is_not_a_normal_result(self):
        from polysweeper.results_espn import outcome
        base = {"completed": True, "home_score": 3, "away_score": 4}
        self.assertIsNone(outcome(dict(base, status="STATUS_FINAL_AET")))
        self.assertIsNone(outcome(dict(base, status="STATUS_FINAL_PEN")))
        self.assertEqual(outcome(dict(base, status="STATUS_FULL_TIME")), "away")
        self.assertEqual(outcome({"completed": True, "status": "STATUS_FULL_TIME", "home_score": 1, "away_score": 1}), "draw")

    def test_ambiguous_club_name_fits_both_sides(self):
        from polysweeper.results_espn import same_club
        # "Paris Saint-Germain FC" loosely fits both; the checker must then skip
        self.assertTrue(same_club("Paris Saint-Germain FC", "Paris Saint-Germain"))
        self.assertTrue(same_club("Paris Saint-Germain FC", "Paris FC"))
        self.assertFalse(same_club("Manchester United FC", "Manchester City"))

    def test_estimated_end_uses_stoppage_clock(self):
        from polysweeper.results_espn import estimated_end
        e = estimated_end({"kickoff": "2026-09-20T13:00Z", "clock": "90'+5'"})
        self.assertEqual(e.isoformat(), "2026-09-20T14:52:00+00:00")


class ConfirmerTests(unittest.TestCase):
    def board(self, results):
        return lambda league, day: results

    def test_football_win_maps_to_yes_or_no(self):
        from polysweeper.confirm import Confirmer
        res = [{"kickoff": "2026-09-20T13:00Z", "status": "STATUS_FULL_TIME", "completed": True, "clock": "90'+5'",
                "home": "Manchester City", "away": "Sunderland", "home_score": 5, "away_score": 3}]
        c = Confirmer()
        ev = {"startTime": "2026-09-20T13:00:00Z"}
        m = {"question": "Will Manchester City FC win on 2026-09-20?", "gameStartTime": "2026-09-20 13:00:00+00"}
        idx, _ = c.football("epl", ev, m, ["Yes", "No"], board=self.board(res))
        self.assertEqual(idx, 0)
        m2 = {"question": "Will Sunderland AFC win on 2026-09-20?", "gameStartTime": "2026-09-20 13:00:00+00"}
        idx2, _ = c.football("epl", ev, m2, ["Yes", "No"], board=self.board(res))
        self.assertEqual(idx2, 1)
        m3 = {"question": "Will Manchester City FC vs. Sunderland AFC end in a draw?", "gameStartTime": "2026-09-20 13:00:00+00"}
        idx3, _ = c.football("epl", ev, m3, ["Yes", "No"], board=self.board(res))
        self.assertEqual(idx3, 1)

    def test_football_extra_time_not_confirmed(self):
        from polysweeper.confirm import Confirmer
        res = [{"kickoff": "2026-03-19T20:00Z", "status": "STATUS_FINAL_AET", "completed": True, "clock": "120'",
                "home": "AS Roma", "away": "Bologna", "home_score": 3, "away_score": 4}]
        m = {"question": "Will Bologna FC 1909 win on 2026-03-19?", "gameStartTime": "2026-03-19 20:00:00+00"}
        idx, why = Confirmer().football("uel", {}, m, ["Yes", "No"], board=self.board(res))
        self.assertIsNone(idx)

    def test_dota_series_winner(self):
        from polysweeper.confirm import Confirmer
        series = [{"teams": ["Team Spirit", "1win"], "winner": "Team Spirit", "start": 1790000000, "end": 1790007000}]
        ev = {"title": "Dota 2: Team Spirit vs 1win (BO3) - BLAST", "startTime": "2026-09-21T13:33:20Z"}
        idx, _ = Confirmer().dota(ev, ["Team Spirit", "1win"], series=series)
        self.assertEqual(idx, 0)
        idx2, _ = Confirmer().dota(ev, ["Team Spirit", "1win"], series=[])
        self.assertIsNone(idx2)

    def test_unknown_league_has_no_source(self):
        from polysweeper.confirm import Confirmer
        idx, why = Confirmer().winner_index("cs2", {}, {}, ["A", "B"])
        self.assertIsNone(idx)


class ShadowRobustnessTests(unittest.TestCase):
    def make(self, tmp):
        import polysweeper.shadow as sh
        from polysweeper.config import Limits
        sh.OUT = __import__("pathlib").Path(tmp)
        sh.leagues = lambda: {"cs2": {"series": "1"}}
        return sh, sh.Shadow(["cs2"], Limits.from_json("config.json"))

    def test_bad_market_does_not_stop_the_round(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            sh, s = self.make(d)
            s.markets = {"m1": {"league": "cs2", "event": {"id": "e1"}, "market": {}, "tokens": ["t1"], "outcomes": ["A"]},
                         "m2": {"league": "cs2", "event": {"id": "e2"}, "market": {}, "tokens": ["t2"], "outcomes": ["B"]}}
            calls = []
            def boom(mid, info, books):
                calls.append(mid)
                if mid == "m1":
                    raise ValueError("bad reply")
            s.poll_market = boom
            s.refresh_states = lambda: None
            s.fetch_books = lambda: {}
            s.poll()
            self.assertEqual(calls, ["m1", "m2"])        # m2 still processed
            self.assertEqual(s.counters["errors"], 1)

    def test_batched_books_are_keyed_by_token(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            sh, s = self.make(d)
            s.markets = {"m1": {"league": "cs2", "event": {"id": "e1"}, "market": {}, "tokens": ["11", "22"], "outcomes": ["A", "B"]}}
            sh.post_json = lambda url, payload: [{"asset_id": "11", "asks": []}, {"asset_id": "22", "asks": []}]
            books = s.fetch_books()
            self.assertEqual(sorted(books), ["11", "22"])

    def test_late_band_is_logged_but_not_bought(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            sh, s = self.make(d)
            info = {"league": "cs2", "event": {"id": "e1", "ended": True}, "market": {"question": "q"},
                    "tokens": ["11", "22"], "outcomes": ["A", "B"]}
            s.markets = {"m1": info}
            s.confirmer.winner_index = lambda *a: (0, "test source")
            books = {"11": {"asks": [{"price": "0.998", "size": "50"}], "bids": [{"price": "0.996", "size": "50"}]},
                     "22": {"asks": [{"price": "0.01", "size": "50"}], "bids": []}}
            s.poll_market("m1", info, books)
            self.assertEqual(s.counters["entries"], 0)          # 0.998 is above the buy band
            self.assertEqual(s.counters["snapshots"], 1)        # but it was recorded
            ev = [json.loads(l) for l in open(f"{d}/events.jsonl") if l.strip()]
            self.assertTrue(any(e.get("type") == "confirmed" for e in ev))   # and the result was checked


class BookSanityTests(unittest.TestCase):
    def test_both_sides_expensive_is_junk(self):
        from polysweeper.shadow import book_problem
        stats = {0: (0.97, 0.95, [], []), 1: (0.97, 0.95, [], [])}
        self.assertIsNotNone(book_problem(0, stats))

    def test_no_bids_is_junk(self):
        from polysweeper.shadow import book_problem
        stats = {0: (0.97, None, [], []), 1: (0.03, 0.02, [], [])}
        self.assertIsNotNone(book_problem(0, stats))

    def test_normal_book_is_fine(self):
        from polysweeper.shadow import book_problem
        stats = {0: (0.97, 0.96, [], []), 1: (0.04, 0.03, [], [])}
        self.assertIsNone(book_problem(0, stats))


class RefreshWindowTests(unittest.TestCase):
    def test_uses_match_start_not_listing_date(self):
        import tempfile, json
        from datetime import datetime, timedelta, timezone
        import polysweeper.shadow as sh
        from polysweeper.config import Limits
        with tempfile.TemporaryDirectory() as d:
            sh.OUT = __import__("pathlib").Path(d)
            sh.leagues = lambda: {"lol": {"series": "1"}}
            s = sh.Shadow(["lol"], Limits.from_json("config.json"))
            now = datetime.now(timezone.utc)
            mk = {"id": "m1", "sportsMarketType": "moneyline", "acceptingOrders": True,
                  "clobTokenIds": json.dumps(["a", "b"]), "outcomes": json.dumps(["X", "Y"])}
            listed_days_ago = {"id": "e1", "startDate": (now - timedelta(days=5)).isoformat(),
                               "startTime": (now - timedelta(minutes=30)).isoformat(), "live": True, "ended": False, "markets": [mk]}
            far_future = dict(listed_days_ago, id="e2", startTime=(now + timedelta(days=2)).isoformat(),
                              markets=[dict(mk, id="m2")])
            s.open_events = lambda sid: [listed_days_ago, far_future]
            s.refresh()
            self.assertEqual(sorted(s.markets), ["m1"])   # listed 5 days ago but playing now -> watched


class ScoreCheckTests(unittest.TestCase):
    def test_sep30_loss_is_blocked(self):
        from polysweeper.scorecheck import allows
        e = {"title": "Counter-Strike: EAC Extra vs MASONIC (BO1) - Dust2.dk Ligaen Regular Season", "score": "000-000|0-1|Bo1"}
        self.assertEqual(allows(e, ["EAC Extra", "MASONIC"], 0, "esports"), "against")
        self.assertEqual(allows(e, ["EAC Extra", "MASONIC"], 1, "esports"), "agree")

    def test_series_not_finished_is_unknown(self):
        from polysweeper.scorecheck import allows
        e = {"title": "LoL: A vs B (BO3) - X", "score": "000-000|1-1|Bo3"}
        self.assertEqual(allows(e, ["A", "B"], 0, "esports"), "unknown")
        e["score"] = "000-000|2-0|Bo5"
        self.assertEqual(allows(e, ["A", "B"], 0, "esports"), "unknown")

    def test_outcome_order_differs_from_title(self):
        from polysweeper.scorecheck import allows
        e = {"title": "Valorant: A vs B (BO3) - X", "score": "000-000|2-1|Bo3"}
        self.assertEqual(allows(e, ["B", "A"], 1, "esports"), "agree")
        self.assertEqual(allows(e, ["B", "A"], 0, "esports"), "against")

    def test_names_not_matching_is_unknown(self):
        from polysweeper.scorecheck import allows
        e = {"title": "CS2: Team A vs B (BO3) - X", "score": "000-000|2-0|Bo3"}
        self.assertEqual(allows(e, ["A", "B"], 0, "esports"), "unknown")

    def test_tennis(self):
        from polysweeper.scorecheck import allows, tennis_score
        e = {"title": "Curitiba: Guido Justo vs Gonzalo Villanueva", "score": "6-2, 4-6, 7-6(7-4)"}
        self.assertEqual(allows(e, ["Guido Justo", "Gonzalo Villanueva"], 0, "tennis"), "agree")
        e["score"] = "6-2, 4-6, 3-2"            # third set still being played
        self.assertEqual(allows(e, ["Guido Justo", "Gonzalo Villanueva"], 0, "tennis"), "unknown")
        self.assertEqual(tennis_score("7-5, 7-6(9-7)"), (2, 0, 2))


class ShadowScoreRuleTests(unittest.TestCase):
    def test_score_rule_buys_winner_and_blocks_loser(self):
        import tempfile, json, pathlib
        import polysweeper.shadow as sh
        from polysweeper.config import Limits
        with tempfile.TemporaryDirectory() as d:
            sh.OUT = pathlib.Path(d)
            sh.leagues = lambda: {"cs2": {"series": "1"}}
            s = sh.Shadow(["cs2"], Limits.from_json("config.json"))
            s.confirmer.winner_index = lambda *a: (None, "no source")
            ev = {"id": "e", "title": "Counter-Strike: A vs B (BO3) - X", "score": "000-000|2-0|Bo3", "live": False, "ended": True}
            info = {"league": "cs2", "event": ev, "tokens": ["ta", "tb"], "outcomes": ["A", "B"],
                    "market": {"id": "m", "question": "A vs B"}}
            book = lambda ask, bid: {"asks": [{"price": str(ask), "size": "50"}], "bids": [{"price": str(bid), "size": "50"}]}
            s.poll_market("m", info, {"ta": book(0.97, 0.95), "tb": book(0.02, 0.01)})
            rows = [json.loads(l) for l in (pathlib.Path(d) / "trades.jsonl").read_text().splitlines()]
            score_buys = [r for r in rows if r.get("rule") == "score"]
            self.assertEqual([r["outcome"] for r in score_buys], ["A"])
            self.assertEqual(score_buys[0]["score_check"], "agree")
            # now a stale ask on the LOSER that passes the junk filter: check 2 must block it
            ev2 = dict(ev, id="e2", score="000-000|0-2|Bo3")
            s.poll_market("m2", dict(info, event=ev2, market={"id": "m2", "question": "A vs B"}),
                          {"ta": book(0.97, 0.95), "tb": book(0.02, 0.01)})
            rows = [json.loads(l) for l in (pathlib.Path(d) / "trades.jsonl").read_text().splitlines()]
            self.assertFalse([r for r in rows if r.get("rule") == "score" and r["market_id"] == "m2"])
            self.assertTrue([r for r in rows if r["type"] == "skip_score_against"])
            price_only_m2 = [r for r in rows if r.get("rule") == "price_only" and r["market_id"] == "m2"]
            self.assertEqual(price_only_m2[0]["score_check"], "against")   # the old rule would have bought the loser


class EndWatchTests(unittest.TestCase):
    def test_records_window_after_score_decided(self):
        from polysweeper.endwindow import EndWatch
        out = []
        w = EndWatch(out.append, say=lambda *_: None)
        info = {"league": "cs2", "outcomes": ["A", "B"], "event": {"title": "Counter-Strike: A vs B (BO3) - X", "score": "000-000|1-1|Bo3"}}
        ask = lambda p, n: {"price": str(p), "size": str(n)}
        st = lambda a: {0: (a, 0.95, [ask(a, 40)], []), 1: (0.05, 0.01, [ask(0.05, 10)], [])}
        w.observe("m", info, {"ended": False}, st(0.80), 1000)          # still 1-1: nothing recorded
        self.assertEqual(w.open, {})
        info["event"]["score"] = "000-000|2-1|Bo3"
        w.observe("m", info, {"ended": False}, st(0.97), 1010)          # decided, A ask 0.97
        w.observe("m", info, {"ended": True}, st(0.998), 1070)          # ended flag 60 s later
        w.observe("m", info, {"ended": True}, st(0.999), 1100)
        w.observe("m", info, {"ended": True}, st(0.999), 1010 + 15 * 60)
        self.assertEqual(len(out), 1)
        r = out[0]
        self.assertEqual((r["first_trigger"], r["winner_idx"], r["decided_before_ended_by_s"]), ("score_decided", 0, 60.0))
        self.assertEqual((r["ask_at_start"], r["max_shares_096_0995"], r["max_shares_0995_0999"], r["seconds_until_ask_0999"]),
                         (0.97, 40.0, 40.0, 90.0))
