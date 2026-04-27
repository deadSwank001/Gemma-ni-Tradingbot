"""
Layer 9 – Trade Journal & Performance Tracker
==============================================
Records every executed trade to a persistent JSON log file and exposes live
statistics so the rest of the pipeline (and operators) can track performance
without opening a database.

Usage:
    from trade_journal import TradeJournal

    journal = TradeJournal()
    journal.record_trade("BUY",  amount_sol=0.25, confidence=82,
                         reasoning="Bullish cross + high volume",
                         price=142.50)
    journal.record_trade("SELL", amount_sol=0.25, confidence=78,
                         reasoning="RSI overbought", price=148.00)

    print(journal.summary())   # human-readable stats
    stats = journal.get_stats()  # structured dict for downstream use
"""

import json
import os
from datetime import datetime
from config import TRADE_JOURNAL_FILE


class TradeJournal:
    """
    Append-only trade log backed by a JSON file.

    Each entry is a dict with the fields:
        timestamp, action, amount_sol, confidence, reasoning, price, pnl_sol

    *pnl_sol* is computed automatically for SELL trades by pairing them with
    the most recent unmatched BUY entry (FIFO).  BUY entries carry ``None``.
    """

    def __init__(self, filepath: str = TRADE_JOURNAL_FILE):
        self._filepath = filepath
        self._trades   = self._load()
        # FIFO queue of open BUY entries awaiting a matching SELL
        self._open_buys: list = [
            t for t in self._trades
            if t["action"] == "BUY" and t.get("pnl_sol") is None
        ]

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> list:
        """Load existing trades from disk; return empty list if file absent."""
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save(self) -> None:
        with open(self._filepath, "w") as fh:
            json.dump(self._trades, fh, indent=2)

    # ── Public API ────────────────────────────────────────────────────────────

    def record_trade(
        self,
        action:     str,
        amount_sol: float,
        confidence: int,
        reasoning:  str,
        price:      float,
    ) -> None:
        """
        Append a trade to the journal and persist it to disk.

        Args:
            action:     ``"BUY"``, ``"SELL"``, or ``"HOLD"``.  HOLD is skipped.
            amount_sol: Position size in SOL.
            confidence: LLM confidence score (0-100).
            reasoning:  Short explanation from the LLM.
            price:      Asset price at the time of execution (in SOL or USD).
        """
        if action == "HOLD":
            return

        pnl_sol = None

        if action == "SELL" and self._open_buys:
            buy          = self._open_buys.pop(0)
            buy_price    = buy["price"]
            pnl_sol      = round((price - buy_price) * amount_sol / buy_price, 6)

        entry = {
            "timestamp":  datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "action":     action,
            "amount_sol": round(amount_sol, 6),
            "confidence": confidence,
            "reasoning":  reasoning,
            "price":      price,
            "pnl_sol":    pnl_sol,
        }

        self._trades.append(entry)
        if action == "BUY":
            self._open_buys.append(entry)

        self._save()

    def get_stats(self) -> dict:
        """
        Return a structured performance summary dict.

        Keys: total_trades, buy_trades, sell_trades, winning_trades,
              losing_trades, win_rate, total_pnl_sol, avg_confidence.
        """
        sells       = [t for t in self._trades if t["action"] == "SELL"]
        buys        = [t for t in self._trades if t["action"] == "BUY"]
        pnls        = [t["pnl_sol"] for t in sells if t.get("pnl_sol") is not None]
        winning     = [p for p in pnls if p > 0]
        losing      = [p for p in pnls if p < 0]
        win_rate    = (len(winning) / len(pnls) * 100) if pnls else 0.0
        total_pnl   = sum(pnls)
        all_conf    = [t["confidence"] for t in self._trades if t.get("confidence")]
        avg_conf    = (sum(all_conf) / len(all_conf)) if all_conf else 0.0

        return {
            "total_trades":   len(self._trades),
            "buy_trades":     len(buys),
            "sell_trades":    len(sells),
            "winning_trades": len(winning),
            "losing_trades":  len(losing),
            "win_rate":       round(win_rate, 1),
            "total_pnl_sol":  round(total_pnl, 6),
            "avg_confidence": round(avg_conf, 1),
        }

    def summary(self) -> str:
        """Return a human-readable one-liner of current journal stats."""
        s = self.get_stats()
        return (
            f"Trades: {s['total_trades']} "
            f"(B:{s['buy_trades']} / S:{s['sell_trades']}) | "
            f"Win Rate: {s['win_rate']:.1f}% | "
            f"Total P&L: {s['total_pnl_sol']:+.6f} SOL | "
            f"Avg Confidence: {s['avg_confidence']:.1f}%"
        )
