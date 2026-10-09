"""Load 1-minute OHLCV bars as a DataFrame indexed by bar open time in
New York time, with columns open, high, low, close, volume."""

import os

import pandas as pd

NY = "America/New_York"
COLUMNS = ["open", "high", "low", "close", "volume"]


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df = df.set_axis(idx.tz_convert(NY))
    df = df[COLUMNS].astype(float).sort_index()
    return df[~df.index.duplicated(keep="last")]


def load_csv(path: str) -> pd.DataFrame:
    """CSV with a `timestamp` column (bar open time; UTC if no offset given)
    plus open, high, low, close, volume."""
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    return _finish(df)


def load_databento(
    start: str,
    end: str,
    symbol: str = "NQ.v.0",
    cache_dir: str | None = "data",
) -> pd.DataFrame:
    """Fetch 1-minute bars from Databento's CME Globex dataset.

    `symbol` is a continuous contract: NQ.v.0 rolls to the most-traded
    contract. Requires the DATABENTO_API_KEY environment variable."""
    cache = None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cache = os.path.join(cache_dir, f"{symbol}_{start}_{end}.parquet")
        if os.path.exists(cache):
            return pd.read_parquet(cache)

    import databento as db

    client = db.Historical(os.environ["DATABENTO_API_KEY"])
    store = client.timeseries.get_range(
        dataset="GLBX.MDP3",
        schema="ohlcv-1m",
        symbols=[symbol],
        stype_in="continuous",
        start=start,
        end=end,
    )
    df = _finish(store.to_df())
    if cache:
        df.to_parquet(cache)
    return df
