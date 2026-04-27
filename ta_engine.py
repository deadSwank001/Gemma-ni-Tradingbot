import requests
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from config import TARGET_TOKEN, BIRDEYE_API_KEY

def fetch_historical_ohlcv(token_address: str, time_from: int, time_to: int, type: str = "1H") -> pd.DataFrame:
    """
    Fetches OHLCV data from Birdeye API.
    """
    url = f"https://public-api.birdeye.so/defi/history_price?address={token_address}&address_type=token&type={type}&time_from={time_from}&time_to={time_to}"
    headers = {
        "X-API-KEY": BIRDEYE_API_KEY,
        "x-chain": "solana"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"[TA Engine] Error fetching data: {response.status_code}")
        return pd.DataFrame()
    
    data = response.json().get("data", {}).get("items", [])
    if not data:
        return pd.DataFrame()
        
    df = pd.DataFrame(data)
    # Birdeye API typically returns unixTime, value (price)
    # In a real scenario, you'd ensure it returns Full OHLCV. For the mock we just map the 'value' to close, and use random/approximate for missing ones if needed.
    # Assuming Birdeye OHLCV endpoint is used:
    if "c" in df.columns:
        df = df.rename(columns={"c": "close", "v": "volume", "unixTime": "timestamp", "h": "high", "l": "low", "o": "open"})
    else:
        # Mock mapping if simple price endpoint
        df["close"] = df["value"]
        df["volume"] = 1000000 # Mock volume
        
    df["timestamp"] = pd.to_datetime(df["unixTime"], unit="s")
    df.set_index("timestamp", inplace=True)
    return df

# ── Auto-correlation ──────────────────────────────────────────────────────────

def compute_autocorrelation(series: pd.Series, lags: list = None) -> dict:
    """
    Computes autocorrelation of 1-period price returns at each lag.

    Positive autocorr  → momentum (trend continuation is likely).
    Negative autocorr  → mean-reversion (price likely to reverse).

    Args:
        series: Close price series.
        lags:   List of integer lags in hours. Defaults to [1, 6, 24].

    Returns:
        Dict mapping 'autocorr_lag_Nh' keys to rounded float values.
    """
    if lags is None:
        lags = [1, 6, 24]
    returns = series.pct_change().dropna()
    result = {}
    for lag in lags:
        raw = returns.autocorr(lag=lag)
        # autocorr() returns NaN when variance is zero or data is insufficient
        result[f"autocorr_lag_{lag}h"] = round(float(raw), 4) if not (raw != raw) else 0.0
    return result

# ── EMA extrapolation ─────────────────────────────────────────────────────────

def extrapolate_ema(series: pd.Series, forward_periods: int = 3) -> list:
    """
    Projects an EMA series forward by fitting a linear regression to the last
    20 (non-NaN) values and extrapolating *forward_periods* steps.

    Returns a list of forecasted float values (same price units as input).
    """
    recent = series.dropna().tail(20).values
    if len(recent) < 2:
        return []
    x = np.arange(len(recent))
    try:
        coeffs = np.polyfit(x, recent, deg=1)  # [slope, intercept]
    except (np.linalg.LinAlgError, ValueError):
        return []
    future_x = np.arange(len(recent), len(recent) + forward_periods)
    return [round(float(np.polyval(coeffs, fx)), 6) for fx in future_x]

# ── Core TA ───────────────────────────────────────────────────────────────────

