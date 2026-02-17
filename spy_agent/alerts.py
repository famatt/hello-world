"""Alert and notification system for SPY pattern detection agent.

Supports console alerts with rich formatting, optional sound alerts,
and webhook notifications (Discord/Slack).
"""

import datetime as dt
import json
import os
import urllib.request
from typing import Optional

from spy_agent.patterns import Direction, Signal


class AlertManager:
    """Manages alerts with cooldowns, filtering, and multi-channel delivery."""

    def __init__(
        self,
        cooldown_seconds: int = 300,
        min_confidence: float = 0.6,
        webhook_url: Optional[str] = None,
        sound_enabled: bool = True,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.min_confidence = min_confidence
        self.webhook_url = webhook_url or os.environ.get("SPY_AGENT_WEBHOOK_URL")
        self.sound_enabled = sound_enabled
        self._last_alerts: dict[str, dt.datetime] = {}

    def should_alert(self, signal: Signal) -> bool:
        """Check if we should fire an alert for this signal."""
        if signal.confidence < self.min_confidence:
            return False

        key = f"{signal.pattern}_{signal.direction.value}"
        now = signal.timestamp if isinstance(signal.timestamp, dt.datetime) else dt.datetime.now()

        if key in self._last_alerts:
            elapsed = (now - self._last_alerts[key]).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False

        return True

    def alert(self, signal: Signal) -> str:
        """Fire alert for a signal. Returns formatted alert string."""
        if not self.should_alert(signal):
            return ""

        key = f"{signal.pattern}_{signal.direction.value}"
        now = signal.timestamp if isinstance(signal.timestamp, dt.datetime) else dt.datetime.now()
        self._last_alerts[key] = now

        alert_text = self._format_alert(signal)

        # Send to webhook if configured
        if self.webhook_url:
            self._send_webhook(signal)

        # Terminal bell for sound
        if self.sound_enabled:
            print("\a", end="", flush=True)

        return alert_text

    def _format_alert(self, signal: Signal) -> str:
        """Format signal into a rich console alert."""
        direction_str = "BUY CALLS" if signal.direction == Direction.LONG else "BUY PUTS"
        confidence_bar = self._confidence_bar(signal.confidence)

        lines = [
            "",
            "=" * 60,
            f"  SIGNAL: {signal.pattern.upper().replace('_', ' ')}",
            f"  Action: {direction_str}",
            f"  Time:   {signal.timestamp:%Y-%m-%d %H:%M:%S}",
            "-" * 60,
            f"  Entry:      ${signal.entry_price:.2f}",
            f"  Stop Loss:  ${signal.stop_price:.2f}",
            f"  Target:     ${signal.target_price:.2f}",
            f"  Risk:Reward {signal.risk_reward:.1f}:1",
            f"  Confidence: {confidence_bar} {signal.confidence:.0%}",
            "-" * 60,
            f"  {signal.description}",
            "=" * 60,
            "",
        ]
        return "\n".join(lines)

    def _confidence_bar(self, confidence: float) -> str:
        """Create a text-based confidence bar."""
        filled = int(confidence * 10)
        return "[" + "#" * filled + "-" * (10 - filled) + "]"

    def _send_webhook(self, signal: Signal) -> bool:
        """Send alert to Discord/Slack webhook."""
        if not self.webhook_url:
            return False

        direction_str = "BUY CALLS" if signal.direction == Direction.LONG else "BUY PUTS"

        # Discord-compatible payload (also works with Slack)
        payload = {
            "content": None,
            "embeds": [
                {
                    "title": f"SPY 0DTE Signal: {signal.pattern.replace('_', ' ').title()}",
                    "description": signal.description,
                    "color": 0x00FF00 if signal.direction == Direction.LONG else 0xFF0000,
                    "fields": [
                        {"name": "Action", "value": direction_str, "inline": True},
                        {"name": "Entry", "value": f"${signal.entry_price:.2f}", "inline": True},
                        {"name": "Stop", "value": f"${signal.stop_price:.2f}", "inline": True},
                        {"name": "Target", "value": f"${signal.target_price:.2f}", "inline": True},
                        {"name": "R:R", "value": f"{signal.risk_reward:.1f}:1", "inline": True},
                        {"name": "Confidence", "value": f"{signal.confidence:.0%}", "inline": True},
                    ],
                    "timestamp": signal.timestamp.isoformat()
                    if isinstance(signal.timestamp, dt.datetime)
                    else None,
                }
            ],
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False


def format_backtest_report(result) -> str:
    """Format backtest results into a comprehensive report string."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  SPY 0 DTE OPTIONS BACKTEST REPORT")
    lines.append("=" * 70)
    lines.append("")

    # Summary
    lines.append("  PERFORMANCE SUMMARY")
    lines.append("  " + "-" * 40)
    lines.append(f"  Total Trades:      {result.total_trades}")
    lines.append(f"  Winners:           {len(result.winners)}")
    lines.append(f"  Losers:            {len(result.losers)}")
    lines.append(f"  Win Rate:          {result.win_rate:.1f}%")
    lines.append(f"  Total P&L:         ${result.total_pnl:+,.2f}")
    lines.append(f"  Avg P&L/Trade:     ${result.avg_pnl:+,.2f}")
    lines.append(f"  Avg Winner:        ${result.avg_winner:+,.2f}")
    lines.append(f"  Avg Loser:         ${result.avg_loser:+,.2f}")
    lines.append(f"  Profit Factor:     {result.profit_factor:.2f}")
    lines.append(f"  Max Drawdown:      {result.max_drawdown:.1f}%")
    lines.append(f"  Sharpe Ratio:      {result.sharpe_ratio:.2f}")
    lines.append(f"  Avg Duration:      {result.avg_duration_minutes:.0f} min")
    lines.append("")
    lines.append(f"  Initial Capital:   ${result.initial_capital:,.2f}")
    lines.append(f"  Final Capital:     ${result.final_capital:,.2f}")
    lines.append(f"  Return:            {(result.final_capital/result.initial_capital - 1)*100:+.1f}%")
    lines.append("")

    # Pattern Breakdown
    lines.append("  PATTERN BREAKDOWN")
    lines.append("  " + "-" * 66)
    lines.append(f"  {'Pattern':<32} {'Trades':>6} {'Win%':>6} {'Total P&L':>12} {'Avg P&L':>10}")
    lines.append("  " + "-" * 66)

    for pattern, stats in result.pattern_breakdown().items():
        name = pattern.replace("_", " ").title()[:30]
        lines.append(
            f"  {name:<32} {stats['count']:>6} {stats['win_rate']:>5.1f}% "
            f"${stats['pnl']:>+10,.2f} ${stats['avg_pnl']:>+8,.2f}"
        )
    lines.append("")

    # Day of Week
    lines.append("  DAY OF WEEK BREAKDOWN")
    lines.append("  " + "-" * 50)
    for day, stats in result.day_of_week_breakdown().items():
        lines.append(
            f"  {day:<12} {stats['count']:>4} trades  "
            f"{stats['win_rate']:>5.1f}% win  ${stats['pnl']:>+10,.2f}"
        )
    lines.append("")

    # Hour of Day
    lines.append("  HOUR OF DAY BREAKDOWN")
    lines.append("  " + "-" * 50)
    for hour, stats in result.hour_breakdown().items():
        lines.append(
            f"  {hour:>2}:00       {stats['count']:>4} trades  "
            f"{stats['win_rate']:>5.1f}% win  ${stats['pnl']:>+10,.2f}"
        )
    lines.append("")

    # Top 10 trades
    lines.append("  TOP 10 WINNING TRADES")
    lines.append("  " + "-" * 60)
    top_winners = sorted(result.trades, key=lambda t: t.total_pnl, reverse=True)[:10]
    for t in top_winners:
        lines.append(f"  {t}")
    lines.append("")

    # Worst 10 trades
    lines.append("  TOP 10 LOSING TRADES")
    lines.append("  " + "-" * 60)
    top_losers = sorted(result.trades, key=lambda t: t.total_pnl)[:10]
    for t in top_losers:
        lines.append(f"  {t}")
    lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)
