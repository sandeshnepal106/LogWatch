"""Core log scanning engine.

Reads log files line-by-line, applies compiled regex patterns, respects
user-defined filters, and produces structured scan results.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from logwatch.config import DEFAULT_CONFIG, load_config
from logwatch.patterns import Pattern, compile_patterns, get_default_patterns

logger = logging.getLogger(__name__)

# Common timestamp formats to try when extracting dates from log lines.
_TIMESTAMP_FORMATS: List[str] = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
    "%b %d %H:%M:%S",           # syslog
    "%d/%b/%Y:%H:%M:%S",       # Apache CLF
    "%Y-%m-%dT%H:%M:%S%z",     # ISO 8601 with tz
]

# Pre-compiled regex to pull a candidate timestamp token from the start of a line.
_TS_RE = re.compile(
    r"^[\[\s]*"
    r"(\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:[+-]\d{2}:?\d{2}|Z)?)"
    r"|^[\[\s]*"
    r"([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
    r"|^[\[\s]*"
    r"(\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2})"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ScanMatch:
    """A single matched occurrence within a log file.

    Attributes:
        line_number: 1-based line number where the match was found.
        timestamp: Extracted timestamp string, or ``None`` if not parseable.
        severity: Severity level of the matching pattern.
        pattern_name: Name of the :class:`~logwatch.patterns.Pattern` that matched.
        raw_line: The full original log line.
        matched_text: The substring that the regex matched.
    """

    line_number: int
    timestamp: Optional[str]
    severity: str
    pattern_name: str
    raw_line: str
    matched_text: str


@dataclass
class ScanResult:
    """Aggregate result of scanning a single log file.

    Attributes:
        file_path: Absolute or relative path to the scanned file.
        total_lines: Number of lines read from the file.
        matches: List of individual :class:`ScanMatch` instances.
        summary: Counts per severity level (e.g. ``{"ERROR": 12, …}``).
        scan_time: Wall-clock duration of the scan in seconds.
        start_time: ISO-formatted start timestamp.
        end_time: ISO-formatted end timestamp.
    """

    file_path: str
    total_lines: int
    matches: List[ScanMatch] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    scan_time: float = 0.0
    start_time: str = ""
    end_time: str = ""


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class Scanner:
    """High-level log scanner.

    Loads configuration, compiles built-in + any custom patterns, and
    provides a :meth:`scan_file` method that produces :class:`ScanResult`
    objects.

    Args:
        config: An optional pre-loaded configuration dictionary.  If
            ``None``, :data:`~logwatch.config.DEFAULT_CONFIG` is used.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = config or DEFAULT_CONFIG
        self._patterns: List[Tuple[Pattern, re.Pattern]] = get_default_patterns()

        # Append any custom patterns supplied through the config.
        custom_patterns = self.config.get("custom_patterns", [])
        if custom_patterns:
            extra = [
                Pattern(
                    name=p.get("name", "custom"),
                    regex=p["regex"],
                    severity=p.get("severity", "INFO"),
                    description=p.get("description", "Custom pattern"),
                )
                for p in custom_patterns
            ]
            self._patterns.extend(compile_patterns(extra))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def scan_file(
        self,
        file_path: str | os.PathLike,
        filters: Optional[Dict[str, Any]] = None,
    ) -> ScanResult:
        """Scan a single log file and return structured results.

        Args:
            file_path: Path to the log file.
            filters: Optional filter overrides.  Keys may include
                ``severity``, ``date_from``, ``date_to``,
                ``keyword_include``, and ``keyword_exclude``.

        Returns:
            A :class:`ScanResult` populated with all matches.
        """
        file_path_str = str(file_path)
        encoding = self.config.get("scanner", {}).get("encoding", "utf-8")
        max_line = self.config.get("scanner", {}).get("max_line_length", 10_000)

        effective_filters = dict(self.config.get("filters", {}))
        if filters:
            effective_filters.update(filters)

        matches: List[ScanMatch] = []
        total_lines = 0

        start_wall = time.time()
        start_ts = datetime.now().isoformat()

        try:
            with open(file_path_str, "r", encoding=encoding, errors="replace") as fh:
                for line_number, raw_line in enumerate(fh, start=1):
                    total_lines += 1

                    # Truncate excessively long lines.
                    line = raw_line[:max_line]

                    timestamp = self._extract_timestamp(line)

                    for pattern, compiled in self._patterns:
                        m = compiled.search(line)
                        if m:
                            match = ScanMatch(
                                line_number=line_number,
                                timestamp=timestamp,
                                severity=pattern.severity,
                                pattern_name=pattern.name,
                                raw_line=raw_line.rstrip("\n\r"),
                                matched_text=m.group(0),
                            )
                            if self._apply_filters(match, effective_filters):
                                matches.append(match)
        except FileNotFoundError:
            logger.error("File not found: %s", file_path_str)
        except PermissionError:
            logger.error("Permission denied: %s", file_path_str)
        except OSError as exc:
            logger.error("OS error reading %s: %s", file_path_str, exc)

        end_wall = time.time()
        end_ts = datetime.now().isoformat()

        return ScanResult(
            file_path=file_path_str,
            total_lines=total_lines,
            matches=matches,
            summary=self._build_summary(matches),
            scan_time=round(end_wall - start_wall, 4),
            start_time=start_ts,
            end_time=end_ts,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_timestamp(line: str) -> Optional[str]:
        """Try to extract a timestamp string from the beginning of *line*.

        Returns the matched substring on success, or ``None``.
        """
        ts_match = _TS_RE.search(line)
        if not ts_match:
            return None

        raw_ts = next((g for g in ts_match.groups() if g is not None), None)
        if raw_ts is None:
            return None

        # Validate by attempting to parse with known formats.
        for fmt in _TIMESTAMP_FORMATS:
            try:
                datetime.strptime(raw_ts, fmt)
                return raw_ts
            except ValueError:
                continue

        # Return the raw string even if we cannot parse it — the caller
        # may still find it useful.
        return raw_ts

    @staticmethod
    def _apply_filters(match: ScanMatch, filters: Dict[str, Any]) -> bool:
        """Return ``True`` if *match* passes all *filters*.

        Supported filter keys:

        - ``severity`` — list of allowed severity strings.
        - ``date_from`` / ``date_to`` — ISO date strings for range filtering.
        - ``keyword_include`` — list of substrings; at least one must appear.
        - ``keyword_exclude`` — list of substrings; none may appear.
        """
        # Severity filter
        allowed_severities = filters.get("severity")
        if allowed_severities and match.severity not in allowed_severities:
            return False

        # Date range filters
        if match.timestamp:
            try:
                ts = datetime.fromisoformat(match.timestamp)
            except (ValueError, TypeError):
                ts = None

            if ts:
                date_from = filters.get("date_from")
                if date_from:
                    try:
                        if ts < datetime.fromisoformat(str(date_from)):
                            return False
                    except (ValueError, TypeError):
                        pass

                date_to = filters.get("date_to")
                if date_to:
                    try:
                        if ts > datetime.fromisoformat(str(date_to)):
                            return False
                    except (ValueError, TypeError):
                        pass

        # Keyword include — at least one keyword must appear in the line
        kw_include = filters.get("keyword_include", [])
        if kw_include:
            line_lower = match.raw_line.lower()
            if not any(kw.lower() in line_lower for kw in kw_include):
                return False

        # Keyword exclude — none of the keywords may appear
        kw_exclude = filters.get("keyword_exclude", [])
        if kw_exclude:
            line_lower = match.raw_line.lower()
            if any(kw.lower() in line_lower for kw in kw_exclude):
                return False

        return True

    @staticmethod
    def _build_summary(matches: List[ScanMatch]) -> Dict[str, int]:
        """Build a severity → count mapping from a list of matches."""
        summary: Dict[str, int] = {}
        for m in matches:
            summary[m.severity] = summary.get(m.severity, 0) + 1
        return summary
