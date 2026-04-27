"""

Solana + Gemma2 Trading Bot Architecture
Goal Description
The objective is to design a live-trading Solana bot that uses gemma2 as a reasoning engine. The bot operates on a set schedule (4 AM to 11 AM) and analyzes technical indicators (RSI, EMA, Volume)
-to execute intermittent trades.
Additionally, it will connect to a dummy/testnet wallet to safely simulate transactions before risking real capital.

Proposed Architecture
Our system will be composed of several key modules:

1. Market Data Ingestion & Technical Analysis (TA) Engine
Data Source: We'll use a reliable Solana RPC provider (like Helius or QuickNode) paired with a market data API (e.g., Birdeye, Jupiter Price API, or DexScreener)
to fetch real-time price and volume data for target Solana tokens.

Indicators: We will compute hourly RSI, EMA (9/21/50), Volume, autocorrelation of returns,
and linear-regression EMA forecasts using pandas-ta and numpy.
Scheduler: A robust scheduler (e.g., APScheduler or native cron) to run the data fetching and analysis strictly between 4 AM and 11 AM local time.

2. LLM Reasoning Engine (Gemma 2)
Local/API LLM: We can run gemma2 locally using Ollama or via a cloud provider.

Prompt Formulation: The bot will construct a prompt containing the current market context (e.g., "RSI is 35, 9-EMA crossed 21-EMA, Volume is up 40%").
Decision Making: gemma2 will digest the metrics and output a structured JSON response deciding whether to BUY, SELL, or HOLD, along with a confidence score and reasoning.
3. Execution & Wallet Management

Wallet: You mentioned MetaMask, which is primarily for EVM networks (Ethereum, Base, Arbitrum). While MetaMask has "Solana Snaps", native Solana development typically uses raw Keypairs or wallets like Phantom.
For a dummy setup, we will use a Solana Devnet Keypair.

Execution: We will use the solders and solana-py libraries to construct, sign, and broadcast swap transactions. For optimal routing on Solana, we'll integrate the Jupiter Aggregator API to ensure the best swap rates.
[Sniper vs. Swing: A "sniper" bot requires ultra-low latency and raw RPC mempool subscriptions.]** Since we are checking hourly (swing/day trading), the architecture can be a bit more relaxed,
allowing the LLM time to process the TA without missing millisecond-level block inclusions.

4. Alerts & Logging       – structured file log + Discord webhook (alerts.py)
5. Position Sizer         – risk-based sizing scaled by LLM confidence (position_sizer.py)
6. Risk Manager           – daily loss cap + drawdown guard with persisted state (risk_manager.py)
7. Backtester             – walk-forward replay on historical OHLCV (backtester.py)
8. Sentiment Engine       – social/community sentiment score appended to LLM context (sentiment_engine.py)
9. Trade Journal          – append-only trade log with live performance stats (trade_journal.py)

Verification Plan

Backtesting: Run the TA Engine and LLM prompts on historical data to see how gemma2 evaluates past setups.
Devnet Simulation: Run the bot on the Solana Devnet with dummy SOL/tokens. The bot will sign real transactions without real financial value.
Dry Run in Prod: Run the bot connected to Mainnet data, but instead of signing transactions, it simply logs its intended actions to a Discord webhook or local log file.

"""


import os
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import time

from config import TRADING_HOURS_START, TRADING_HOURS_END
from ta_engine import get_market_context, get_last_price
from llm_engine import query_gemma
from execution import execute_trade
from alerts import log_info, log_error, notify_trade, notify_risk_block
from position_sizer import calculate_position_size
from risk_manager import RiskManager
from sentiment_engine import get_sentiment_context
from trade_journal import TradeJournal

# Instantiate the risk manager once at start-up so daily state persists
# across trading cycles within the same process.
_risk_manager = RiskManager()

# Instantiate the trade journal once so all cycles share the same log.
_trade_journal = TradeJournal()

def run_trading_cycle():
    """
    Main sequence for a single trading cycle.
    1. Check risk limits
    2. Fetch TA Context
    2b. Fetch Sentiment Context
    3. Query LLM
    4. Size position
    5. Execute Trade
    6. Record in Trade Journal
    7. Alert
    """
    log_info(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] --- Starting Trading Cycle ---")
    log_info(f"[Main] Risk state: {_risk_manager.summary()}")

    # 0. Risk gate – bail early if limits are already breached
    allowed, reason = _risk_manager.is_trade_allowed()
    if not allowed:
        notify_risk_block(reason)
        return

    # 1. Market Data & TA
    context = get_market_context()
    log_info("[Main] Market Context generated:")
    log_info(context)

    # 1b. Sentiment layer – append social sentiment to the LLM context
    sentiment = get_sentiment_context()
    log_info(f"[Main] Sentiment: {sentiment}")
    context = context + "\n" + sentiment

    # 2. Reasoning Engine
    log_info("[Main] Querying local Gemma2 LLM via Ollama...")
    decision = query_gemma(context)
    log_info(f"[Main] LLM Decision: {decision}")
    
    # Extract decision properties
    action     = decision.get("action", "HOLD").upper()
    confidence = decision.get("confidence", 0)
    reasoning  = decision.get("reasoning", "")

    # Basic safety check
    if confidence < 75 and action in ["BUY", "SELL"]:
        log_info(f"[Main] Confidence ({confidence}%) too low. Forcing HOLD.")
        action = "HOLD"

    # 3. Position sizing (only meaningful for BUY/SELL)
    stop_loss_pct = _risk_manager.get_stop_loss_pct()
    amount_sol    = calculate_position_size(confidence, stop_loss_pct=stop_loss_pct)
    log_info(f"[Main] Calculated position size: {amount_sol:.4f} SOL")

    # 4. Execution Engine
    execute_trade(action, amount_sol=amount_sol)

    # 5. Trade Journal – record every non-HOLD trade
    if action in ("BUY", "SELL"):
        _trade_journal.record_trade(action, amount_sol, confidence, reasoning, get_last_price())
        log_info(f"[Main] Journal updated: {_trade_journal.summary()}")

    # 6. Alert
    if action in ("BUY", "SELL"):
        notify_trade(action, amount_sol, reasoning, confidence)

    log_info("--- Trading Cycle Complete ---\n")

def start_scheduler():
    """
    Schedules the bot to run hourly strictly between specified trading hours.
    """
    scheduler = BlockingScheduler()
    
    # Run the cycle once per hour, only between TRADING_HOURS_START and TRADING_HOURS_END.
    # The cron syntax hour='4-11', minute=0 means it runs at the top of the hour from 4 AM to 11 AM.
    scheduler.add_job(
        run_trading_cycle, 
        'cron', 
        hour=f'{TRADING_HOURS_START}-{TRADING_HOURS_END}', 
        minute=0
    )
    
    log_info(f"Trading bot initialized. Scheduling active from {TRADING_HOURS_START}:00 to {TRADING_HOURS_END}:00 local time.")
    log_info("Press Ctrl+C to exit.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log_info("\nShutdown signal received. Exiting.")

if __name__ == "__main__":
    start_scheduler()
    
    # Note: If you want to test immediately without waiting for the next hour,
    # uncomment the line below to run one cycle instantly:
    # run_trading_cycle()

    # To run a quick rule-based backtest on start-up, uncomment:
    # from backtester import run_backtest
    # run_backtest(use_llm=False)
