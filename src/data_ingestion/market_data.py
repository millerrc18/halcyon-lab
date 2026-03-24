"""Market data ingestion via yfinance."""

import sys

import pandas as pd
import yfinance as yf


def fetch_ohlcv(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch daily OHLCV data for a list of tickers.

    Returns a dict mapping ticker -> DataFrame with columns:
    Open, High, Low, Close, Volume, indexed by date.
    Tickers that fail to download are skipped with a warning.
    """
    if not tickers:
        return {}

    result = {}

    if len(tickers) == 1:
        ticker = tickers[0]
        try:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=False)
            if df is not None and not df.empty:
                # Flatten MultiIndex columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df[["Open", "High", "Low", "Close", "Volume"]]
                result[ticker] = df
            else:
                print(f"WARNING: No data returned for {ticker}", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: Failed to fetch {ticker}: {e}", file=sys.stderr)
        return result

    try:
        raw = yf.download(tickers, period=period, progress=False, auto_adjust=False, group_by="ticker")
    except Exception as e:
        print(f"WARNING: Batch download failed: {e}", file=sys.stderr)
        return result

    if raw is None or raw.empty:
        print("WARNING: No data returned from batch download", file=sys.stderr)
        return result

    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                df = raw[ticker][["Open", "High", "Low", "Close", "Volume"]].copy()
            else:
                df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
            df = df.dropna(how="all")
            if not df.empty:
                result[ticker] = df
            else:
                print(f"WARNING: No data for {ticker}", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: Failed to extract data for {ticker}: {e}", file=sys.stderr)

    return result


def fetch_spy_benchmark(period: str = "1y") -> pd.DataFrame:
    """Fetch daily OHLCV data for SPY benchmark.

    Returns a DataFrame with columns: Open, High, Low, Close, Volume.
    """
    data = fetch_ohlcv(["SPY"], period=period)
    if "SPY" in data:
        return data["SPY"]
    return pd.DataFrame()
