"""Run the Phase 1 backtest.

  python run_backtest.py --start 2025-01-01 --end 2025-07-01
  python run_backtest.py --csv bars.csv --stop-mode wick --target-r 1
"""

import argparse
import json

from bot import backtest, data
from bot.config import Config


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="1m bars CSV instead of Databento")
    src.add_argument("--start", help="Databento start date, e.g. 2025-01-01")
    ap.add_argument("--end", help="Databento end date")
    ap.add_argument("--symbol", default="NQ.v.0")
    ap.add_argument("--stop-mode", choices=["body", "wick"], default="body")
    ap.add_argument("--target-r", type=float, default=2.0)
    ap.add_argument("--timeframes", default="10,15,30")
    ap.add_argument("--out", default="trades.csv")
    args = ap.parse_args()

    if args.csv:
        bars = data.load_csv(args.csv)
    else:
        if not args.end:
            ap.error("--end is required with --start")
        bars = data.load_databento(args.start, args.end, args.symbol)

    cfg = Config(
        stop_mode=args.stop_mode,
        target_r=args.target_r,
        level_timeframes=[int(x) for x in args.timeframes.split(",")],
    )
    trades = backtest.run(bars, cfg)
    trades.to_csv(args.out, index=False)
    print(f"{len(bars):,} bars from {bars.index[0]} to {bars.index[-1]}")
    print(json.dumps(backtest.summarize(trades), indent=2, default=str))
    print(f"Trades written to {args.out}")


if __name__ == "__main__":
    main()
