"""
Layer 1 – Alerts & Logging
==========================
Provides structured file-based logging and optional Discord webhook notifications
for all significant bot events (trade signals, risk blocks, errors).
"""

import logging
import logging.handlers
import requests
from datetime import datetime
from config import DISCORD_WEBHOOK_URL, LOG_FILE_PATH

# ── Logger setup ──────────────────────────────────────────────────────────────
_logger = logging.getLogger("tradingbot")
_logger.setLevel(logging.DEBUG)

# Rotating file handler – keeps up to 5 × 5 MB log files
_fh = logging.handlers.RotatingFileHandler(
    LOG_FILE_PATH, maxBytes=5 * 1024 * 1024, backupCount=5
)
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
_logger.addHandler(_fh)

# Console handler – INFO and above only
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
_logger.addHandler(_ch)

# ── Internal helpers ──────────────────────────────────────────────────────────

def _send_discord(message: str) -> None:
    """POST *message* to the configured Discord webhook. Silently skips if URL is empty."""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message},
            timeout=5
        )
        if resp.status_code not in (200, 204):
            _logger.warning(f"Discord webhook returned HTTP {resp.status_code}")
    except Exception as exc:
        _logger.error(f"Discord alert failed: {exc}")

# ── Public API ────────────────────────────────────────────────────────────────

def log_info(message: str) -> None:
    _logger.info(message)

def log_warning(message: str) -> None:
    _logger.warning(message)

def log_error(message: str) -> None:
    _logger.error(message)

def notify_trade(action: str, amount_sol: float, reasoning: str, confidence: int) -> None:
    """Log a trade signal and push a Discord notification."""
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🤖 **Trade Signal** | {ts}\n"
        f"Action: **{action}** | Amount: {amount_sol:.4f} SOL | Confidence: {confidence}%\n"
        f"Reasoning: {reasoning}"
    )
    _logger.info(msg)
    _send_discord(msg)

def notify_risk_block(reason: str) -> None:
    """Log a risk-manager veto and push a Discord notification."""
    msg = f"🛑 **Trade Blocked by Risk Manager** | {reason}"
    _logger.warning(msg)
    _send_discord(msg)

def notify_error(context: str, error: Exception) -> None:
    """Log an unexpected error and push a Discord notification."""
    msg = f"❌ **Bot Error** in {context}: {error}"
    _logger.error(msg)
    _send_discord(msg)
