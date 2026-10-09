"""Backtest settings. Each field marked VARIANT is a rule the videos leave
fuzzy; the backtest should be run with each option to see which holds up."""

from dataclasses import dataclass, field
from datetime import time


@dataclass
class Config:
    # Timeframes (minutes) whose swing highs/lows count as entry liquidity
    # (ELS). The continuation model uses 10, 15 and 30.
    level_timeframes: list[int] = field(default_factory=lambda: [10, 15, 30])
    # Ignore levels older than this many minutes.
    max_level_age_min: int = 2 * 24 * 60

    # Only take sweeps inside this New York time window.
    entry_start: time = time(9, 30)
    entry_end: time = time(12, 0)
    # Close any open trade at this time.
    flatten_at: time = time(15, 55)
    max_trades_per_day: int = 2

    # After a sweep, how many 1m bars to wait for an FVG/VI to form.
    max_bars_to_gap: int = 20
    # After the gap forms, how many 1m bars the limit may wait for a fill
    # ("I like to see my entries get tapped within like three candles").
    fill_window_bars: int = 3

    # VARIANT: "body" = stop beyond the sweep candle's body (videos 2, 9);
    # "wick" = stop beyond the sweep extreme (video 10).
    stop_mode: str = "body"
    # Reward-to-risk target, in R.
    target_r: float = 2.0
    # Skip setups whose stop is tighter than this many points.
    min_risk_points: float = 1.0

    tick_size: float = 0.25
    # Slippage on stop-outs and flatten exits, in ticks.
    slippage_ticks: int = 1
    # Contract economics: MNQ = $2 per point.
    point_value: float = 2.0
    contracts: int = 1
    commission_round_trip: float = 1.50
