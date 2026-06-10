"""Built-in regex patterns for common log formats.

Provides a library of pre-defined patterns for detecting errors, warnings,
and other notable events in application and server logs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Pattern:
    """A single log-matching pattern.

    Attributes:
        name: Human-readable identifier for the pattern.
        regex: Raw regex string used to match log lines.
        severity: One of CRITICAL, ERROR, WARNING, or INFO.
        description: Brief explanation of what this pattern detects.
    """

    name: str
    regex: str
    severity: str  # CRITICAL | ERROR | WARNING | INFO
    description: str


# ---------------------------------------------------------------------------
# Default pattern library
# ---------------------------------------------------------------------------

DEFAULT_PATTERNS: List[Pattern] = [
    Pattern(
        name="critical_fatal",
        regex=r"(?i)\b(CRITICAL|FATAL)\b",
        severity="CRITICAL",
        description="Detects CRITICAL or FATAL log levels.",
    ),
    Pattern(
        name="error_level",
        regex=r"(?i)\bERROR\b",
        severity="ERROR",
        description="Detects ERROR log level.",
    ),
    Pattern(
        name="warning_level",
        regex=r"(?i)\b(WARNING|WARN)\b",
        severity="WARNING",
        description="Detects WARNING or WARN log levels.",
    ),
    Pattern(
        name="exception_traceback",
        regex=r"(?i)(Traceback|Exception|Error:\s)",
        severity="ERROR",
        description="Detects Python tracebacks, exceptions, and generic error messages.",
    ),
    Pattern(
        name="http_5xx",
        regex=(
            r"\bHTTP[/\s]?\d?\.?\d?\s*5\d{2}\b"
            r"|\b5\d{2}\s+(Internal|Bad Gateway|Service Unavailable|Gateway Timeout)"
        ),
        severity="ERROR",
        description="Detects HTTP 5xx server error responses.",
    ),
    Pattern(
        name="http_4xx",
        regex=(
            r"\bHTTP[/\s]?\d?\.?\d?\s*4\d{2}\b"
            r"|\b4\d{2}\s+(Not Found|Unauthorized|Forbidden|Bad Request)"
        ),
        severity="WARNING",
        description="Detects HTTP 4xx client error responses.",
    ),
    Pattern(
        name="connection_error",
        regex=r"(?i)(connection\s+(refused|reset|timed?\s*out)|ECONNREFUSED|ETIMEDOUT)",
        severity="ERROR",
        description="Detects connection failures (refused, reset, timeout).",
    ),
    Pattern(
        name="out_of_memory",
        regex=r"(?i)(out\s+of\s+memory|OOM|MemoryError|heap\s+space)",
        severity="CRITICAL",
        description="Detects out-of-memory conditions.",
    ),
    Pattern(
        name="disk_space",
        regex=r"(?i)(no\s+space\s+left|disk\s+full|ENOSPC)",
        severity="CRITICAL",
        description="Detects disk-space exhaustion.",
    ),
    Pattern(
        name="timeout",
        regex=r"(?i)(timeout|timed?\s*out|deadline\s+exceeded)",
        severity="WARNING",
        description="Detects timeout and deadline-exceeded events.",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compile_patterns(
    patterns_list: List[Pattern],
) -> List[Tuple[Pattern, re.Pattern]]:
    """Compile a list of *Pattern* objects into ``(Pattern, compiled_regex)`` tuples.

    Args:
        patterns_list: Iterable of :class:`Pattern` instances.

    Returns:
        A list of ``(Pattern, compiled re.Pattern)`` tuples ready for matching.
    """
    compiled: List[Tuple[Pattern, re.Pattern]] = []
    for pat in patterns_list:
        compiled.append((pat, re.compile(pat.regex)))
    return compiled


def get_default_patterns() -> List[Tuple[Pattern, re.Pattern]]:
    """Return the compiled default pattern set.

    This is a convenience wrapper around :func:`compile_patterns` using
    :data:`DEFAULT_PATTERNS`.
    """
    return compile_patterns(DEFAULT_PATTERNS)
