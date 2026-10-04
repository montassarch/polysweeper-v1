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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            data = build(Path(d) / "none", Path(d) / "no.json", Path(d) / "no.json")
        self.assertEqual(data["shadow"]["by_rule"]["confirmed"]["kpi"]["entries"], 0)
        self.assertIsNone(data["backtest"])

    def test_counts_entries_and_results(self):
        import json, tempfile
        from pathlib import Path
        from polysweeper.dashboard import build_shadow
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
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

    def test_fill_check_second_look_and_public_trades(self):
        import tempfile, json
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            sh, s = self.make(d)
            self.addCleanup(setattr, sh, "post_json", sh.post_json)
            self.addCleanup(setattr, sh, "get_json", sh.get_json)
            t0 = 1000.0
            s.followups = [{"key": "k1", "rule": "score", "token": "t1", "t0": t0, "cond": "c1", "worst": 0.99, "shares": 5},
                           {"key": "k2", "rule": "score", "token": "t2", "t0": t0, "cond": "c2", "worst": 0.99, "shares": 5}]
            books = {"t1": [{"price": "0.99", "size": "7"}], "t2": [{"price": "0.995", "size": "50"}]}
            sh.post_json = lambda url, payload, tries=4: [{"asks": books[payload[0]["token_id"]]}]
            trades = {"c1": [], "c2": [{"asset": "t2", "side": "BUY", "price": 0.99, "size": 9, "timestamp": 1003},
                                     {"asset": "t2", "side": "BUY", "price": 0.99, "size": 4, "timestamp": 900}]}
            sh.get_json = lambda url, tries=5: trades[url.split("market=")[1].split("&")[0]]
            s.check_fills(t0 + 3)
            self.assertEqual(len(s.followups), 2)      # trades not looked at yet
            s.check_fills(t0 + 11)
            self.assertEqual(s.followups, [])
            s.trade_f.flush()
            rows = [json.loads(l) for l in open(s.trade_f.name) if '"fill_check"' in l]
            v = {r["key"]: r for r in rows}
            self.assertEqual(v["k1"]["verdict"], "likely filled")
            self.assertEqual(v["k2"]["verdict"], "taken by others")
            self.assertEqual(v["k2"]["others_bought_shares"], 9)
            s.close()

    def test_bad_market_does_not_stop_the_round(self):
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            sh, s = self.make(d)
            s.markets = {"m1": {"league": "cs2", "event": {"id": "e1"}, "market": {}, "tokens": ["11", "22"], "outcomes": ["A", "B"]}}
            sh.post_json = lambda url, payload: [{"asset_id": "11", "asks": []}, {"asset_id": "22", "asks": []}]
            books = s.fetch_books()
            self.assertEqual(sorted(books), ["11", "22"])

    def test_late_band_is_logged_but_not_bought(self):
        import tempfile, json
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
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
        self.assertEqual((r["seconds_observed"], r["seconds_watched"]), (90.0, 900.0))   # last change vs real watch time

    def test_ignores_matches_already_over_and_never_reopens(self):
        from polysweeper.endwindow import EndWatch
        out = []
        w = EndWatch(out.append, say=lambda *_: None)
        info = {"league": "cs2", "outcomes": ["A", "B"], "event": {"title": "Counter-Strike: A vs B (BO3) - X", "score": "000-000|2-0|Bo3"}}
        st = {0: (None, 0.999, [], []), 1: (0.01, None, [{"price": "0.01", "size": "9"}], [])}
        for t in (0, 100, 2000):
            w.observe("late", info, {"ended": True}, st, t)        # first seen already decided
        self.assertEqual((w.open, out), ({}, []))
        football = {"league": "epl", "outcomes": ["Yes", "No"], "event": {"title": "X vs Y", "score": "0-0"}}
        half = {0: (0.51, 0.50, [{"price": "0.51", "size": "9"}], []), 1: (0.51, 0.49, [], [])}
        w.observe("void", football, {"ended": False}, half, 0)
        w.observe("void", football, {"ended": True}, half, 10)     # cancelled, 50/50: no clear winner
        w.close("void", "test")
        self.assertEqual(out, [])


