"""Argparse-based CLI for LogWatch.

Provides ``scan``, ``watch``, and ``report`` subcommands for one-shot
scanning, continuous monitoring, and CSV export respectively.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

from logwatch import __version__
from logwatch.alerter import EmailAlerter
from logwatch.config import load_config
from logwatch.reporter import ConsoleReporter, CSVReporter
from logwatch.scanner import Scanner
from logwatch.watcher import LogWatcher

logger = logging.getLogger("logwatch")

# ---------------------------------------------------------------------------
# Ensure stdout supports UTF-8 on Windows
# ---------------------------------------------------------------------------

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

_BANNER = r"""
  _                __        __    _       _
 | |    ___   __ _ \ \      / /_ _| |_ ___| |__
 | |   / _ \ / _` | \ \ /\ / / _` | __/ __| '_ \
 | |__| (_) | (_| |  \ V  V / (_| | || (__| | | |
 |_____\___/ \__, |   \_/\_/ \__,_|\__\___|_| |_|
             |___/
  DevOps Log Monitoring Tool  v{version}
""".format(version=__version__)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> None:
    """Parse command-line arguments and dispatch to the appropriate handler.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).
    """
    parser = argparse.ArgumentParser(
        prog="logwatch",
        description="LogWatch — DevOps Log Monitoring Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global arguments
    parser.add_argument(
        "--config",
        "-c",
        metavar="PATH",
        default=None,
        help="Path to a JSON or TOML configuration file.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (repeat for more: -v, -vv).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"LogWatch {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Shared config argument for all subcommands (so --config works after subcommand too)
    _config_parent = argparse.ArgumentParser(add_help=False)
    _config_parent.add_argument(
        "--config",
        "-c",
        metavar="PATH",
        default=None,
        help="Path to a JSON or TOML configuration file.",
    )

    # ── scan ────────────────────────────────────────────────────────────
    scan_parser = subparsers.add_parser("scan", help="Scan one or more log files.", parents=[_config_parent])
    scan_parser.add_argument(
        "files",
        nargs="+",
        help="Log file path(s) to scan.",
    )
    scan_parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default=None,
        help="Export results to a CSV file at PATH.",
    )
    scan_parser.add_argument(
        "--severity",
        "-s",
        nargs="*",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO"],
        default=None,
        help="Filter by severity level(s).",
    )
    scan_parser.add_argument(
        "--pattern",
        "-p",
        action="append",
        default=[],
        help="Additional regex pattern(s) to match (can be repeated).",
    )
    scan_parser.add_argument(
        "--from-date",
        metavar="DATE",
        default=None,
        help="Filter matches from this date (ISO format).",
    )
    scan_parser.add_argument(
        "--to-date",
        metavar="DATE",
        default=None,
        help="Filter matches up to this date (ISO format).",
    )
    scan_parser.add_argument(
        "--keyword",
        "-k",
        action="append",
        default=[],
        help="Include lines containing this keyword (can be repeated).",
    )
    scan_parser.add_argument(
        "--exclude",
        "-x",
        action="append",
        default=[],
        help="Exclude lines containing this keyword (can be repeated).",
    )
    scan_parser.add_argument(
        "--alert",
        "-a",
        action="store_true",
        default=False,
        help="Enable email alerts for this scan.",
    )

    # ── watch ───────────────────────────────────────────────────────────
    watch_parser = subparsers.add_parser("watch", help="Continuously monitor a log file.", parents=[_config_parent])
    watch_parser.add_argument(
        "file",
        help="Log file path to watch.",
    )
    watch_parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=30,
        help="Scan interval in seconds (default: 30).",
    )
    watch_parser.add_argument(
        "--alert",
        "-a",
        action="store_true",
        default=False,
        help="Enable email alerts.",
    )

    # ── report ──────────────────────────────────────────────────────────
    report_parser = subparsers.add_parser("report", help="Scan and export to CSV.", parents=[_config_parent])
    report_parser.add_argument(
        "files",
        nargs="+",
        help="Log file path(s) to scan.",
    )
    report_parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        required=True,
        help="CSV output path (required).",
    )
    report_parser.add_argument(
        "--severity",
        "-s",
        nargs="*",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO"],
        default=None,
        help="Filter by severity level(s).",
    )

    # ── Parse ───────────────────────────────────────────────────────────
    args = parser.parse_args(argv)

    # Configure logging based on verbosity.
    log_level = logging.WARNING
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose >= 1:
        log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Print banner.
    print(_BANNER)

    # Load configuration.
    config = load_config(args.config)

    # Dispatch.
    if args.command == "scan":
        _run_scan(args, config)
    elif args.command == "watch":
        _run_watch(args, config)
    elif args.command == "report":
        _run_report(args, config)
    else:
        parser.print_help()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _run_scan(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    """Execute the ``scan`` subcommand.

    Creates a :class:`~logwatch.scanner.Scanner`, processes each file,
    prints a console report, and optionally exports to CSV and sends alerts.
    """
    # Build runtime filters from CLI flags.
    filters: Dict[str, Any] = {}
    if args.severity:
        filters["severity"] = args.severity
    if args.from_date:
        filters["date_from"] = args.from_date
    if args.to_date:
        filters["date_to"] = args.to_date
    if args.keyword:
        filters["keyword_include"] = args.keyword
    if args.exclude:
        filters["keyword_exclude"] = args.exclude

    # Inject extra patterns into config.
    if args.pattern:
        config.setdefault("custom_patterns", [])
        for idx, pat in enumerate(args.pattern):
            config["custom_patterns"].append(
                {
                    "name": f"cli_pattern_{idx}",
                    "regex": pat,
                    "severity": "INFO",
                    "description": f"User-supplied pattern: {pat}",
                }
            )

    scanner = Scanner(config=config)
    console = ConsoleReporter()
    csv_reporter = CSVReporter() if args.output else None
    alerter = EmailAlerter(config) if args.alert else None

    for file_path in args.files:
        result = scanner.scan_file(file_path, filters=filters)
        console.report(result)

        if csv_reporter and args.output:
            csv_reporter.export(result, args.output)

        if alerter and alerter.should_alert(result):
            alerter.send_alert(result)


def _run_watch(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    """Execute the ``watch`` subcommand.

    Creates a :class:`~logwatch.watcher.LogWatcher` and starts
    continuous monitoring.
    """
    watcher = LogWatcher(
        file_path=args.file,
        config=config,
        alert_enabled=args.alert,
        check_interval=args.interval,
    )
    watcher.start()


def _run_report(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    """Execute the ``report`` subcommand.

    Scans file(s) and exports results to a CSV file.
    """
    filters: Dict[str, Any] = {}
    if args.severity:
        filters["severity"] = args.severity

    scanner = Scanner(config=config)
    csv_reporter = CSVReporter()

    for file_path in args.files:
        result = scanner.scan_file(file_path, filters=filters)
        csv_reporter.export(result, args.output)
