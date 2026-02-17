#!/usr/bin/env python3
"""SPY 0 DTE Options Pattern Detection Agent - Main CLI.

Usage:
    python -m spy_agent monitor          Live monitoring with alerts
    python -m spy_agent backtest         Run backtest on 5yr simulated data
    python -m spy_agent backtest --live  Backtest on recent actual intraday data
    python -m spy_agent scan             One-time scan of recent data
    python -m spy_agent compare          Compare all patterns side by side
"""

import argparse
import datetime as dt
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from spy_agent.alerts import AlertManager, format_backtest_report
from spy_agent.backtester import Backtester, BacktestResult
from spy_agent.config import AgentConfig
from spy_agent.data_fetcher import DataFetcher
from spy_agent.patterns import Direction, PatternDetector

console = Console()


def cmd_monitor(args, config: AgentConfig):
    """Live monitoring mode - scans for patterns every N seconds."""
    fetcher = DataFetcher(config.ticker)
    detector = PatternDetector(config)
    alert_mgr = AlertManager(
        cooldown_seconds=config.alert_cooldown_seconds,
        min_confidence=config.min_pattern_confidence,
        webhook_url=args.webhook,
        sound_enabled=not args.no_sound,
    )

    interval = args.interval or 60

    console.print(Panel(
        f"[bold cyan]SPY 0DTE Pattern Monitor[/bold cyan]\n"
        f"Scanning every {interval}s | Min confidence: {config.min_pattern_confidence:.0%}\n"
        f"Patterns: {len(config.enabled_patterns)} enabled\n"
        f"Webhook: {'configured' if alert_mgr.webhook_url else 'not set'}",
        title="SPY Agent", border_style="cyan",
    ))

    scan_count = 0
    while True:
        try:
            scan_count += 1
            now = dt.datetime.now()
            console.print(f"\n[dim]Scan #{scan_count} at {now:%H:%M:%S}[/dim]")

            # Check if market is open (rough check)
            if now.weekday() >= 5:
                console.print("[yellow]Market closed (weekend). Waiting...[/yellow]")
                time.sleep(interval)
                continue

            hour = now.hour
            if hour < 9 or (hour == 9 and now.minute < 30) or hour >= 16:
                console.print("[yellow]Market closed. Waiting...[/yellow]")
                time.sleep(interval)
                continue

            # Fetch latest intraday data
            intraday = fetcher.fetch_intraday(interval="5m", period="5d")
            if intraday is None or len(intraday) == 0:
                console.print("[red]No data available[/red]")
                time.sleep(interval)
                continue

            # Add previous day levels
            intraday = fetcher.get_previous_day_levels(intraday)
            vwap = fetcher.get_vwap(intraday)

            # Scan for patterns
            signals = detector.scan(intraday, vwap)

            # Filter to today's signals only
            today = dt.date.today()
            today_signals = [
                s for s in signals
                if hasattr(s.timestamp, 'date') and s.timestamp.date() == today
            ]

            if today_signals:
                console.print(f"[green]Found {len(today_signals)} signal(s) today[/green]")

                for signal in today_signals:
                    alert_text = alert_mgr.alert(signal)
                    if alert_text:
                        console.print(alert_text)
            else:
                console.print("[dim]No signals detected[/dim]")

            # Show current status table
            _print_status_table(intraday, vwap, today_signals)

            time.sleep(interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Monitor stopped.[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            time.sleep(interval)


def cmd_scan(args, config: AgentConfig):
    """One-time scan of recent data."""
    console.print(Panel("[bold cyan]SPY 0DTE Pattern Scan[/bold cyan]", border_style="cyan"))

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), console=console,
    ) as progress:
        task = progress.add_task("Fetching data...", total=4)

        fetcher = DataFetcher(config.ticker)
        intraday = fetcher.fetch_intraday(interval="5m", period="5d")
        progress.update(task, advance=1, description="Processing data...")

        intraday = fetcher.get_previous_day_levels(intraday)
        vwap = fetcher.get_vwap(intraday)
        progress.update(task, advance=1, description="Scanning patterns...")

        detector = PatternDetector(config)
        signals = detector.scan(intraday, vwap)
        progress.update(task, advance=1, description="Formatting results...")

        # Filter by confidence
        signals = [s for s in signals if s.confidence >= config.min_pattern_confidence]

        progress.update(task, advance=1, description="Done!")

    if not signals:
        console.print("[yellow]No signals found in recent data.[/yellow]")
        return

    # Show results in a table
    table = Table(title=f"SPY Pattern Signals ({len(signals)} found)", show_lines=True)
    table.add_column("Time", style="cyan", width=18)
    table.add_column("Pattern", style="white", width=30)
    table.add_column("Direction", width=10)
    table.add_column("Entry", style="green", width=10)
    table.add_column("Stop", style="red", width=10)
    table.add_column("Target", style="blue", width=10)
    table.add_column("R:R", width=6)
    table.add_column("Conf", width=6)

    # Show most recent signals
    for signal in signals[-50:]:
        dir_style = "bold green" if signal.direction == Direction.LONG else "bold red"
        dir_text = "CALLS" if signal.direction == Direction.LONG else "PUTS"
        table.add_row(
            f"{signal.timestamp:%m-%d %H:%M}",
            signal.pattern.replace("_", " ").title(),
            Text(dir_text, style=dir_style),
            f"${signal.entry_price:.2f}",
            f"${signal.stop_price:.2f}",
            f"${signal.target_price:.2f}",
            f"{signal.risk_reward:.1f}",
            f"{signal.confidence:.0%}",
        )

    console.print(table)

    # Pattern frequency summary
    pattern_counts = {}
    for s in signals:
        pattern_counts[s.pattern] = pattern_counts.get(s.pattern, 0) + 1

    freq_table = Table(title="Pattern Frequency (Recent Data)")
    freq_table.add_column("Pattern", style="white")
    freq_table.add_column("Count", style="cyan", justify="right")
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
        freq_table.add_row(pattern.replace("_", " ").title(), str(count))
    console.print(freq_table)


