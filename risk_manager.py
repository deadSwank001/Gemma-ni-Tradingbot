"""
Layer 3 – Risk Manager
======================
Tracks real-time P&L and enforces hard risk limits:

    • Daily loss cap  – halt trading once cumulative day loss exceeds MAX_DAILY_LOSS_SOL.
    • Max drawdown    – halt trading once the drop from the session peak exceeds
                        MAX_DRAWDOWN_PCT.

State is serialised to a JSON file so limits survive process restarts within the
same calendar day.
"""

import json
import os
from datetime import date
from config import MAX_DAILY_LOSS_SOL, MAX_DRAWDOWN_PCT, STOP_LOSS_PCT, RISK_STATE_FILE


class RiskManager:
    """
    Stateful risk guard.  Instantiate once at bot start-up, then call:

        allowed, reason = rm.is_trade_allowed()
        rm.record_trade_result(pnl_sol)
    """

    def __init__(self):
        self._state_file = RISK_STATE_FILE
        self._load_state()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_state(self) -> None:
        today = str(date.today())
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r") as fh:
                    data = json.load(fh)
                if data.get("date") == today:
                    self.daily_pnl      = float(data.get("daily_pnl", 0.0))
                    self.peak_balance   = float(data.get("peak_balance", 0.0))
                    self.current_balance = float(data.get("current_balance", 0.0))
                    self.date           = today
                    return
            except (json.JSONDecodeError, KeyError):
                pass  # corrupt file – reset state

        # New day or first run
        self.daily_pnl       = 0.0
        self.peak_balance    = 0.0
        self.current_balance = 0.0
        self.date            = today
        self._save_state()

    def _save_state(self) -> None:
        with open(self._state_file, "w") as fh:
            json.dump(
                {
                    "date":             self.date,
                    "daily_pnl":        self.daily_pnl,
                    "peak_balance":     self.peak_balance,
                    "current_balance":  self.current_balance,
                },
                fh,
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def record_trade_result(self, pnl_sol: float) -> None:
        """
        Update state after a trade closes.

        Args:
            pnl_sol: Realised profit (+) or loss (−) in SOL.
        """
        self.daily_pnl       += pnl_sol
        self.current_balance += pnl_sol
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        self._save_state()

    def is_trade_allowed(self) -> tuple:
        """
        Return ``(True, 'OK')`` when trading is permitted, or
        ``(False, <reason>)`` when a risk limit has been breached.
        """
        # Re-check date so a long-running process rolls over at midnight
        if str(date.today()) != self.date:
            self._load_state()

        if self.daily_pnl <= -abs(MAX_DAILY_LOSS_SOL):
            return False, (
                f"Daily loss limit reached ({self.daily_pnl:.4f} SOL / "
                f"limit −{MAX_DAILY_LOSS_SOL:.4f} SOL)"
            )

        if self.peak_balance > 0:
            drawdown_pct = (
                (self.peak_balance - self.current_balance) / self.peak_balance
            ) * 100
            if drawdown_pct >= MAX_DRAWDOWN_PCT:
                return False, (
                    f"Max drawdown exceeded ({drawdown_pct:.1f}% / "
                    f"limit {MAX_DRAWDOWN_PCT:.1f}%)"
                )

        return True, "OK"

    @staticmethod
    def get_stop_loss_pct() -> float:
        """Convenience accessor for the configured stop-loss percentage."""
        return STOP_LOSS_PCT

    def summary(self) -> str:
        """Return a human-readable one-liner of current risk state."""
        return (
            f"Daily P&L: {self.daily_pnl:+.4f} SOL | "
            f"Balance: {self.current_balance:.4f} SOL | "
            f"Peak: {self.peak_balance:.4f} SOL"
        )