class OneBuyPerMatchTests(unittest.TestCase):
    """B7: at most 1 pretend buy per match and rule (shadow bought both teams in 2 CS2 matches)."""
    def make(self, tmp):
        import pathlib
        import polysweeper.shadow as sh
        sh.OUT = pathlib.Path(tmp)
        sh.leagues = lambda: {"cs2": {"series": "1"}}
        s = sh.Shadow(["cs2"], Limits.from_json("config.json"))
        s.confirmer.winner_index = lambda *a: (None, "no source")
        return s

    def rows(self, d):
        import json, pathlib
        return [json.loads(l) for l in (pathlib.Path(d) / "trades.jsonl").read_text().splitlines()]

    def test_comeback_does_not_buy_the_other_team(self):
        import tempfile
        book = lambda ask, bid: {"asks": [{"price": str(ask), "size": "50"}], "bids": [{"price": str(bid), "size": "50"}]}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            s = self.make(d)
            ev = {"id": "e", "title": "Counter-Strike: A vs B (BO3) - X", "score": "000-000|1-0|Bo3", "live": True, "ended": False}
            info = {"league": "cs2", "event": ev, "tokens": ["ta", "tb"], "outcomes": ["A", "B"],
                    "market": {"id": "m", "question": "A vs B"}}
            s.poll_market("m", info, {"ta": book(0.96, 0.95), "tb": book(0.05, 0.03)})      # A leads 1-0
            info["event"] = dict(ev, score="000-000|1-1|Bo3")
            s.poll_market("m", info, {"ta": book(0.03, 0.02), "tb": book(0.98, 0.97)})      # B comes back
            rows = self.rows(d)
            self.assertEqual([r["outcome"] for r in rows if r["type"] == "entry"], ["A"])
            skips = [r for r in rows if r["type"] == "skip_second_buy"]
            self.assertEqual([(r["outcome"], r["reason"]) for r in skips], [("B", "already bought A in this match")])
            s.poll_market("m", info, {"ta": book(0.03, 0.02), "tb": book(0.98, 0.97)})      # logged once only
            self.assertEqual(len([r for r in self.rows(d) if r["type"] == "skip_second_buy"]), 1)

    def test_football_draw_market_counts_as_same_match(self):
        import tempfile
        book = lambda ask, bid: {"asks": [{"price": str(ask), "size": "50"}], "bids": [{"price": str(bid), "size": "50"}]}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            s = self.make(d)
            ev = {"id": "e9", "title": "X vs Y", "score": "1-0", "live": True, "ended": False}
            home = {"league": "cs2", "event": ev, "tokens": ["h1", "h2"], "outcomes": ["Yes", "No"], "market": {"id": "home", "question": "X win?"}}
            draw = {"league": "cs2", "event": ev, "tokens": ["d1", "d2"], "outcomes": ["Yes", "No"], "market": {"id": "draw", "question": "Draw?"}}
            s.poll_market("home", home, {"h1": book(0.96, 0.95), "h2": book(0.05, 0.03)})
            s.poll_market("draw", draw, {"d2": book(0.97, 0.96), "d1": book(0.04, 0.03)})
            self.assertEqual([r["market_id"] for r in self.rows(d) if r["type"] == "entry"], ["home"])

    def test_buy_made_before_the_rule_still_counts(self):
        import tempfile
        book = lambda ask, bid: {"asks": [{"price": str(ask), "size": "50"}], "bids": [{"price": str(bid), "size": "50"}]}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            s = self.make(d)
            s.state["pending"]["m:0"] = {"rule": "price_only", "market_id": "m", "outcome": "A"}   # old state, no event id
            s.state["entered"].append("m:0")
            ev = {"id": "e", "title": "Counter-Strike: A vs B (BO3) - X", "score": "000-000|1-1|Bo3", "live": True, "ended": False}
            info = {"league": "cs2", "event": ev, "tokens": ["ta", "tb"], "outcomes": ["A", "B"], "market": {"id": "m", "question": "A vs B"}}
            s.poll_market("m", info, {"ta": book(0.03, 0.02), "tb": book(0.98, 0.97)})
            self.assertEqual([r["type"] for r in self.rows(d)], ["skip_second_buy"])


class EndWindowReportTests(unittest.TestCase):
    def test_leaves_out_old_rows_and_repeats(self):
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location("ewr", pathlib.Path(__file__).parent.parent / "end_window_report.py")
        ewr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ewr)
        rows = [{"ts": "2026-10-03T14:07:00", "market_id": "old", "winner_idx": 0},
                {"ts": "2026-10-03T15:00:00", "market_id": "a", "winner_idx": 1},
                {"ts": "2026-10-03T15:01:00", "market_id": "football", "winner_idx": None},   # no score: kept
                {"ts": "2026-10-03T15:05:00", "market_id": "a", "winner_idx": 1}]
        self.assertEqual([r["market_id"] for r in ewr.usable(rows)], ["a", "football"])

    def test_keeps_the_longest_watch_of_a_match(self):
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location("ewr", pathlib.Path(__file__).parent.parent / "end_window_report.py")
        ewr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ewr)
        rows = [{"ts": "2026-10-03T20:02:55", "market_id": "spirit", "seconds_watched": 32.0, "shares": 2},
                {"ts": "2026-10-03T20:05:00", "market_id": "b", "seconds_observed": 900, "shares": 7},
                {"ts": "2026-10-03T20:12:58", "market_id": "spirit", "seconds_watched": 532.9, "shares": 40918},
                {"ts": "2026-10-03T20:20:00", "market_id": "spirit", "seconds_watched": 10.0, "shares": 1}]
        self.assertEqual([(r["market_id"], r["shares"]) for r in ewr.usable(rows)], [("spirit", 40918), ("b", 7)])