def cmd_backtest(args, config: AgentConfig):
    """Run backtest."""
    use_daily = not args.live
    mode = "5-year simulated intraday" if use_daily else "recent actual intraday (~60 days)"

    console.print(Panel(
        f"[bold cyan]SPY 0DTE Backtest[/bold cyan]\n"
        f"Mode: {mode}\n"
        f"Capital: ${config.initial_capital:,.2f} | Position: {config.position_size_pct}%\n"
        f"Stop: {config.max_loss_per_trade_pct}% | Target: {config.profit_target_pct}%",
        title="Backtest", border_style="cyan",
    ))

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), console=console,
    ) as progress:
        task = progress.add_task("Starting backtest...", total=3)

        def progress_cb(current, total):
            desc_map = {
                0: "Fetching and preparing data...",
                1: "Detecting patterns...",
                2: "Simulating trades...",
                3: "Generating report...",
            }
            progress.update(task, completed=current, description=desc_map.get(current, "Processing..."))

        backtester = Backtester(config)
        result = backtester.run(use_daily_simulation=use_daily, progress_callback=progress_cb)

    # Print report
    report = format_backtest_report(result)
    console.print(report)

    # Save report to file if requested
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        console.print(f"\n[green]Report saved to {args.output}[/green]")


def cmd_compare(args, config: AgentConfig):
    """Compare all patterns individually."""
    console.print(Panel(
        "[bold cyan]SPY 0DTE Pattern Comparison[/bold cyan]\n"
        "Running individual backtests for each pattern...",
        title="Pattern Comparison", border_style="cyan",
    ))

    backtester = Backtester(config)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), console=console,
    ) as progress:
        task = progress.add_task("Comparing patterns...", total=len(config.enabled_patterns))
        results = {}

        for i, pattern in enumerate(config.enabled_patterns):
            progress.update(task, completed=i, description=f"Testing {pattern}...")
            single_config = AgentConfig(
                **{k: v for k, v in config.__dict__.items() if k != "enabled_patterns"},
                enabled_patterns=[pattern],
            )
            bt = Backtester(single_config)
            try:
                result = bt.run(use_daily_simulation=True)
                if result.total_trades > 0:
                    results[pattern] = result
            except Exception:
                pass

        progress.update(task, completed=len(config.enabled_patterns), description="Done!")

    if not results:
        console.print("[yellow]No patterns generated trades.[/yellow]")
        return

    # Comparison table
    table = Table(title="Pattern Performance Comparison", show_lines=True)
    table.add_column("Pattern", style="white", width=32)
    table.add_column("Trades", justify="right", width=7)
    table.add_column("Win%", justify="right", width=7)
    table.add_column("Total P&L", justify="right", width=12)
    table.add_column("Avg P&L", justify="right", width=10)
    table.add_column("PF", justify="right", width=6)
    table.add_column("MaxDD", justify="right", width=8)
    table.add_column("Sharpe", justify="right", width=7)

    for pattern, result in sorted(results.items(), key=lambda x: x[1].total_pnl, reverse=True):
        pnl_style = "green" if result.total_pnl > 0 else "red"
        table.add_row(
            pattern.replace("_", " ").title(),
            str(result.total_trades),
            f"{result.win_rate:.1f}%",
            Text(f"${result.total_pnl:+,.2f}", style=pnl_style),
            f"${result.avg_pnl:+,.2f}",
            f"{result.profit_factor:.2f}",
            f"{result.max_drawdown:.1f}%",
            f"{result.sharpe_ratio:.2f}",
        )

    console.print(table)

    # Top 5 recommendation
    top_patterns = sorted(results.items(), key=lambda x: x[1].profit_factor, reverse=True)[:5]
    console.print("\n[bold]Top 5 Patterns by Profit Factor:[/bold]")
    for i, (pattern, result) in enumerate(top_patterns, 1):
        console.print(
            f"  {i}. {pattern.replace('_', ' ').title()} "
            f"(PF: {result.profit_factor:.2f}, Win: {result.win_rate:.0f}%, "
            f"P&L: ${result.total_pnl:+,.2f})"
        )


