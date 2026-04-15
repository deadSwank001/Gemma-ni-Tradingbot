"""
Layer 2 – Position Sizer
========================
Determines the SOL amount to allocate to each trade using a risk-based model.

Formula (per trade):
    risk_amount   = portfolio_balance × (max_risk_pct / 100) × confidence_scalar
    position_size = risk_amount / (stop_loss_pct / 100)

The result is clamped to [0, MAX_POSITION_SIZE_SOL] so a single trade can never
exceed the configured hard cap.
"""

from config import (
    PORTFOLIO_BALANCE_SOL,
    MAX_RISK_PER_TRADE_PCT,
    MAX_POSITION_SIZE_SOL,
    STOP_LOSS_PCT,
)


def calculate_position_size(
    confidence: int,
    stop_loss_pct: float = STOP_LOSS_PCT,
    portfolio_balance: float = PORTFOLIO_BALANCE_SOL,
) -> float:
    """
    Return the position size in SOL for a single trade.

    Args:
        confidence:       LLM confidence score (0-100). Scales the risk linearly
                          so low-confidence signals trade smaller.
        stop_loss_pct:    Expected stop-loss distance as a percentage of the entry
                          price (e.g. 2.0 means 2 %).  Defaults to STOP_LOSS_PCT.
        portfolio_balance: Current portfolio value in SOL.  Defaults to the
                           configured PORTFOLIO_BALANCE_SOL.

    Returns:
        Position size in SOL, rounded to 4 decimal places.
    """
    if stop_loss_pct <= 0 or confidence <= 0:
        return 0.0

    confidence_scalar = confidence / 100.0
    risk_amount = portfolio_balance * (MAX_RISK_PER_TRADE_PCT / 100.0) * confidence_scalar
    position_size = risk_amount / (stop_loss_pct / 100.0)

    # Apply hard cap
    position_size = min(position_size, MAX_POSITION_SIZE_SOL)
    position_size = max(position_size, 0.0)

    return round(position_size, 4)
