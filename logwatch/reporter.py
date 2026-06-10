"""Report generation for scan results.

Provides both a coloured console reporter and a CSV exporter.
"""

from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from typing import Dict

from logwatch.scanner import ScanResult

# ---------------------------------------------------------------------------
# Ensure stdout supports UTF-8 on Windows
# ---------------------------------------------------------------------------

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# ANSI colour helpers (respects NO_COLOR — https://no-color.org/)
# ---------------------------------------------------------------------------

_NO_COLOR = os.environ.get("NO_COLOR") is not None

_RESET = "" if _NO_COLOR else "\033[0m"
_BOLD = "" if _NO_COLOR else "\033[1m"
_DIM = "" if _NO_COLOR else "\033[2m"

_RED = "" if _NO_COLOR else "\033[91m"
_YELLOW = "" if _NO_COLOR else "\033[93m"
_CYAN = "" if _NO_COLOR else "\033[96m"
_GREEN = "" if _NO_COLOR else "\033[92m"
_WHITE = "" if _NO_COLOR else "\033[97m"
_MAGENTA = "" if _NO_COLOR else "\033[95m"

_SEVERITY_COLORS: Dict[str, str] = {
    "CRITICAL": _RED,
    "ERROR": _RED,
    "WARNING": _YELLOW,
    "INFO": _CYAN,
}


def _color(text: str, code: str) -> str:
    """Wrap *text* in an ANSI colour escape sequence."""
    if _NO_COLOR:
        return text
    return f"{code}{text}{_RESET}"


# ---------------------------------------------------------------------------
# Box-drawing helpers
# ---------------------------------------------------------------------------

_H = "\u2500"   # ─
_V = "\u2502"   # │
_TL = "\u250c"  # ┌
_TR = "\u2510"  # ┐
_BL = "\u2514"  # └
_BR = "\u2518"  # ┘
_ML = "\u251c"  # ├
_MR = "\u2524"  # ┤


def _hline(width: int, left: str = _TL, right: str = _TR) -> str:
    return f"{left}{_H * width}{right}"


# ---------------------------------------------------------------------------
# Console reporter
# ---------------------------------------------------------------------------


class ConsoleReporter:
    """Prints a rich, coloured summary of a :class:`ScanResult` to *stdout*."""

    def report(self, scan_result: ScanResult) -> None:
        """Print a beautiful coloured console report.

        Sections:
        1. Header banner with file name and scan time.
        2. Severity summary table.
        3. Top 10 most frequent matched messages.
        4. Time distribution (if timestamps are available).
        5. Footer with total lines and match rate.

        Args:
            scan_result: The :class:`~logwatch.scanner.ScanResult` to display.
        """
        width = 72

        # ── Header ──────────────────────────────────────────────────────
        print()
        print(_color(_hline(width), _CYAN))
        title = f"  LogWatch Scan Report — {os.path.basename(scan_result.file_path)}"
        print(_color(f"{_V}{title:<{width}}{_V}", _CYAN))
        meta = f"  Scanned in {scan_result.scan_time:.3f}s  |  {scan_result.start_time}"
        print(_color(f"{_V}{meta:<{width}}{_V}", _DIM))
        print(_color(_hline(width, _ML, _MR), _CYAN))

        # ── Summary table ───────────────────────────────────────────────
        print(_color(f"{_V}{'  SEVERITY SUMMARY':<{width}}{_V}", _BOLD))
        print(_color(_hline(width, _ML, _MR), _CYAN))

        for severity in ("CRITICAL", "ERROR", "WARNING", "INFO"):
            count = scan_result.summary.get(severity, 0)
            sev_color = _SEVERITY_COLORS.get(severity, _WHITE)
            label = _color(f"  {severity:<12}", sev_color)
            bar = _color("█" * min(count, 40), sev_color)
            line_text = f"{label} {count:>6}  {bar}"
            # Print without padding the colour-coded string (padding
            # would be off due to escape sequences).
            print(f"{_V}{line_text}")

        print(_color(_hline(width, _ML, _MR), _CYAN))

        # ── Top 10 frequent matches ─────────────────────────────────────
        if scan_result.matches:
            print(_color(f"{_V}{'  TOP 10 MATCHED MESSAGES':<{width}}{_V}", _BOLD))
            print(_color(_hline(width, _ML, _MR), _CYAN))

            counter: Counter[str] = Counter()
            for m in scan_result.matches:
                # Use matched_text as the key for frequency counting.
                counter[m.matched_text] += 1

            for rank, (text, cnt) in enumerate(counter.most_common(10), start=1):
                truncated = (text[:50] + "…") if len(text) > 50 else text
                entry = f"  {rank:>2}. [{cnt:>4}x] {truncated}"
                print(f"{_V}{entry}")

            print(_color(_hline(width, _ML, _MR), _CYAN))

        # ── Time distribution ───────────────────────────────────────────
        timestamps = [m.timestamp for m in scan_result.matches if m.timestamp]
        if timestamps:
            print(_color(f"{_V}{'  TIME DISTRIBUTION':<{width}}{_V}", _BOLD))
            print(_color(_hline(width, _ML, _MR), _CYAN))

            # Group by hour portion of the timestamp string.
            hour_counter: Counter[str] = Counter()
            for ts in timestamps:
                # Attempt to extract the hour component.
                try:
                    hour = ts.split("T")[-1].split(" ")[-1][:2]
                    hour_counter[f"{hour}:00"] += 1
                except (IndexError, ValueError):
                    hour_counter["unknown"] += 1

            for hour, cnt in sorted(hour_counter.items()):
                bar = _color("▓" * min(cnt, 40), _MAGENTA)
                entry = f"  {hour:<8} {cnt:>5}  {bar}"
                print(f"{_V}{entry}")

            print(_color(_hline(width, _ML, _MR), _CYAN))

        # ── Footer ──────────────────────────────────────────────────────
        total = scan_result.total_lines
        matched = len(scan_result.matches)
        rate = (matched / total * 100) if total else 0.0
        footer = (
            f"  Total lines: {total:,}  |  "
            f"Matches: {matched:,}  |  "
            f"Match rate: {rate:.2f}%"
        )
        print(_color(f"{_V}{footer:<{width}}{_V}", _GREEN))
        print(_color(_hline(width, _BL, _BR), _CYAN))
        print()


# ---------------------------------------------------------------------------
# CSV reporter
# ---------------------------------------------------------------------------


class CSVReporter:
    """Exports a :class:`ScanResult` to a CSV file."""

    def export(self, scan_result: ScanResult, output_path: str) -> str:
        """Write scan matches to a CSV file.

        Columns: ``line_number``, ``timestamp``, ``severity``,
        ``pattern_name``, ``matched_text``, ``raw_line``.

        The output directory is created automatically if it does not exist.

        Args:
            scan_result: The :class:`~logwatch.scanner.ScanResult` to export.
            output_path: Destination file path for the CSV.

        Returns:
            The absolute path to the written CSV file.
        """
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "line_number",
                    "timestamp",
                    "severity",
                    "pattern_name",
                    "matched_text",
                    "raw_line",
                ]
            )
            for m in scan_result.matches:
                writer.writerow(
                    [
                        m.line_number,
                        m.timestamp or "",
                        m.severity,
                        m.pattern_name,
                        m.matched_text,
                        m.raw_line,
                    ]
                )

        abs_path = os.path.abspath(output_path)
        print(f"CSV report written to: {abs_path}")
        return abs_path
