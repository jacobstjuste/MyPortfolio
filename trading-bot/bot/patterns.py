"""Candle patterns: higher-timeframe swing levels, and 1-minute FVG/VI gaps.

Every pattern carries the time it becomes knowable, so the backtest never
acts on a candle before it has closed (no lookahead)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Level:
    price: float
    side: str  # "low" (buy-side sweep) or "high" (sell-side sweep)
    timeframe: int  # minutes
    formed_at: pd.Timestamp  # open time of the candle that made the wick
    available_at: pd.Timestamp  # when the swing is confirmed


def resample(bars: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Aggregate 1m bars into `minutes` candles, indexed by open time."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    out = bars.resample(f"{minutes}min", label="left", closed="left").agg(agg)
    return out.dropna()


def swing_levels(bars: pd.DataFrame, minutes: int) -> list[Level]:
    """Swing highs/lows on the `minutes` timeframe: a wick beyond both
    neighbours. Confirmed only once the next candle has closed."""
    htf = resample(bars, minutes)
    hi, lo = htf["high"].to_numpy(), htf["low"].to_numpy()
    opens = htf.index
    step = pd.Timedelta(minutes=minutes)
    levels = []
    for i in range(1, len(htf) - 1):
        available = opens[i + 1] + step
        if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]:
            levels.append(Level(lo[i], "low", minutes, opens[i], available))
        if hi[i] > hi[i - 1] and hi[i] > hi[i + 1]:
            levels.append(Level(hi[i], "high", minutes, opens[i], available))
    return levels


def find_gaps(bars: pd.DataFrame) -> pd.DataFrame:
    """For each 1m bar c, the bullish and bearish gap that completes at c.

    FVG: candles a, b, c with no overlap between a's and c's wicks.
    VI: candles b, c whose bodies don't overlap.
    Columns: long_top/long_bottom/long_b and short_top/short_bottom/short_b,
    where *_b is the position of candle b (NaN when no gap). For a long the
    limit goes at long_top; for a short at short_bottom (the first edge
    price returns to). When both an FVG and a VI exist, the one price
    reaches first wins."""
    o, h, l, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    n = len(bars)
    body_hi, body_lo = np.maximum(o, c), np.minimum(o, c)
    out = {k: np.full(n, np.nan) for k in (
        "long_top", "long_bottom", "long_b",
        "short_top", "short_bottom", "short_b")}

    for i in range(1, n):
        # Bullish VI: body of i fully above body of i-1.
        if body_lo[i] > body_hi[i - 1]:
            out["long_top"][i], out["long_bottom"][i] = body_lo[i], body_hi[i - 1]
            out["long_b"][i] = i - 1
        if body_hi[i] < body_lo[i - 1]:
            out["short_top"][i], out["short_bottom"][i] = body_lo[i - 1], body_hi[i]
            out["short_b"][i] = i - 1
        if i < 2:
            continue
        # Bullish FVG: low of c above high of a.
        if l[i] > h[i - 2] and not (out["long_top"][i] > l[i]):
            out["long_top"][i], out["long_bottom"][i] = l[i], h[i - 2]
            out["long_b"][i] = i - 1
        if h[i] < l[i - 2] and not (out["short_bottom"][i] < h[i]):
            out["short_top"][i], out["short_bottom"][i] = l[i - 2], h[i]
            out["short_b"][i] = i - 1
    return pd.DataFrame(out, index=bars.index)