class AutopilotNotesOnlyTests(unittest.TestCase):
    """A notes-only update is pulled without stopping shadow mode; anything in code/ restarts it."""
    def setUp(self):
        import tempfile, pathlib, subprocess
        import polysweeper.autopilot as ap
        self.ap, self.tmp = ap, tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = pathlib.Path(self.tmp.name)
        self.saved = (ap.REPO, ap.SHADOW_DIR, ap.LOG)
        ap.SHADOW_DIR, ap.LOG = root, root / "autopilot.log"
        def g(where, *args):
            subprocess.run(["git", "-C", str(where), "-c", "user.name=t", "-c", "user.email=t@t",
                            "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)
        self.g = g
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(root / "origin.git")], check=True)
        for name in ("dev", "pc"):
            subprocess.run(["git", "clone", "-q", str(root / "origin.git"), str(root / name)], check=True, capture_output=True)
        self.dev, self.pc = root / "dev", root / "pc"
        self.write(self.dev, "code/data/shadow/trades.jsonl", "one\n")
        self.write(self.dev, "code/polysweeper/x.py", "x = 1\n")
        self.write(self.dev, "Notes/a.md", "note\n")
        self.write(self.dev, ".gitignore", "app/bin/\n")
        g(self.dev, "add", "-A"); g(self.dev, "commit", "-qm", "init"); g(self.dev, "push", "-q", "origin", "HEAD:main")
        g(self.pc, "pull", "-q", "origin", "main")
        for k, v in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            g(self.pc, "config", k, v)
        ap.REPO = self.pc
        self.write(self.pc, "code/data/shadow/trades.jsonl", "one\ntwo (written by shadow mode, not committed)\n")

    def tearDown(self):
        self.ap.REPO, self.ap.SHADOW_DIR, self.ap.LOG = self.saved
        self.tmp.cleanup()

    def write(self, repo, rel, text):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def push_from_dev(self, rel, text):
        self.write(self.dev, rel, text)
        self.g(self.dev, "commit", "-qam", "update")
        self.g(self.dev, "pull", "-q", "--rebase", "origin", "main")      # the PC may have pushed data meanwhile
        self.g(self.dev, "push", "-q", "origin", "HEAD:main")

    def test_notes_only_update_is_pulled_and_data_kept(self):
        self.push_from_dev("Notes/a.md", "note v2\n")
        self.assertTrue(self.ap.update_available())
        self.assertEqual(self.ap.incoming_files(), {"Notes/a.md"})
        self.assertTrue(self.ap.update_without_restart())
        self.assertEqual((self.pc / "Notes/a.md").read_text(), "note v2\n")
        self.assertIn("two", (self.pc / "code/data/shadow/trades.jsonl").read_text())   # shadow's new line untouched
        self.assertFalse(self.ap.update_available())

    def test_code_update_needs_restart(self):
        self.push_from_dev("code/polysweeper/x.py", "x = 2\n")
        self.assertTrue(self.ap.update_available())
        self.assertFalse(self.ap.update_without_restart())
        self.assertEqual((self.pc / "code/polysweeper/x.py").read_text(), "x = 1\n")      # left for the normal path

    def test_local_note_edit_in_the_way_falls_back(self):
        self.push_from_dev("Notes/a.md", "note v2\n")
        self.write(self.pc, "Notes/a.md", "edited on the PC\n")
        self.assertTrue(self.ap.update_available())
        self.assertFalse(self.ap.update_without_restart())
        self.assertEqual((self.pc / "Notes/a.md").read_text(), "edited on the PC\n")      # nothing changed

    def test_daily_folder_is_synced(self):
        import subprocess
        self.write(self.pc, "code/data/shadow/daily/2026-10-03.jsonl", '{"type": "score"}\n')
        self.ap.sync_data()
        out = subprocess.run(["git", "-C", str(self.pc.parent / "origin.git"), "log", "-1", "--name-only", "--format=%s", "main"],
                             capture_output=True, text=True).stdout
        self.assertIn("shadow data (autopilot)", out)
        self.assertIn("code/data/shadow/daily/2026-10-03.jsonl", out)
        self.assertIn("code/data/shadow/trades.jsonl", out)

    def test_pc_note_edits_no_longer_block_updates(self):
        """What happened on 2026-10-03: notes edited on the PC (not committed) blocked every pull."""
        import subprocess
        self.write(self.pc, "Notes/a.md", "edited on the PC\n")             # local, not committed
        self.write(self.dev, "Notes/a.md", "note v2 from GitHub\n")
        self.push_from_dev("code/polysweeper/x.py", "x = 2\n")             # plus a code update
        self.assertTrue(self.ap.update_available())
        changed = self.ap.pull()
        self.assertIn("code/polysweeper/x.py", changed)
        self.assertEqual((self.pc / "code/polysweeper/x.py").read_text(), "x = 2\n")
        self.assertFalse(self.ap.behind())
        log = subprocess.run(["git", "-C", str(self.pc), "log", "--format=%s"], capture_output=True, text=True).stdout
        self.assertIn("Edits made on the PC (kept by autopilot)", log)     # the PC's edit is kept in history
        self.assertIn("two", (self.pc / "code/data/shadow/trades.jsonl").read_text())   # shadow data untouched

    def test_pc_code_edits_are_put_aside(self):
        import subprocess
        self.write(self.pc, "code/polysweeper/x.py", "x = 99  # edited on the PC\n")
        self.push_from_dev("Notes/a.md", "note v2\n")
        self.ap.update_available()
        self.ap.pull()
        self.assertEqual((self.pc / "code/polysweeper/x.py").read_text(), "x = 1\n")   # runs GitHub's code
        stash = subprocess.run(["git", "-C", str(self.pc), "stash", "list"], capture_output=True, text=True).stdout
        self.assertIn("code edits made on the PC", stash)

    def test_file_in_the_way_is_renamed_not_deleted(self):
        self.write(self.dev, "Notes/new.md", "from GitHub\n")
        self.g(self.dev, "add", "-A")
        self.push_from_dev("code/polysweeper/x.py", "x = 3\n")
        self.write(self.pc, "Notes/new.md", "an untracked file in the way\n")
        self.assertTrue(self.ap.update_available())
        self.assertIn("Notes/new.md", self.ap.pull())
        self.assertEqual((self.pc / "Notes/new.md").read_text(), "from GitHub\n")
        copies = list((self.pc / "Notes").glob("new.md.pc-copy-*"))
        self.assertEqual([c.read_text() for c in copies], ["an untracked file in the way\n"])

    def test_failed_update_is_reported_not_looped(self):
        """If an update still cannot come in (here: GitHub unreachable after the check), apply_update
        says so and shadow mode is running again; the loop then waits 30 minutes before trying again."""
        import shutil
        self.push_from_dev("code/polysweeper/x.py", "x = 3\n")
        class FakeShadow:
            starts = stops = 0
            def stop(self): FakeShadow.stops += 1
            def start(self): FakeShadow.starts += 1
        self.assertTrue(self.ap.update_available())
        shutil.move(str(self.pc.parent / "origin.git"), str(self.pc.parent / "gone.git"))
        self.assertEqual(self.ap.apply_update(FakeShadow(), "code/polysweeper/autopilot.py"), "failed")
        self.assertEqual((FakeShadow.stops, FakeShadow.starts), (1, 1))

    def test_owner_stop_file_is_never_cleared_by_the_autopilot(self):
        """2026-10-03: in a restart loop the autopilot deleted the owner's stop file, so
        stop_shadow.bat seemed to do nothing."""
        import sys
        ap = self.ap
        saved = ap.STOP
        ap.STOP = self.pc.parent / "STOP"
        try:
            waiter = [sys.executable, "-c", "import os,sys,time\nwhile not os.path.exists(sys.argv[1]): time.sleep(0.05)", str(ap.STOP)]
            sh = ap.ShadowProcess(waiter)
            sh.start()
            sh.stop(wait=10)                                  # an update: the autopilot's own stop file
            self.assertFalse(ap.STOP.exists())                # ...is cleaned up
            ap.STOP.write_text("stop\r\n")                    # the owner's stop_shadow.bat
            self.assertTrue(ap.owner_stop())
            sh.start()                                        # the update path starting shadow again
            sh.stop(wait=10)
            self.assertTrue(ap.STOP.exists() and ap.owner_stop())   # the owner's request survives
        finally:
            ap.STOP = saved

    def test_desktop_app_is_installed_and_updated_from_the_build_branch(self):
        import os
        ap = self.ap
        saved = ap.APP_EXE
        ap.APP_EXE = self.pc / "app" / "bin" / "PolySweeper.exe"
        try:
            ap.install_app()                                          # no build branch yet: nothing, no error
            self.assertFalse(ap.APP_EXE.exists())
            def publish(content):
                self.g(self.dev, "checkout", "-q", "--orphan", "app-build-tmp")
                self.g(self.dev, "rm", "-rfq", ".")
                (self.dev / "PolySweeper.exe").write_bytes(content)
                self.g(self.dev, "add", "PolySweeper.exe")
                self.g(self.dev, "commit", "-qm", "build")
                self.g(self.dev, "push", "-qf", "origin", "HEAD:app-build")
                self.g(self.dev, "checkout", "-qf", "main" if "main" in self.branches() else "master")
                self.g(self.dev, "branch", "-qD", "app-build-tmp")
            v1, v2 = os.urandom(1_200_000), os.urandom(1_300_000)
            publish(v1)
            ap.install_app()
            self.assertEqual(ap.APP_EXE.read_bytes(), v1)
            mtime = ap.APP_EXE.stat().st_mtime_ns
            ap.install_app()                                          # same build: not rewritten
            self.assertEqual(ap.APP_EXE.stat().st_mtime_ns, mtime)
            publish(v2)
            ap.install_app()
            self.assertEqual(ap.APP_EXE.read_bytes(), v2)
            import subprocess
            status = subprocess.run(["git", "-C", str(self.pc), "status", "--porcelain"], capture_output=True, text=True).stdout
            self.assertNotIn("app/bin", status)                       # git ignores the installed app
        finally:
            ap.APP_EXE = saved

    def branches(self):
        import subprocess
        return subprocess.run(["git", "-C", str(self.dev), "branch"], capture_output=True, text=True).stdout

    def test_bad_update_goes_back_on_purpose(self):
        """Go-back test: a version that stops shadow mode from writing live.json is undone by itself."""
        import sys, time
        ap = self.ap
        saved = (ap.LIVE, ap.GOOD, ap.HOLD, ap.STOP, ap.VERIFY_SECONDS)
        d = self.pc.parent
        ap.LIVE, ap.GOOD, ap.HOLD, ap.STOP, ap.VERIFY_SECONDS = d / "live.json", d / "good", d / "hold", d / "STOP", 1.5
        ok_file = self.pc / "code" / "fake_ok.txt"
        script = ("import os,sys,time\n"
                  "ok, live, stop = sys.argv[1:4]\n"
                  "if not os.path.exists(ok): sys.exit(1)\n"            # the 'bad version': crashes at start
                  "while not os.path.exists(stop):\n"
                  "    open(live, 'w').write('{}'); time.sleep(0.2)\n")
        sh = ap.ShadowProcess([sys.executable, "-c", script, str(ok_file), str(ap.LIVE), str(ap.STOP)])
        try:
            self.write(self.dev, "code/fake_ok.txt", "ok\n")
            self.g(self.dev, "add", "-A")
            self.push_from_dev("code/fake_ok.txt", "ok\n")
            ap.update_available(); ap.pull()
            sh.start()
            v = ap.Verifier()
            v.start(time.time())
            time.sleep(1.8)
            self.assertEqual(v.tick(sh, time.time()), "good")
            good = ap.head()
            self.assertEqual(ap._read(ap.GOOD), good)
            # the bad update: removes the file the stand-in needs
            self.g(self.dev, "rm", "-q", "code/fake_ok.txt"); self.g(self.dev, "commit", "-qm", "bad")
            self.g(self.dev, "pull", "-q", "--rebase", "origin", "main")
            self.g(self.dev, "push", "-q", "origin", "HEAD:main")
            self.assertTrue(ap.update_available())
            self.assertEqual(ap.apply_update(sh, "code/polysweeper/autopilot.py"), "ok")
            v.start(time.time())
            time.sleep(1.8)
            self.assertEqual(v.tick(sh, time.time()), "went back")
            self.assertTrue(ok_file.exists())                         # code is back to the good version
            self.assertTrue(ap.held())
            self.assertIn("two", (self.pc / "code/data/shadow/trades.jsonl").read_text())   # data kept
            time.sleep(1.8)
            self.assertEqual(v.tick(sh, time.time()), "good")         # and shadow mode runs again
            self.assertEqual(ap._read(ap.GOOD), good)                 # the bad version is never marked good
            self.push_from_dev("Notes/a.md", "note during hold\n")
            ap.update_available()
            self.assertFalse(ap.code_change_since_hold())             # notes only: keep holding
            self.write(self.dev, "code/fake_ok.txt", "fixed\n")        # a real fix arrives
            self.g(self.dev, "add", "-A")
            self.push_from_dev("code/fake_ok.txt", "fixed\n")
            ap.update_available()
            self.assertTrue(ap.code_change_since_hold())
            ap.leave_hold()
            self.assertFalse(ap.held())
            self.assertIn("code/fake_ok.txt", ap.pull())
        finally:
            sh.stop(wait=5)
            ap.LIVE, ap.GOOD, ap.HOLD, ap.STOP, ap.VERIFY_SECONDS = saved

    def test_unknown_changes_count_as_code(self):
        self.assertTrue(self.ap.touches_code(None))
        self.assertFalse(self.ap.touches_code({"PolySweeper-V1/24-Task-List.md", "CLAUDE.md"}))
        self.assertTrue(self.ap.touches_code({"CLAUDE.md", "code/config.json"}))


