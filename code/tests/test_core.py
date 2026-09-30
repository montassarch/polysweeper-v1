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
