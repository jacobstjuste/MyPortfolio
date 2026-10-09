# NQ liquidity-sweep backtester

Phase 1 of the bot described in [SPEC.md](SPEC.md): the "continuation model" with no daily bias.

1. A swing high or low on the 10, 15 or 30-minute chart gets swept.
2. The first 1-minute FVG or VI that forms after the sweep becomes the entry. A limit order goes at its edge.
3. The limit must fill within 3 candles.
4. The stop goes beyond the sweep candle's body (or wick). The target is 2R.

## Setup

```
pip install -r requirements.txt
python -m pytest -q
```

## Run

With Databento (needs `DATABENTO_API_KEY` set and `hist.databento.com` reachable):

```
python run_backtest.py --start 2025-01-01 --end 2025-07-01
```

With your own 1-minute CSV (columns `timestamp,open,high,low,close,volume`; UTC timestamps unless an offset is given):

```
python run_backtest.py --csv bars.csv
```

To compare variants:

```
python run_backtest.py --start 2025-01-01 --end 2025-07-01 --stop-mode wick
python run_backtest.py --start 2025-01-01 --end 2025-07-01 --target-r 1
python run_backtest.py --start 2025-01-01 --end 2025-07-01 --timeframes 15,30
```

Results print as a summary (win rate, average R, profit factor, max drawdown). Every trade is written to `trades.csv`.

## Notes

- **No lookahead.** Swing levels count only after the next higher-timeframe candle closes. Gaps count only after their third candle closes. If a stop and target are hit in the same 1-minute bar, it counts as a loss.
- **Sanity check.** On random-walk data the strategy comes out about break-even before costs, which is what an honest backtest should show on data with no structure.
- **Not yet built (Phase 2):** daily bias, the "valid wick" filter, and the cancel rules (second wick, opposite setups). Add them one at a time and measure each one.
