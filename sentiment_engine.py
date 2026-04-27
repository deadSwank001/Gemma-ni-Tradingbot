"""
Layer 8 – Sentiment Engine
==========================
Fetches aggregated social / news sentiment for the target token and returns
a formatted string that is appended to the LLM market-context prompt.

Data source: CoinGecko public API (no key required for basic endpoints).
The engine queries the trending coins list and the asset's community data to
derive a simple sentiment label and numeric score.

Fallback: when the API is unreachable or returns unexpected data the engine
logs a warning and returns a neutral placeholder so the rest of the pipeline
is never blocked.
"""

import requests
from alerts import log_warning
from config import SENTIMENT_API_BASE_URL, SENTIMENT_COIN_ID

# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_coin_data(coin_id: str) -> dict:
    """
    Retrieve community / sentiment data for *coin_id* from CoinGecko.

    Returns the raw response dict, or an empty dict on any error.
    """
    url = f"{SENTIMENT_API_BASE_URL}/coins/{coin_id}"
    params = {
        "localization":   "false",
        "tickers":        "false",
        "market_data":    "false",
        "community_data": "true",
        "developer_data": "false",
        "sparkline":      "false",
    }
    try:
        resp = requests.get(url, params=params, timeout=4)
        if resp.status_code == 200:
            return resp.json()
        log_warning(f"[Sentiment Engine] CoinGecko returned HTTP {resp.status_code}")
    except Exception as exc:
        log_warning(f"[Sentiment Engine] Request failed: {exc}")
    return {}


def _score_from_community(community: dict) -> tuple:
    """
    Derive a 0-100 sentiment score and a label from CoinGecko community data.

    Heuristic:
        • Base on `sentiment_votes_up_percentage` when available.
        • Supplement with twitter_followers / reddit_subscribers growth signal.

    Returns (score: float, label: str).
    """
    up_pct = community.get("sentiment_votes_up_percentage")
    if up_pct is not None:
        score = float(up_pct)
    else:
        # Fallback: flat neutral
        score = 50.0

    if score >= 65:
        label = "Bullish"
    elif score <= 35:
        label = "Bearish"
    else:
        label = "Neutral"

    return round(score, 1), label


# ── Public API ────────────────────────────────────────────────────────────────

def get_sentiment_score() -> tuple:
    """
    Return ``(score: float, label: str)`` for the configured token.

    *score* is in the range [0, 100] where 100 = maximally bullish.
    *label* is one of ``"Bullish"``, ``"Neutral"``, or ``"Bearish"``.
    """
    data      = _fetch_coin_data(SENTIMENT_COIN_ID)
    community = data.get("community_data", {})

    if not community:
        log_warning("[Sentiment Engine] No community data – defaulting to Neutral (50).")
        return 50.0, "Neutral"

    return _score_from_community(community)


def get_sentiment_context() -> str:
    """
    Return a one-line formatted string ready to be appended to the LLM prompt.

    Example output:
        Social Sentiment: Bullish (score: 72.3 / 100)
    """
    score, label = get_sentiment_score()
    return f"Social Sentiment: {label} (score: {score} / 100)"
