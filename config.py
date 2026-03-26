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
TRADE_AMOUNT_SOL = 0.1 # Amount of SOL to trade per signal