def perform_technical_analysis(df: pd.DataFrame) -> dict:
    """
    Computes RSI, multi-period EMAs, volume metrics, auto-correlation of returns,
    and linear-regression EMA forecasts.

    Returns a dict of scalar and list metrics; empty dict on insufficient data.
    """
    if df.empty or len(df) < 50:
        return {}

    # ── Indicators ────────────────────────────────────────────────────────────
    df["RSI"] = ta.rsi(df["close"], length=14)
    df["EMA_9"]  = ta.ema(df["close"], length=9)
    df["EMA_21"] = ta.ema(df["close"], length=21)
    df["EMA_50"] = ta.ema(df["close"], length=50)
    df["Volume_Change"] = df["volume"].pct_change() * 100

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    # ── EMA crossover signal ──────────────────────────────────────────────────
    if   prev["EMA_9"] <= prev["EMA_21"] and latest["EMA_9"] > latest["EMA_21"]:
        crossover = "Bullish Cross"
    elif prev["EMA_9"] >= prev["EMA_21"] and latest["EMA_9"] < latest["EMA_21"]:
        crossover = "Bearish Cross"
    else:
        crossover = "None"

    # ── RSI condition label ───────────────────────────────────────────────────
    rsi_val = latest["RSI"]
    if   rsi_val >= 70:
        rsi_signal = "Overbought"
    elif rsi_val <= 30:
        rsi_signal = "Oversold"
    else:
        rsi_signal = "Neutral"

    # ── Auto-correlation of returns ───────────────────────────────────────────
    autocorr = compute_autocorrelation(df["close"])

    # ── EMA linear-regression forecasts (next 3 hours) ───────────────────────
    ema_9_forecast  = extrapolate_ema(df["EMA_9"],  forward_periods=3)
    ema_21_forecast = extrapolate_ema(df["EMA_21"], forward_periods=3)

    return {
        "price":              latest["close"],
        # RSI
        "RSI":                latest["RSI"],
        "RSI_Signal":         rsi_signal,
        # EMAs
        "EMA_9":              latest["EMA_9"],
        "EMA_21":             latest["EMA_21"],
        "EMA_50":             latest["EMA_50"],
        "EMA_Crossover":      crossover,
        # EMA forecasts
        "EMA_9_Forecast_3H":  ema_9_forecast,
        "EMA_21_Forecast_3H": ema_21_forecast,
        # Volume
        "Volume_Change_Pct":  latest["Volume_Change"],
        # Auto-correlation
        "Autocorr_Lag_1h":    autocorr.get("autocorr_lag_1h", 0.0),
        "Autocorr_Lag_6h":    autocorr.get("autocorr_lag_6h", 0.0),
        "Autocorr_Lag_24h":   autocorr.get("autocorr_lag_24h", 0.0),
    }

def get_market_context() -> str:
    """
    Fetches OHLCV data and returns a formatted string with all TA metrics
    (including autocorrelation and EMA forecasts) for the LLM prompt.
    """
    now = int(time.time())
    # Fetch last 3 days of hourly data to have enough for EMA/RSI calculations
    time_from = now - (3 * 24 * 60 * 60)
    
    df = fetch_historical_ohlcv(TARGET_TOKEN, time_from, now)
    metrics = perform_technical_analysis(df)
    
    if not metrics:
        return "Market data unavailable or insufficient data for analysis."

    # Cache last known price for other modules to consume without a second fetch
    _cache["last_price"] = metrics.get("price", 0.0)

    return format_context(metrics)


# Module-level price cache populated by get_market_context()
_cache: dict = {}


def get_last_price() -> float:
    """
    Return the most recently fetched asset price (set by ``get_market_context``).
    Returns 0.0 if no price has been fetched yet this session.
    """
    return _cache.get("last_price", 0.0)


def format_context(metrics: dict) -> str:
    """
    Formats a metrics dict (from perform_technical_analysis) into the standard
    context string consumed by the LLM prompt.

    Extracted as a shared helper so the backtester and live cycle produce
    identical prompt text.
    """
    ema_9_fc  = ", ".join(f"{v:.4f}" for v in metrics.get("EMA_9_Forecast_3H", []))
    ema_21_fc = ", ".join(f"{v:.4f}" for v in metrics.get("EMA_21_Forecast_3H", []))

    return (
        f"Current Price: {metrics['price']:.4f}\n"
        f"RSI (14): {metrics['RSI']:.2f} [{metrics['RSI_Signal']}]\n"
        f"9-EMA:  {metrics['EMA_9']:.4f}  → Forecast (next 3H): {ema_9_fc}\n"
        f"21-EMA: {metrics['EMA_21']:.4f} → Forecast (next 3H): {ema_21_fc}\n"
        f"50-EMA: {metrics['EMA_50']:.4f}\n"
        f"EMA Crossover: {metrics['EMA_Crossover']}\n"
        f"Volume Change (1H): {metrics['Volume_Change_Pct']:.2f}%\n"
        f"Autocorrelation — 1H: {metrics['Autocorr_Lag_1h']:.4f} | "
        f"6H: {metrics['Autocorr_Lag_6h']:.4f} | "
        f"24H: {metrics['Autocorr_Lag_24h']:.4f}\n"
    )
