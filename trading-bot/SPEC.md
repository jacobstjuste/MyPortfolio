# NQ Liquidity-Sweep Strategy: Spec and Handoff

This file carries the context from an earlier Claude Code session so a new session can continue without re-explaining.

## Background

The user shared transcripts of 10 YouTube videos (9 unique; links 4 and 8 were the same video) from a futures trader who teaches an ICT-style "liquidity sweep" strategy. The goal is a bot that calls out trades (alerts with entry, stop, target) based on these rules.

Videos, in order:
1. What is and how to identify liquidity (VwHeRG3bn-s)
2. Identifying high vs low probability sweeps (FWBqttukrJY)
3. How to validate/invalidate your entries (XR3nsie3lsk)
4. Creating a framework and mastering market outcomes (I0UKzZ0ZTuo), sent twice
5. How to align the HTF with the 1 minute (C7s_BobtO6Q)
6. Mastering the 1M by using IE's (1WwBQ6UjprI)
7. Wick to wick and in-depth explanation of IE's (JTT0pMFt6CU)
8. (duplicate of 4)
9. How to create daily bias, trade/market recap (as2b6yg36UE)
10. How to create daily bias with live execution (bFRBkZSB8sU)

## Market and session

- Instrument: NQ / MNQ futures (the trader says "I want everyone to trade NQ"). Also trades gold and silver at times. Trade one instrument per day.
- Point values: NQ $20/pt, MNQ $2/pt; GC $100/pt, MGC $10/pt.
- Session: entries from the New York open, 9:30 ET (he is on Pacific time and calls it 6:30). Also trades London, never Asia.
- Context: prop-firm accounts (Topstep, etc.); for example a $50k account with about a $2k max loss. Some trades are taken just to hit payout rules (for example $150 days); the bot should ignore that.

## Definitions

- **Liquidity:** resting orders at wicks (candle highs and lows) on any timeframe. Price moves wick to wick, from one pool of liquidity to the next.
- **Valid level:** a wick with a candle "next to" or "behind" it, meaning the neighbouring candle sits right up against that level. A wick sticking out alone with empty space beside it is "floating" and is ignored.
  - *Measurable version:* valid if the adjacent candle's high/low is within 0.25 × ATR of the wick extreme.
  - Exception (video 7): in price discovery (all-time high/low, nothing to the left), the latest extreme always counts as liquidity.
- **Sweep:** a candle trades beyond a level and reverses.
  - *Measurable version:* the wick goes past the level and the candle closes back on the original side.
  - A swept low means buy; a swept high means sell.
- **Double:** two levels swept at once, or the same sweep on two timeframes. Stronger.
- **FVG (fair value gap):** three candles where the first candle's wick and the third candle's wick don't overlap.
- **VI (volume imbalance):** a gap between the bodies of two adjacent candles.
- **ELS (entry liquidity sweep):** a pre-marked level whose sweep triggers the hunt for a 1-minute entry.
- **IE (invalidated entry):** a condition that cancels a pending limit order.

## Step 1: daily bias (pre-market)

- Go top-down: 6M, 3M, 2M, 1M, 3W, 1W, 3D, 2D, 1D, 12h, 8h. The daily, 12h and 8h matter most. Never start as low as the 4h.
- The bias comes from the most recent valid high-timeframe sweep.
- **Probability check:** go up one timeframe. If the swept level is also a wick there, it's a high-probability sweep and the bias holds. If it's only body (no wick), the bias is likely wrong and price continues to the next liquidity.
- **Draw on liquidity (target):** the nearest untouched valid level in the bias direction (previous day, week or month high/low; 3- or 6-month levels when nothing is closer).
- Skip "ugly" timeframes that have no clear sweeps.
- Bias is a preference for the day's trade direction, not a one-way forecast. Every high-timeframe wick produces a reaction.
- Bias can flip intraday (rarely): if price breaks back through a level a valid sweep should have held, stop trading the bias direction.

## Step 2: three scenarios (pick one and stick to it)

1. **Late:** the high-timeframe level is already swept. Take continuation entries only.
2. **On time:** price is sweeping the level now. Catch the top or bottom.
3. **Early:** price hasn't reached the level. Either trade toward it (counter-bias) or wait for the sweep. *First version: skip counter-bias trades;* he says they rarely fill.

## Step 3: mark ELS levels

