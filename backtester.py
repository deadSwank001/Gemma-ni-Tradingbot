"""
Layer 4 – Backtester
=====================
Replays the TA engine (and optionally the LLM) on historical OHLCV data in a
walk-forward fashion, simulating trade entry/exit and reporting P&L.

Two modes:
    rule_based (default, fast)
        Entry  – Bullish EMA crossover AND RSI < 60
        Exit   – Bearish EMA crossover OR  RSI > 70
    llm  (slow – makes one Ollama call per candle)
        Uses query_gemma() exactly as the live bot does.

Usage:
    from backtester import run_backtest
    run_backtest(use_llm=False)   # rule-based, no Ollama required
    run_backtest(use_llm=True)    # LLM-assisted (requires running Ollama)
"""

import time
import pandas as pd
from ta_engine import fetch_historical_ohlcv, perform_technical_analysis
from position_sizer import calculate_position_size
from config import TARGET_TOKEN, BACKTEST_DAYS, BACKTEST_INITIAL_BALANCE_SOL


def _rule_based_decision(metrics: dict) -> tuple:
    """
    Simple deterministic signal derived from EMA crossover + RSI.
    Returns (action: str, confidence: int).
    """
    crossover = metrics.get("EMA_Crossover", "None")
    rsi       = metrics.get("RSI", 50)
    rsi_sig   = metrics.get("RSI_Signal", "Neutral")

    if crossover == "Bullish Cross" and rsi_sig != "Overbought":
        return "BUY", 80
    if crossover == "Bearish Cross" or rsi_sig == "Overbought":
        return "SELL", 80
    # Momentum continuation: positive autocorr at lag-1 h with neutral RSI
    if metrics.get("Autocorr_Lag_1h", 0) > 0.15 and rsi < 60:
        return "BUY", 65
    return "HOLD", 50


def run_backtest(use_llm: bool = False) -> dict:
    """
    Walk-forward backtest over the last BACKTEST_DAYS of hourly data.

    Args:
        use_llm: When True the LLM is queried for each candle (slow).
                 When False a fast rule-based signal is used instead.

    Returns:
        Summary dict with keys: final_balance, total_pnl, total_trades,
        winning_trades, win_rate, max_drawdown_pct.
    """
    mode_label = "LLM-assisted" if use_llm else "rule-based"
    print(
        f"\n[Backtester] Starting {mode_label} backtest over last "
        f"{BACKTEST_DAYS} days …"
    )

    now       = int(time.time())
    time_from = now - (BACKTEST_DAYS * 24 * 60 * 60)
    df        = fetch_historical_ohlcv(TARGET_TOKEN, time_from, now)

    if df.empty or len(df) < 52:
        print("[Backtester] Insufficient historical data – aborting.")
        return {}

    # ── Walk-forward simulation ───────────────────────────────────────────────
    balance      = BACKTEST_INITIAL_BALANCE_SOL
    peak_balance = balance
    min_balance  = balance
    position     = 0.0   # token units held
    entry_price  = 0.0
    trades       = []

    # Leave first 50 candles as indicator warm-up
    for i in range(50, len(df)):
        window  = df.iloc[:i].copy()
        metrics = perform_technical_analysis(window)
        if not metrics:
            continue

        price = metrics["price"]

        # ── Signal ────────────────────────────────────────────────────────────
        if use_llm:
            from llm_engine import query_gemma
            ema_9_fc  = ", ".join(f"{v:.4f}" for v in metrics["EMA_9_Forecast_3H"])
            ema_21_fc = ", ".join(f"{v:.4f}" for v in metrics["EMA_21_Forecast_3H"])
            context = (
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
            decision   = query_gemma(context)
            action     = decision.get("action", "HOLD").upper()
            confidence = decision.get("confidence", 0)
            if confidence < 75 and action in ("BUY", "SELL"):
                action = "HOLD"
        else:
            action, confidence = _rule_based_decision(metrics)

        size_sol = calculate_position_size(confidence)

        # ── Trade execution simulation ────────────────────────────────────────
        if action == "BUY" and position == 0.0 and balance >= size_sol and size_sol > 0:
            tokens      = size_sol / price
            position    = tokens
            entry_price = price
            balance    -= size_sol
            trades.append({
                "type":     "BUY",
                "price":    price,
                "size_sol": size_sol,
                "pnl_sol":  None,
            })

        elif action == "SELL" and position > 0.0:
            proceeds = position * price
            pnl      = proceeds - (position * entry_price)
            balance += proceeds
            trades.append({
                "type":    "SELL",
                "price":   price,
                "pnl_sol": pnl,
            })
            position    = 0.0
            entry_price = 0.0

        # Track drawdown
        if balance < min_balance:
            min_balance = balance
        if balance > peak_balance:
            peak_balance = balance

    # ── Close any open position at final candle ───────────────────────────────
    if position > 0.0:
        last_price = df.iloc[-1]["close"]
        proceeds   = position * last_price
        pnl        = proceeds - (position * entry_price)
        balance   += proceeds
        trades.append({"type": "SELL (close)", "price": last_price, "pnl_sol": pnl})

    # ── Statistics ────────────────────────────────────────────────────────────
    sell_trades   = [t for t in trades if "SELL" in t["type"]]
    winning       = [t for t in sell_trades if (t.get("pnl_sol") or 0) > 0]
    win_rate      = (len(winning) / len(sell_trades) * 100) if sell_trades else 0.0
    total_pnl     = balance - BACKTEST_INITIAL_BALANCE_SOL
    max_dd_pct    = ((peak_balance - min_balance) / peak_balance * 100) if peak_balance > 0 else 0.0

    print(f"\n[Backtester] ── {mode_label.upper()} Results {'─'*35}")
    print(f"  Mode            : {mode_label}")
    print(f"  Period          : last {BACKTEST_DAYS} days")
    print(f"  Initial Balance : {BACKTEST_INITIAL_BALANCE_SOL:.4f} SOL")
    print(f"  Final Balance   : {balance:.4f} SOL")
    print(f"  Total P&L       : {total_pnl:+.4f} SOL")
    print(f"  Total Trades    : {len(trades)}")
    print(f"  Winning Trades  : {len(winning)}")
    print(f"  Win Rate        : {win_rate:.1f}%")
    print(f"  Max Drawdown    : {max_dd_pct:.1f}%")
    print(f"[Backtester] {'─'*55}\n")

    return {
        "final_balance":   balance,
        "total_pnl":       total_pnl,
        "total_trades":    len(trades),
        "winning_trades":  len(winning),
        "win_rate":        win_rate,
        "max_drawdown_pct": max_dd_pct,
    }
