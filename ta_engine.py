import requests
import pandas as pd
import pandas_ta as ta
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

def perform_technical_analysis(df: pd.DataFrame) -> dict:
    """
    Computes RSI, EMA, and Volume metrics using pandas-ta.
    """
    if df.empty or len(df) < 50:
        return {}

    # Calculate RSI
    df["RSI"] = ta.rsi(df["close"], length=14)
    # Calculate EMA 9 and 21
    df["EMA_9"] = ta.ema(df["close"], length=9)
    df["EMA_21"] = ta.ema(df["close"], length=21)
    # Calculate Volume Change
    df["Volume_Change"] = df["volume"].pct_change() * 100

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Check for EMA crossover
    crossover = "Bullish Cross" if (prev["EMA_9"] <= prev["EMA_21"] and latest["EMA_9"] > latest["EMA_21"]) else \
                "Bearish Cross" if (prev["EMA_9"] >= prev["EMA_21"] and latest["EMA_9"] < latest["EMA_21"]) else "None"

    return {
        "price": latest["close"],
        "RSI": latest["RSI"],
        "EMA_9": latest["EMA_9"],
        "EMA_21": latest["EMA_21"],
        "EMA_Crossover": crossover,
        "Volume_Change_Pct": latest["Volume_Change"]
    }

def get_market_context() -> str:
    """
    Fetches data and returns a formatted string with the latest TA metrics.
    """
    now = int(time.time())
    # Fetch last 3 days of hourly data to have enough for EMA/RSI calculations
    time_from = now - (3 * 24 * 60 * 60)
    
    df = fetch_historical_ohlcv(TARGET_TOKEN, time_from, now)
    metrics = perform_technical_analysis(df)
    
    if not metrics:
        return "Market data unavailable or insufficient data for analysis."

    context = (
        f"Current Price: {metrics['price']:.4f}\n"
        f"RSI (14): {metrics['RSI']:.2f}\n"
        f"9-EMA: {metrics['EMA_9']:.4f}\n"
        f"21-EMA: {metrics['EMA_21']:.4f}\n"
        f"EMA Crossover: {metrics['EMA_Crossover']}\n"
        f"Volume Change (1H): {metrics['Volume_Change_Pct']:.2f}%\n"
    )
    return context
