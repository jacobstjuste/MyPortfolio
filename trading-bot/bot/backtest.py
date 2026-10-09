"""Phase 1 backtest: the continuation model with no bias.

Per 1-minute bar the engine moves through four states:
  idle     -> a 10/15/30m swing level is swept          -> armed
  armed    -> first 1m FVG/VI forms after the sweep     -> pending (limit)
  pending  -> limit fills within the fill window        -> in_trade
  in_trade -> stop or target hit (or flatten time)      -> idle

A bar is only acted on with information from bars that closed before it,
and levels/gaps only count from the bar after they are confirmed."""

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .config import Config
from .patterns import Level, find_gaps, swing_levels


@dataclass
class Trade:
    direction: str
    level_tf: int
    level_price: float
    sweep_time: pd.Timestamp
    gap_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    stop: float
    target: float
    exit_time: pd.Timestamp | None = None
    exit: float | None = None
    outcome: str | None = None  # "target", "stop" or "flatten"
    r: float | None = None
    dollars: float | None = None


def run(bars: pd.DataFrame, cfg: Config | None = None) -> pd.DataFrame:
    cfg = cfg or Config()
    gaps = {k: v.to_numpy() for k, v in find_gaps(bars).items()}
    levels = sorted(
        (lv for tf in cfg.level_timeframes for lv in swing_levels(bars, tf)),
        key=lambda lv: lv.available_at,
    )

    t = bars.index
    o, h, l, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    tick = cfg.tick_size
    slip = cfg.slippage_ticks * tick
    max_age = pd.Timedelta(minutes=cfg.max_level_age_min)

    active: list[Level] = []
    next_level = 0
    trades: list[Trade] = []
    state = "idle"
    setup: dict = {}
    trade: Trade | None = None
    day, trades_today = None, 0

    def close_trade(i: int, price: float, outcome: str) -> None:
        nonlocal state, trade
        sign = 1 if trade.direction == "long" else -1
        risk = abs(trade.entry - trade.stop)
        points = sign * (price - trade.entry)
        trade.exit_time, trade.exit, trade.outcome = t[i], price, outcome
        trade.r = points / risk
        trade.dollars = (points * cfg.point_value * cfg.contracts
                         - cfg.commission_round_trip * cfg.contracts)
        trades.append(trade)
        trade, state = None, "idle"

    for i in range(len(bars)):
        now = t[i]
        clock = now.time()
        if now.date() != day:
            day, trades_today = now.date(), 0

        # Levels confirmed before this bar opened become usable.
        while next_level < len(levels) and levels[next_level].available_at <= now:
            active.append(levels[next_level])
            next_level += 1
        active = [lv for lv in active if now - lv.formed_at <= max_age]

        # --- manage an open trade -------------------------------------
        if state == "in_trade":
            long = trade.direction == "long"
            if clock >= cfg.flatten_at:
                close_trade(i, o[i] - slip if long else o[i] + slip, "flatten")
            elif (l[i] <= trade.stop) if long else (h[i] >= trade.stop):
                # Gapped through the stop: fill at the open.
                fill = min(o[i], trade.stop) if long else max(o[i], trade.stop)
                close_trade(i, fill - slip if long else fill + slip, "stop")
            elif (h[i] >= trade.target) if long else (l[i] <= trade.target):
                close_trade(i, trade.target, "target")

        # --- waiting for the limit to fill ----------------------------
        elif state == "pending":
            long = setup["direction"] == "long"
            entry = setup["entry"]
            touched = (l[i] <= entry) if long else (h[i] >= entry)
            if touched:
                fill = min(o[i], entry) if long else max(o[i], entry)
                trade = Trade(
                    setup["direction"], setup["level"].timeframe,
                    setup["level"].price, setup["sweep_time"],
                    setup["gap_time"], now, fill, setup["stop"], setup["target"])
                trades_today += 1
                state = "in_trade"
                # Conservative: if the fill bar also reaches the stop, assume
                # the stop came first. A target on the fill bar is ignored.
                if (l[i] <= trade.stop) if long else (h[i] >= trade.stop):
                    close_trade(i, trade.stop - slip if long else trade.stop + slip, "stop")
            else:
                setup["waited"] += 1
                if setup["waited"] >= cfg.fill_window_bars or clock >= cfg.entry_end:
                    state = "idle"

        # --- swept; looking for the 1m entry gap ----------------------
        elif state == "armed":
            long = setup["direction"] == "long"
            # Track the sweep extreme: the candle that went furthest.
            if (l[i] < l[setup["ext"]]) if long else (h[i] > h[setup["ext"]]):
                setup["ext"] = i
            side = "long" if long else "short"
            b = gaps[f"{side}_b"][i]
            # Gap completes at bar i; its middle candle must be at or after
            # the sweep, and the gap candle must close back past the level.
            reclaimed = c[i] > setup["level"].price if long else c[i] < setup["level"].price
            if not np.isnan(b) and b >= setup["sweep_i"] and reclaimed:
                e = setup["ext"]
                if long:
                    entry = gaps["long_top"][i]
                    base = min(o[e], c[e]) if cfg.stop_mode == "body" else l[e]
                    stop = base - tick
                else:
                    entry = gaps["short_bottom"][i]
                    base = max(o[e], c[e]) if cfg.stop_mode == "body" else h[e]
                    stop = base + tick
                risk = abs(entry - stop)
                valid_side = entry > stop if long else entry < stop
                if valid_side and risk >= cfg.min_risk_points:
                    sign = 1 if long else -1
                    setup.update(entry=entry, stop=stop, waited=0,
                                 target=entry + sign * cfg.target_r * risk,
                                 gap_time=now)
                    state = "pending"
                else:
                    state = "idle"
            elif i - setup["sweep_i"] >= cfg.max_bars_to_gap or clock >= cfg.entry_end:
                state = "idle"

        # --- sweeps: always consume levels, arm only when idle --------
        swept_low = [lv for lv in active if lv.side == "low" and l[i] < lv.price]
        swept_high = [lv for lv in active if lv.side == "high" and h[i] > lv.price]
        if swept_low or swept_high:
            gone = {id(lv) for lv in swept_low + swept_high}
            active = [lv for lv in active if id(lv) not in gone]
            in_window = cfg.entry_start <= clock < cfg.entry_end
            if (state == "idle" and in_window and trades_today < cfg.max_trades_per_day
                    and bool(swept_low) != bool(swept_high)):
                long = bool(swept_low)
                # Prefer the highest-timeframe level swept on this bar.
                lv = max(swept_low or swept_high, key=lambda x: x.timeframe)
                setup = dict(direction="long" if long else "short", level=lv,
                             sweep_i=i, sweep_time=now, ext=i)
                state = "armed"

    return pd.DataFrame([asdict(tr) for tr in trades])


def summarize(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    r = trades["r"]
    equity = r.cumsum()
    drawdown = (equity.cummax().clip(lower=0) - equity).max()
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    months = max(
        (trades["entry_time"].max() - trades["entry_time"].min()).days / 30.4, 1)
    return {
        "trades": len(trades),
        "win_rate": round((r > 0).mean(), 3),
        "avg_r": round(r.mean(), 3),
        "total_r": round(r.sum(), 2),
        "profit_factor": round(wins / losses, 2) if losses else float("inf"),
        "max_drawdown_r": round(drawdown, 2),
        "trades_per_month": round(len(trades) / months, 1),
        "net_dollars": round(trades["dollars"].sum(), 2),
        "by_direction": trades.groupby("direction")["r"].agg(["count", "mean"]).round(3).to_dict(),
        "by_outcome": trades["outcome"].value_counts().to_dict(),
    }