def _print_status_table(df, vwap, signals):
    """Print current market status table."""
    if len(df) == 0:
        return

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    change = latest["close"] - prev["close"]
    change_pct = change / prev["close"] * 100

    table = Table(title="Current Status", show_header=False, border_style="dim")
    table.add_column("Label", style="dim")
    table.add_column("Value", style="bold")

    price_style = "green" if change >= 0 else "red"
    table.add_row("SPY Price", Text(f"${latest['close']:.2f} ({change:+.2f} / {change_pct:+.2f}%)", style=price_style))

    if vwap is not None and len(vwap) > 0:
        current_vwap = vwap.iloc[-1]
        if not pd.isna(current_vwap):
            vwap_rel = "above" if latest["close"] > current_vwap else "below"
            table.add_row("VWAP", f"${current_vwap:.2f} (price {vwap_rel})")

    table.add_row("Volume", f"{int(latest['volume']):,}")
    table.add_row("Day Range", f"${df.iloc[-78:]['low'].min():.2f} - ${df.iloc[-78:]['high'].max():.2f}" if len(df) >= 78 else "N/A")
    table.add_row("Signals Today", str(len(signals)))

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="SPY 0 DTE Options Pattern Detection Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spy_agent monitor                   Live monitoring
  python -m spy_agent monitor --interval 30     Scan every 30 seconds
  python -m spy_agent monitor --webhook URL     Send alerts to Discord/Slack
  python -m spy_agent scan                      One-time pattern scan
  python -m spy_agent backtest                  5-year backtest (simulated)
  python -m spy_agent backtest --live           Backtest on real intraday data
  python -m spy_agent backtest -o report.txt    Save report to file
  python -m spy_agent compare                   Compare all patterns
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Monitor
    mon = subparsers.add_parser("monitor", help="Live pattern monitoring")
    mon.add_argument("--interval", type=int, default=60, help="Scan interval in seconds")
    mon.add_argument("--webhook", type=str, help="Discord/Slack webhook URL")
    mon.add_argument("--no-sound", action="store_true", help="Disable sound alerts")

    # Scan
    subparsers.add_parser("scan", help="One-time pattern scan")

    # Backtest
    bt = subparsers.add_parser("backtest", help="Run backtest")
    bt.add_argument("--live", action="store_true", help="Use actual intraday data (60 days)")
    bt.add_argument("-o", "--output", type=str, help="Save report to file")

    # Compare
    subparsers.add_parser("compare", help="Compare patterns individually")

    # Global options
    parser.add_argument("--capital", type=float, default=10000, help="Initial capital")
    parser.add_argument("--position-size", type=float, default=5, help="Position size %%")
    parser.add_argument("--stop-loss", type=float, default=50, help="Stop loss %%")
    parser.add_argument("--take-profit", type=float, default=100, help="Take profit %%")
    parser.add_argument("--min-confidence", type=float, default=0.6, help="Min signal confidence")
    parser.add_argument("--patterns", type=str, nargs="+", help="Enable specific patterns only")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Build config
    config = AgentConfig(
        initial_capital=args.capital,
        position_size_pct=args.position_size,
        max_loss_per_trade_pct=args.stop_loss,
        profit_target_pct=args.take_profit,
        min_pattern_confidence=args.min_confidence,
    )

    if args.patterns:
        config.enabled_patterns = args.patterns

    # Import pandas here for status table (only needed if running)
    global pd
    import pandas as pd

    commands = {
        "monitor": cmd_monitor,
        "scan": cmd_scan,
        "backtest": cmd_backtest,
        "compare": cmd_compare,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()