class LiveFeedTests(unittest.TestCase):
    """The live order-book feed (websocket) and what it remembers."""
    def test_frames_round_trip(self):
        from polysweeper import livefeed as lf
        for n in (0, 5, 125, 126, 70000):
            for mask in (True, False):
                data = bytes(range(256)) * (n // 256) + bytes(range(n % 256))
                raw = lf.frame(1, data, mask=mask)
                self.assertIsNone(lf.parse(raw[:-1] if n else raw[:1]))     # incomplete: wait for more
                fin, op, payload, used = lf.parse(raw + b"extra")
                self.assertEqual((fin, op, payload, used), (True, 1, data, len(raw)))

    def test_books_changes_trades_and_history(self):
        import json
        from polysweeper.livefeed import LiveFeed
        f = LiveFeed()
        f.handle(json.dumps([{"event_type": "book", "asset_id": "a", "bids": [{"price": "0.95", "size": "10"}],
                              "asks": [{"price": "0.97", "size": "8"}, {"price": "0.998", "size": "50"}]},
                             {"event_type": "book", "asset_id": "b", "buys": [{"price": "0.02", "size": "9"}],
                              "sells": [{"price": "0.05", "size": "9"}]}]), 100.0)
        self.assertEqual((f.top("a"), f.top("b")), ((0.97, 0.95), (0.05, 0.02)))
        # new format: several tokens per message; size is the new total, 0 removes the level
        f.handle(json.dumps({"event_type": "price_change", "market": "m", "price_changes": [
            {"asset_id": "a", "price": "0.97", "size": "0", "side": "SELL"},
            {"asset_id": "a", "price": "0.999", "size": "40", "side": "BUY"}]}), 101.0)
        self.assertEqual(f.top("a"), (0.998, 0.999))
        f.handle(json.dumps({"event_type": "price_change", "asset_id": "b",            # older format
                             "changes": [{"price": "0.04", "size": "3", "side": "SELL"}]}), 102.0)
        self.assertEqual(f.top("b"), (0.04, 0.02))
        f.handle(json.dumps({"event_type": "last_trade_price", "asset_id": "a", "price": "0.998", "size": "6", "side": "BUY"}), 103.0)
        f.handle(json.dumps({"event_type": "last_trade_price", "asset_id": "b", "price": "0.04", "size": "6", "side": "BUY"}), 103.0)
        f.handle("PONG", 104.0)
        self.assertEqual(f.history("a", 0, 200), [(100.0, 0.97, 0.95, 8.0, 50.0), (101.0, 0.998, 0.999, 0.0, 50.0)])
        self.assertEqual(f.history("a", 100.5, 200)[0][0], 100.0)       # starts with the state at t_from
        self.assertEqual(f.history("b", 0, 200), [])                     # not a favourite: no history kept
        self.assertEqual(f.trades("a", 0, 200), [(103.0, 0.998, 6.0, "BUY")])
        self.assertEqual(f.trades("b", 0, 200), [])

    def test_talks_to_a_websocket_server(self):
        """End to end against a small local server: handshake, subscription, a book, a ping,
        and a price change split over two frames."""
        import json, socket, struct, threading, time
        from polysweeper import livefeed as lf
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        got = {}

        def raw(fin, op, payload):
            n = len(payload)
            return bytes([(0x80 if fin else 0) | op]) + (bytes([n]) if n < 126 else bytes([126]) + struct.pack(">H", n)) + payload

        def serve():
            c, _ = srv.accept()
            c.settimeout(5)
            data = b""
            while b"\r\n\r\n" not in data:
                data += c.recv(4096)
            got["request"] = data.split(b"\r\n")[0]
            c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
            buf = bytearray()
            def next_frame():
                while True:
                    f = lf.parse(buf)
                    if f:
                        del buf[:f[3]]
                        return f
                    buf.extend(c.recv(4096))
            got["sub"] = json.loads(next_frame()[2])
            c.sendall(lf.frame(1, json.dumps([{"event_type": "book", "asset_id": "t1", "bids": [{"price": "0.97", "size": "10"}],
                                               "asks": [{"price": "0.98", "size": "20"}]}]).encode(), mask=False))
            c.sendall(lf.frame(9, b"hi", mask=False))
            change = json.dumps({"event_type": "price_change", "market": "m", "price_changes": [
                {"asset_id": "t1", "price": "0.98", "size": "0", "side": "SELL"},
                {"asset_id": "t1", "price": "0.99", "size": "7", "side": "SELL"}]}).encode()
            c.sendall(raw(False, 1, change[:40]) + raw(True, 0, change[40:]))
            while "pong" not in got:
                fin, op, payload, _ = next_frame()
                if op == 10:
                    got["pong"] = payload
            try:
                while c.recv(4096):
                    pass
            except OSError:
                pass
            c.close()

        threading.Thread(target=serve, daemon=True).start()
        feed = lf.LiveFeed(url=f"ws://127.0.0.1:{srv.getsockname()[1]}/ws/market")
        feed.set_tokens(["t1"])
        feed.start()
        end = time.time() + 5
        while time.time() < end and (feed.top("t1") != (0.99, 0.97) or "pong" not in got):
            time.sleep(0.05)
        feed.stop()
        srv.close()
        self.assertEqual(got["request"], b"GET /ws/market HTTP/1.1")
        self.assertEqual(got["sub"], {"assets_ids": ["t1"], "type": "market"})
        self.assertEqual(feed.top("t1"), (0.99, 0.97))
        self.assertEqual(got.get("pong"), b"hi")
        st = feed.status()
        self.assertEqual((st["connected"], st["connects"], st["tokens_with_book"]), (True, 1, 1))
        self.assertEqual(list(feed.hist), ["t1"])                  # history kept for the watched favourite

    def test_no_server_is_not_fatal(self):
        import socket, time
        from polysweeper.livefeed import LiveFeed
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()                                           # nothing listens here
        errors = []
        feed = LiveFeed(url=f"ws://127.0.0.1:{port}/ws/market", on_error=lambda w, e: errors.append(w))
        feed.set_tokens(["t1"])
        feed.start()
        end = time.time() + 3
        while time.time() < end and not errors:
            time.sleep(0.05)
        feed.stop()
        self.assertEqual(errors[:1], ["live feed"])
        self.assertIsNone(feed.top("t1"))
        self.assertFalse(feed.status()["connected"])

    def test_live_summary(self):
        from polysweeper.livefeed import live_summary
        hist = [(995.0, 0.97, 0.95, 10.0, 0.0), (1012.0, None, 0.999, 0.0, 0.0)]
        trades = [(1005.0, 0.97, 5.0, "BUY"), (1011.0, 0.97, 4.0, "BUY"), (1013.0, 0.998, 3.0, "BUY")]
        r = live_summary(hist, trades, 1010.0, 1910.0)
        self.assertEqual((r["live_v1_until_s"], r["live_v1_seconds_after"], r["live_bid099_at_s"]), (2.0, 2.0, 2.0))
        self.assertEqual((r["live_trades_v1_after"], r["live_trades_v1_shares_after"]), (1, 4.0))
        self.assertEqual((r["live_trades_late_after"], r["live_late_until_s"]), (1, None))
        gone = live_summary([(990.0, 0.97, 0.95, 10.0, 0.0), (1004.0, None, 0.999, 0.0, 0.0)], [], 1010.0, 1910.0)
        self.assertEqual((gone["live_v1_until_s"], gone["live_v1_seconds_after"]), (-6.0, 0.0))  # gone before we saw it

    def test_end_window_gets_live_numbers_and_detail(self):
        import json
        from polysweeper.endwindow import EndWatch
        from polysweeper.livefeed import LiveFeed
        feed = LiveFeed()
        feed.stats["connects"] = 1
        feed.handle(json.dumps({"event_type": "book", "asset_id": "ta", "bids": [{"price": "0.95", "size": "10"}],
                                "asks": [{"price": "0.97", "size": "10"}]}), 995.0)
        feed.handle(json.dumps({"event_type": "last_trade_price", "asset_id": "ta", "price": "0.97", "size": "4", "side": "BUY"}), 1011.0)
        feed.handle(json.dumps({"event_type": "price_change", "market": "m", "price_changes": [
            {"asset_id": "ta", "price": "0.97", "size": "0", "side": "SELL"},
            {"asset_id": "ta", "price": "0.999", "size": "50", "side": "BUY"}]}), 1012.0)
        out, detail = [], []
        w = EndWatch(out.append, say=lambda *_: None, live=feed, detail=detail.append)
        info = {"league": "cs2", "outcomes": ["A", "B"], "tokens": ["ta", "tb"],
                "event": {"title": "Counter-Strike: A vs B (BO3) - X", "score": "000-000|1-1|Bo3"}}
        st = {0: (0.97, 0.95, [{"price": "0.97", "size": "10"}], []), 1: (0.05, 0.03, [], [])}
        w.observe("m", info, {"ended": False}, st, 1000)
        info["event"]["score"] = "000-000|2-1|Bo3"
        w.observe("m", info, {"ended": False}, st, 1010)
        w.observe("m", info, {"ended": True}, st, 1010 + 15 * 60)
        r = out[0]
        self.assertEqual((r["live_v1_until_s"], r["live_trades_v1_after"], r["live_bid099_at_s"]), (2.0, 1, 2.0))
        self.assertEqual((detail[0]["type"], detail[0]["winner"], detail[0]["samples"][0][0]), ("end_window_live", "A", -15.0))


class ShadowLiveTests(unittest.TestCase):
    """2-second re-checks for matches near the end, and the score log (daily file)."""
    def make(self, tmp):
        import pathlib
        import polysweeper.shadow as sh
        sh.OUT = pathlib.Path(tmp)
        sh.leagues = lambda: {"cs2": {"series": "1"}}
        s = sh.Shadow(["cs2"], Limits.from_json("config.json"))
        s.confirmer.winner_index = lambda *a: (None, "no source")
        return sh, s

    def daily_rows(self, d):
        import json, pathlib
        return [json.loads(l) for f in sorted((pathlib.Path(d) / "daily").glob("*.jsonl")) for l in f.read_text().splitlines()]

    def test_decided_match_is_checked_at_once(self):
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            sh, s = self.make(d)
            ev = {"id": "e1", "title": "Counter-Strike: A vs B (BO3) - X", "score": "000-000|1-0|Bo3",
                  "live": True, "ended": False, "startTime": "2020-01-01T00:00:00Z"}
            info = {"league": "cs2", "event": ev, "tokens": ["ta", "tb"], "outcomes": ["A", "B"],
                    "market": {"id": "m", "question": "A vs B"}}
            s.markets = {"m": info}
            book = lambda asks, bids: {"asks": [{"price": str(p), "size": "50"} for p in asks],
                                       "bids": [{"price": str(p), "size": "50"} for p in bids]}
            s.poll_market("m", info, {"ta": book([0.999], [0.95]), "tb": book([0.06], [0.01])})   # playing, A bid 0.95
            calls = []
            def gamma(url, tries=5):
                calls.append(tries)
                return [dict(ev, score="000-000|2-0|Bo3")]
            sh.get_json = gamma
            s.fetch_books = lambda mids=None: {"ta": book([], [0.999]), "tb": book([0.01], [])}
            s.fast_tick()
            self.assertEqual(calls, [1])                       # one quick try, no long retries
            self.assertEqual(s.counters["fast_rechecks"], 1)
            self.assertIn("m", s.endwatch.open)                # the end window opened right away
            s.fast_tick()                                      # nothing new: no second re-check, no new row
            self.assertEqual(s.counters["fast_rechecks"], 1)
            rows = self.daily_rows(d)
            self.assertEqual([(r["type"], r["score"]) for r in rows], [("score", "000-000|2-0|Bo3")])
            self.assertEqual(rows[0]["books"], [["m", 0, 0.999, 0.95], ["m", 1, 0.06, 0.01]])   # prices known when the score came in
            self.assertEqual(rows[0]["title"], ev["title"])

    def test_not_started_or_not_close_is_not_rechecked(self):
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            sh, s = self.make(d)
            later = {"id": "e2", "title": "X", "live": False, "ended": False, "startTime": "2099-01-01T00:00:00Z"}
            close_call = {"id": "e3", "title": "Y", "live": True, "ended": False, "startTime": "2020-01-01T00:00:00Z"}
            s.markets = {"m2": {"league": "cs2", "event": later, "tokens": ["a", "b"], "outcomes": ["A", "B"], "market": {}},
                         "m3": {"league": "cs2", "event": close_call, "tokens": ["c", "d"], "outcomes": ["C", "D"], "market": {}}}
            s.last_best = {"m2": {0: (0.95, 0.94)}, "m3": {0: (0.60, 0.58), 1: (0.42, 0.40)}}
            sh.get_json = lambda url, tries=5: self.fail("should not be called")
            s.fast_tick()

    def test_score_rows_only_on_change(self):
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            sh, s = self.make(d)
            ev = {"id": "e1", "title": "Bari: A vs B", "score": "6-3, 2-1", "period": "S2", "live": True, "ended": False}
            s.markets = {"m": {"league": "atp", "event": dict(ev), "tokens": ["a", "b"], "outcomes": ["A", "B"], "market": {}}}
            states = [ev, ev, dict(ev, score="6-3, 3-1")]
            sh.get_json = lambda url, tries=5: [states.pop(0)]
            for _ in range(3):
                s.refresh_states()
            rows = self.daily_rows(d)
            self.assertEqual([r["score"] for r in rows], ["6-3, 2-1", "6-3, 3-1"])
            self.assertIn("title", rows[0])
            self.assertNotIn("title", rows[1])                 # names only once per event


class ShadowReportTodayTests(unittest.TestCase):
    def test_today_counts_payouts_per_rule_and_open_buys(self):
        from datetime import date
        from polysweeper.shadow_report import today_lines
        # noon UTC is the same calendar day in any time zone from UTC-11 to UTC+11
        rows = [
            {"type": "entry", "rule": "price_only", "key": "1:0", "vwap": 0.97, "outcome": "A", "question": "A vs B"},
            {"type": "settled", "rule": "price_only", "key": "1:0", "ts": "2026-10-04T12:00:00+00:00", "result": "win", "pnl": 0.15},
            {"type": "entry", "rule": "score", "key": "1:0", "vwap": 0.99, "outcome": "A", "question": "A vs B"},
            {"type": "settled", "rule": "score", "key": "1:0", "ts": "2026-10-04T12:00:00+00:00", "result": "loss", "pnl": -4.95},
            {"type": "entry", "rule": "price_only", "key": "2:1", "vwap": 0.96, "outcome": "D", "question": "C vs D"},
            {"type": "entry", "rule": "price_only", "key": "3:0", "vwap": 0.98, "outcome": "E", "question": "E vs F"},
            {"type": "settled", "rule": "price_only", "key": "3:0", "ts": "2026-10-02T12:00:00+00:00", "result": "win", "pnl": 0.10},
        ]
        text = "\n".join(today_lines(rows, date(2026, 10, 4)))
        self.assertIn("price_only: paid out 1 (win 1, loss 0), fake P&L $+0.15", text)
        self.assertIn("score: paid out 1 (win 0, loss 1), fake P&L $-4.95", text)   # same key, other rule: kept apart
        self.assertIn("still waiting for payout: 1", text)
        self.assertIn("D at 0.960", text)

    def test_today_with_nothing_paid_out(self):
        from datetime import date
        from polysweeper.shadow_report import today_lines
        self.assertIn("  no pretend buy paid out today yet", today_lines([], date(2026, 10, 4)))


class CutOffReplyTests(unittest.TestCase):
    def test_a_cut_off_reply_is_fetched_again(self):
        """2026-10-04: an 11 MB events page arrived cut off (JSONDecodeError) and refresh failed."""
        import io
        import polysweeper.collector as col
        replies = [b'[{"id": "1", "title": "unterminated', b'[{"id": "1"}]']
        class Reply(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        saved = (col.urllib.request.urlopen, col.time.sleep)
        col.urllib.request.urlopen = lambda req, timeout=40: Reply(replies.pop(0))
        col.time.sleep = lambda s: None
        try:
            self.assertEqual(col.get_json("https://example.invalid/events"), [{"id": "1"}])
        finally:
            col.urllib.request.urlopen, col.time.sleep = saved
