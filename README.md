"""

Solana + Gemma2 Trading Bot Architecture
Goal Description
The objective is to design a live-trading Solana bot that uses gemma2 as a reasoning engine. The bot operates on a set schedule (4 AM to 11 AM) and analyzes technical indicators (RSI, EMA, Volume) to execute intermittent trades. Additionally, it will connect to a dummy/testnet wallet to safely simulate transactions before risking real capital.

Proposed Architecture
Our system will be composed of several key modules:

1. Market Data Ingestion & Technical Analysis (TA) Engine
Data Source: We'll use a reliable Solana RPC provider (like Helius or QuickNode) paired with a market data API (e.g., Birdeye, Jupiter Price API, or DexScreener) to fetch real-time price and volume data for target Solana tokens.
Indicators: We will compute hourly RSI, EMA, and Volume metrics using a library like pandas-ta or ta.
Scheduler: A robust scheduler (e.g., APScheduler or native cron) to run the data fetching and analysis strictly between 4 AM and 11 AM local time.
2. LLM Reasoning Engine (Gemma 2)
Local/API LLM: We can run gemma2 locally using Ollama or via a cloud provider.
Prompt Formulation: The bot will construct a prompt containing the current market context (e.g., "RSI is 35, 9-EMA crossed 21-EMA, Volume is up 40%").
Decision Making: gemma2 will digest the metrics and output a structured JSON response deciding whether to BUY, SELL, or HOLD, along with a confidence score and reasoning.
3. Execution & Wallet Management
Wallet: You mentioned MetaMask, which is primarily for EVM networks (Ethereum, Base, Arbitrum). While MetaMask has "Solana Snaps", native Solana development typically uses raw Keypairs or wallets like Phantom. For a dummy setup, we will use a Solana Devnet Keypair.
Execution: We will use the solders and solana-py libraries to construct, sign, and broadcast swap transactions. For optimal routing on Solana, we'll integrate the Jupiter Aggregator API to ensure the best swap rates.
Sniper vs. Swing: A "sniper" bot requires ultra-low latency and raw RPC mempool subscriptions. Since we are checking hourly (swing/day trading), the architecture can be a bit more relaxed, allowing the LLM time to process the TA without missing millisecond-level block inclusions.
Verification Plan
Backtesting: Run the TA Engine and LLM prompts on historical data to see how gemma2 evaluates past setups.
Devnet Simulation: Run the bot on the Solana Devnet with dummy SOL/tokens. The bot will sign real transactions without real financial value.
Dry Run in Prod: Run the bot connected to Mainnet data, but instead of signing transactions, it simply logs its intended actions to a Discord webhook or local log file.

"""
