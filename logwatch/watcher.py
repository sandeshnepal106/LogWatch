"""Continuous file monitoring (tail-and-scan).

Watches a log file for new lines, periodically scans the buffer, and
optionally triggers email alerts when thresholds are exceeded.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from logwatch.alerter import EmailAlerter
from logwatch.config import DEFAULT_CONFIG
from logwatch.reporter import ConsoleReporter
from logwatch.scanner import Scanner

logger = logging.getLogger(__name__)


class LogWatcher:
    """Continuously monitors a single log file for new content.

    New lines are buffered and scanned at a configurable interval.  When
    alerting is enabled the :class:`~logwatch.alerter.EmailAlerter` is
    consulted after each scan cycle.

    Args:
        file_path: Path to the log file to watch.
        config: Optional pre-loaded configuration dictionary.
        alert_enabled: Whether to enable email alerting.
        check_interval: Seconds between scan cycles (default 30).
    """

    def __init__(
        self,
        file_path: str,
        config: Optional[Dict[str, Any]] = None,
        alert_enabled: bool = True,
        check_interval: int = 30,
    ) -> None:
        self.file_path: str = str(file_path)
        self.config: Dict[str, Any] = config or DEFAULT_CONFIG
        self.check_interval: int = check_interval

        self._scanner = Scanner(config=self.config)
        self._reporter = ConsoleReporter()
        self._alerter: Optional[EmailAlerter] = (
            EmailAlerter(self.config) if alert_enabled else None
        )

        self._running: bool = False
        self._last_inode: Optional[int] = None
        self._last_size: int = 0

        # Register signal handlers for graceful shutdown.
        if sys.platform != "win32":
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        else:
            # On Windows SIGTERM is limited; rely on SIGINT (Ctrl-C).
            signal.signal(signal.SIGINT, self._handle_signal)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Begin watching the log file.

        The method blocks until :meth:`stop` is called (either directly or
        via a signal handler).  New lines are polled every **1 second** and
        the accumulated buffer is scanned every :attr:`check_interval`
        seconds.
        """
        self._running = True
        self._log_status(f"Watching {self.file_path} (interval={self.check_interval}s)")

        if not os.path.isfile(self.file_path):
            self._log_status(f"File not found — waiting for creation: {self.file_path}")

        # Wait for the file to appear.
        while self._running and not os.path.isfile(self.file_path):
            time.sleep(1)

        if not self._running:
            return

        # Open and seek to end.
        fh = open(self.file_path, "r", encoding="utf-8", errors="replace")
        fh.seek(0, os.SEEK_END)
        self._update_file_meta()

        buffer: List[str] = []
        last_scan_time = time.time()

        try:
            while self._running:
                # Check for file rotation.
                if self._file_rotated():
                    self._log_status("File rotation detected — reopening.")
                    fh.close()
                    fh = open(
                        self.file_path, "r", encoding="utf-8", errors="replace"
                    )
                    self._update_file_meta()

                line = fh.readline()
                if line:
                    buffer.append(line)
                else:
                    time.sleep(1)

                # Periodically scan the buffer.
                elapsed = time.time() - last_scan_time
                if buffer and elapsed >= self.check_interval:
                    self._process_buffer(buffer)
                    buffer.clear()
                    last_scan_time = time.time()
        except KeyboardInterrupt:
            self._log_status("Interrupted by user.")
        finally:
            # Flush any remaining buffer.
            if buffer:
                self._process_buffer(buffer)
            fh.close()
            self._log_status("Watcher stopped.")

    def stop(self) -> None:
        """Request the watcher to shut down gracefully."""
        self._running = False

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Signal handler that triggers a graceful shutdown."""
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        self._log_status(f"Received {sig_name} — shutting down.")
        self.stop()

    def _process_buffer(self, lines: List[str]) -> None:
        """Scan buffered lines, print a mini-report, and optionally alert.

        A temporary file is written with the buffered content so the
        :class:`~logwatch.scanner.Scanner` can process it via its normal
        file-based API.  For efficiency, the lines are written to a
        temporary on-disk file.

        Args:
            lines: Raw log lines accumulated since the last scan.
        """
        import tempfile

        self._log_status(f"Scanning buffer ({len(lines)} new lines)…")

        # Write buffer to a temp file for the scanner.
        tmp_path: Optional[str] = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".log", prefix="logwatch_buf_")
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_fh:
                tmp_fh.writelines(lines)

            result = self._scanner.scan_file(tmp_path)
            # Override file_path with the real watched file.
            result.file_path = self.file_path

            if result.matches:
                self._reporter.report(result)

                # Trigger alert if applicable.
                if self._alerter and self._alerter.should_alert(result):
                    self._alerter.send_alert(result)
            else:
                self._log_status("No notable events in this cycle.")
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    def _file_rotated(self) -> bool:
        """Detect whether the watched file has been rotated or truncated.

        Rotation is inferred by a size decrease or an inode change (on
        systems that support inodes).
        """
        try:
            stat = os.stat(self.file_path)
        except OSError:
            return False

        current_size = stat.st_size

        # Check inode change (Unix-like systems).
        current_inode = getattr(stat, "st_ino", None)
        if current_inode and self._last_inode and current_inode != self._last_inode:
            self._update_file_meta()
            return True

        # Check if the file was truncated (size decreased).
        if current_size < self._last_size:
            self._update_file_meta()
            return True

        self._last_size = current_size
        return False

    def _update_file_meta(self) -> None:
        """Refresh cached file metadata (size, inode)."""
        try:
            stat = os.stat(self.file_path)
            self._last_size = stat.st_size
            self._last_inode = getattr(stat, "st_ino", None)
        except OSError:
            self._last_size = 0
            self._last_inode = None

    @staticmethod
    def _log_status(message: str) -> None:
        """Print a timestamped status message to *stdout*."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] LogWatch: {message}")
