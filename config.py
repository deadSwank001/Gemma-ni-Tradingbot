import os
from dotenv import load_dotenv

load_dotenv()

# API Keys and Endpoints
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "your_helius_api_key_here")
RPC_URL = f"https://devnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "your_birdeye_api_key_here")

# Solana Wallet
PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY", "your_base58_encoded_private_key")

# LLM Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = "gemma2"

# Trading target (Example: dummy token on Devnet)
TARGET_TOKEN = "So11111111111111111111111111111111111111112" # Wrapped SOL
TRADING_HOURS_START = 4
TRADING_HOURS_END = 11
TRADE_AMOUNT_SOL = 0.1 # Fallback amount of SOL to trade per signal

# ── Risk Manager ──────────────────────────────────────────────────────────────
# Maximum total loss allowed in a single trading day (SOL)
MAX_DAILY_LOSS_SOL = float(os.getenv("MAX_DAILY_LOSS_SOL", "0.5"))
# Halt trading once drawdown from peak balance exceeds this percentage
MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", "10.0"))
# Default stop-loss distance as a percentage of entry price
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "2.0"))
# JSON file used to persist daily risk state across restarts
RISK_STATE_FILE = os.getenv("RISK_STATE_FILE", "risk_state.json")

# ── Position Sizer ────────────────────────────────────────────────────────────
# Total portfolio value the bot manages (SOL)
PORTFOLIO_BALANCE_SOL = float(os.getenv("PORTFOLIO_BALANCE_SOL", "10.0"))
# Maximum percentage of portfolio to risk on a single trade
MAX_RISK_PER_TRADE_PCT = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "1.0"))
# Hard cap on any single position size (SOL)
MAX_POSITION_SIZE_SOL = float(os.getenv("MAX_POSITION_SIZE_SOL", "1.0"))

# ── Alerts & Logging ──────────────────────────────────────────────────────────
# Discord incoming-webhook URL; leave blank to disable Discord notifications
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
# Path to the rotating log file
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "tradingbot.log")

# ── Backtester ────────────────────────────────────────────────────────────────
# Number of historical days to replay
BACKTEST_DAYS = int(os.getenv("BACKTEST_DAYS", "30"))
# Simulated starting balance for backtests (SOL)
BACKTEST_INITIAL_BALANCE_SOL = float(os.getenv("BACKTEST_INITIAL_BALANCE_SOL", "10.0"))

# ── Sentiment Engine ──────────────────────────────────────────────────────────
# Base URL for the CoinGecko public API (no key required)
SENTIMENT_API_BASE_URL = os.getenv("SENTIMENT_API_BASE_URL", "https://api.coingecko.com/api/v3")
# CoinGecko coin ID for the target token (default: solana)
SENTIMENT_COIN_ID = os.getenv("SENTIMENT_COIN_ID", "solana")

# ── Trade Journal ─────────────────────────────────────────────────────────────
# JSON file that stores the persistent trade log
TRADE_JOURNAL_FILE = os.getenv("TRADE_JOURNAL_FILE", "trade_journal.json")
