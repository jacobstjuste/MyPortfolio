"""Hand-built 1m price paths with known answers."""

import numpy as np
import pandas as pd
import pytest

from bot import backtest
from bot.config import Config
from bot.patterns import find_gaps, swing_levels

DAY = "2026-10-07"  # a Wednesday


def make_bars(rows, start=f"{DAY} 08:30"):
    """rows: list of (open, high, low, close), one per minute."""
    idx = pd.date_range(start, periods=len(rows), freq="1min", tz="America/New_York")
    df = pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close"])
    df["volume"] = 100.0
    return df


def setup_rows(after_gap):
    """08:30-09:29 builds a 15m swing low at 95 (confirmed 09:15).
    09:30-09:40 drifts down, 09:41 sweeps to 94, 09:42-09:44 form a
    bullish FVG of 96-97 whose middle candle is after the sweep."""
    rows = [(100, 101, 99.5, 100.5)] * 15                 # 08:30 candle
    rows += [(100, 100.5, 95, 99)] + [(99, 100, 98.5, 99.5)] * 14  # 08:45, low 95
    rows += [(100, 102, 99, 101)] * 15                    # 09:00
    rows += [(101, 101.5, 100.5, 101)] * 15               # 09:15
    for k in range(11):                                   # 09:30-09:40
        op = 101 - 0.5 * k
        rows.append((op, op + 0.2, op - 0.6, op - 0.5))
    rows += [
        (95.5, 95.8, 94.0, 95.6),   # 09:41 sweep of 95; body low 95.5
        (95.6, 96.0, 95.2, 95.8),   # 09:42 candle a, high 96
        (95.8, 99.0, 95.7, 98.8),   # 09:43 candle b
        (98.8, 99.5, 97.0, 99.0),   # 09:44 candle c, low 97 -> FVG 96-97
    ]
    return rows + after_gap


CFG = Config(level_timeframes=[15], commission_round_trip=0, slippage_ticks=0)


def test_swing_level_confirmed_after_next_candle_closes():
    bars = make_bars(setup_rows([]))
    lows = [lv for lv in swing_levels(bars, 15) if lv.side == "low"]
    level = next(lv for lv in lows if lv.price == 95)
    assert level.formed_at == pd.Timestamp(f"{DAY} 08:45", tz="America/New_York")
    # Needs the 09:00 candle to close before it is known.
    assert level.available_at == pd.Timestamp(f"{DAY} 09:15", tz="America/New_York")


def test_fvg_detected_at_third_candle():
    bars = make_bars(setup_rows([]))
    gaps = find_gaps(bars)
    row = gaps.loc[pd.Timestamp(f"{DAY} 09:44", tz="America/New_York")]
    assert row.long_top == 97 and row.long_bottom == 96


def test_long_setup_hits_target():
    rows = setup_rows([
        (99.0, 99.2, 96.9, 97.5),    # 09:45 taps 97 -> filled
        (97.5, 101.0, 97.4, 100.8),  # 09:46 reaches 100.5 target
    ])
    trades = backtest.run(make_bars(rows), CFG)
    assert len(trades) == 1
    tr = trades.iloc[0]
    assert tr.direction == "long"
    assert tr.entry == 97
    assert tr.stop == 95.25          # sweep candle body low 95.5 minus a tick
    assert tr.target == pytest.approx(100.5)
    assert tr.outcome == "target" and tr.r == pytest.approx(2.0)


def test_stop_and_target_same_bar_counts_as_loss():
    rows = setup_rows([
        (99.0, 99.2, 96.9, 97.5),    # filled
        (97.5, 101.0, 95.0, 100.0),  # touches both stop and target
    ])
    tr = backtest.run(make_bars(rows), CFG).iloc[0]
    assert tr.outcome == "stop" and tr.r == pytest.approx(-1.0)


def test_unfilled_limit_cancels_after_fill_window():
    rows = setup_rows([(99.0, 99.5, 98.0, 99.2)] * 3 + [(99.2, 99.3, 96.5, 97.0)])
    trades = backtest.run(make_bars(rows), CFG)
    assert trades.empty


def test_wick_stop_mode():
    rows = setup_rows([(99.0, 99.2, 96.9, 97.5), (97.5, 99.0, 96.0, 98.0)])
    cfg = Config(level_timeframes=[15], stop_mode="wick")
    tr = backtest.run(make_bars(rows), cfg)
    assert tr.empty or tr.iloc[0].stop == 93.75  # sweep low 94 minus a tick


def test_runs_on_random_walk_without_errors():
    rng = np.random.default_rng(0)
    n = 5 * 24 * 60
    close = 20000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.exponential(1, n)
    low = np.minimum(open_, close) - rng.exponential(1, n)
    bars = make_bars(list(zip(open_, high, low, close)), start="2026-10-05 00:00")
    trades = backtest.run(bars, Config())
    summary = backtest.summarize(trades)
    assert summary["trades"] == len(trades)
    if len(trades):
        assert trades["entry_time"].is_monotonic_increasing
        assert (trades["exit_time"] >= trades["entry_time"]).all()