- Walk down the 12h, 8h, 4h, 2h, 1h, 30m, 15m, 10m and 5m charts. Mark clean, unswept valid wicks in the bias direction.
- If a timeframe has too many competing wicks (choppy), go up a timeframe until there are only 1–2 clear ones. *Measurable version: skip a timeframe with more than 3 levels within 1 ATR of price.*
- Rank higher where two timeframes line up (for example 8h with 4h, or 1h with 2h).
- Keep only a few levels. Delete them once used or missed.
- 3m and 5m ELS only count during a clear trend; he later dropped the 3m.
- **Continuation model (no bias needed):** a 10, 15 or 30-minute sweep, then a 1-minute entry. He claims this is profitable alone with a lower win rate. **Build this first as the baseline.**

## Step 4: entry trigger

- An ELS level gets swept on its timeframe. A 1-minute sweep alone "means nothing".
- Drop to the 1-minute chart. Take the **first** VI or FVG that forms **after** the sweep, in the trade direction. Never use old gaps that were sitting there before the sweep.
- Place a **limit order** at the gap edge once the gap candle has closed. Never use market orders. Enter on the pullback; never chase.
- If price runs away from the first gap and a newer gap forms, he moved his limit to the newer one (video 7). *Test both: move to the newer gap vs. cancel.*
- He sometimes uses 30-second or 15-second charts for entries. *Approximate with 1-minute data at first.*

## Step 5: cancel rules (IE), checked before the fill

- **Second-wick rule:** after the sweep, if price runs through a second 1-minute wick in the trade direction before the limit fills, cancel. He says that setup fails about 90% of the time.
  - Exception: when price action is "choppy" (many small overlapping candles, no countable second wick), he keeps the order. *Measurable version: more than 4 overlapping candles between the wicks means choppy. Test with and without this exception.*
- **Opposite liquidity:** cancel if, before the fill, price sweeps a clean opposite-side wick on the 5, 10 or 15-minute chart.
- **Opposite setup:** "You do not want to see your entry throw another lower timeframe entry to the opposite bias." Run the same setup detector in reverse on the small timeframes; if a valid opposite setup forms first, cancel.
- **Gap candle check:** if the candle that formed the gap took out an opposite 1-minute wick and the next candles held instead of breaking through it, cancel. Valid if price breaks through ("disrespects") that wick or taps the gap almost immediately.
- **Fill window:** price must tap the gap within about 3 candles of it forming; otherwise cancel.
- If cancelled and price re-sweeps the same level, a new gap can give a fresh entry.

## Step 6: trade management

- **Stop:** two versions in the videos. *Test both:*
  - Beyond the body of the sweep candle (videos 2, 9: "stop at the body")
  - Beyond the sweep swing low/high wick (video 10)
- **Target:** fixed 1R, 2R or 3R (he usually says "one or two"), or the next opposing liquidity, such as the next 10 or 15-minute wick. *Test all.*
- No trailing stop and no adjustments. The trade ends at the target or the stop.
- Fixed dollar risk per trade, sized to the prop account's max loss. Prefer micros.

## Priority order (his words, video 5)

1. Bias
2. High-timeframe wicks
3. Entry sweep ("no sweep = no trade")
4. Validate or invalidate the entry
5. Enter with a proper stop and a realistic target

## Known fuzzy areas (discretionary, cannot be coded exactly)

- "Clean" vs "choppy". He says "I don't have a word for it".
- Valid wick ("candle behind it"). Confirm the measurable rule against real charts with the user.
- Resolving conflicts between timeframes for bias.
- Stop placement (body vs wick).

The bot will be an approximation of his discretion. Validate every rule with the backtest and drop rules that don't add value.

## Build plan

1. **Phase 1:** backtest the continuation model (no bias) on historical NQ 1-minute data. Report the win rate, average R, max drawdown and trades per month. Watch carefully for lookahead bias: a higher-timeframe candle's high/low must not be used before that candle closes.
2. **Phase 2:** add the bias filter, the valid-wick filter and the IE rules one at a time, measuring the effect of each.
3. **Phase 3:** live alerts (entry, stop, target) to Discord; paper trade first. Needs an always-on host, since the cloud session container is temporary.

## Environment setup (status at handoff)

- Data: Databento (historical API host `hist.databento.com`). Auth is HTTP Basic: API key as username, blank password. Configured as a network secret, or the `DATABENTO_API_KEY` env var.
- Alerts: Discord webhook in the `DISCORD_WEBHOOK_URL` env var; the `discord.com` domain must be allowed.
- Undecided: whether the bot lives in this portfolio repo (`trading-bot/`) or a separate repo.
- The user wanted to pause bot work and get chart reads from screenshots in the meantime.
