"""Email alert system for LogWatch.

Sends styled HTML email alerts via SMTP when error thresholds are exceeded,
with a configurable cooldown to prevent alert fatigue.
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from logwatch.scanner import ScanResult

logger = logging.getLogger(__name__)


class EmailAlerter:
    """Sends email alerts when a scan result exceeds the configured threshold.

    Args:
        config: The full LogWatch configuration dictionary (the ``alerts``
            section is read from here).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._alert_cfg: Dict[str, Any] = config.get("alerts", {})
        self._last_alert_time: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def should_alert(self, scan_result: ScanResult) -> bool:
        """Decide whether an alert should be sent for *scan_result*.

        An alert is triggered when:

        1. Alerting is enabled in configuration.
        2. The number of ERROR + CRITICAL matches meets or exceeds
           ``threshold_errors``.
        3. The cooldown period since the last alert has elapsed.

        Args:
            scan_result: The scan result to evaluate.

        Returns:
            ``True`` if an alert should be dispatched.
        """
        if not self._alert_cfg.get("enabled", False):
            return False

        error_count = scan_result.summary.get("ERROR", 0) + scan_result.summary.get(
            "CRITICAL", 0
        )
        threshold = self._alert_cfg.get("threshold_errors", 10)

        if error_count < threshold:
            return False

        return self._check_cooldown()

    def send_alert(self, scan_result: ScanResult) -> bool:
        """Send an HTML email alert for *scan_result*.

        Args:
            scan_result: The scan result to report.

        Returns:
            ``True`` if the email was sent successfully, ``False`` otherwise.
        """
        smtp_host = self._alert_cfg.get("smtp_host", "")
        smtp_port = int(self._alert_cfg.get("smtp_port", 587))
        smtp_user = self._alert_cfg.get("smtp_user", "")
        smtp_password = self._alert_cfg.get("smtp_password", "")
        use_tls = self._alert_cfg.get("use_tls", True)
        sender = self._alert_cfg.get("sender", "")
        recipients = self._alert_cfg.get("recipients", [])

        if not smtp_host or not recipients:
            logger.warning(
                "SMTP host or recipients not configured — skipping alert."
            )
            return False

        error_count = scan_result.summary.get("ERROR", 0) + scan_result.summary.get(
            "CRITICAL", 0
        )
        filename = os.path.basename(scan_result.file_path)

        subject = f"[LogWatch Alert] {error_count} errors detected in {filename}"
        html_body = self._build_html_body(scan_result)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html"))

        try:
            if use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(sender, recipients, msg.as_string())
            server.quit()

            self._last_alert_time = time.time()
            logger.info("Alert email sent to %s", ", ".join(recipients))
            return True

        except smtplib.SMTPException as exc:
            logger.error("SMTP error while sending alert: %s", exc)
            return False
        except OSError as exc:
            logger.error("Network error while sending alert: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _check_cooldown(self) -> bool:
        """Return ``True`` if enough time has passed since the last alert.

        The cooldown window is defined by ``cooldown_minutes`` in the
        alerts configuration section.
        """
        if self._last_alert_time is None:
            return True

        cooldown_seconds = self._alert_cfg.get("cooldown_minutes", 30) * 60
        elapsed = time.time() - self._last_alert_time
        return elapsed >= cooldown_seconds

    def _build_html_body(self, scan_result: ScanResult) -> str:
        """Build a styled HTML email body summarising *scan_result*.

        Args:
            scan_result: The scan result to render.

        Returns:
            An HTML string suitable for an email body.
        """
        filename = os.path.basename(scan_result.file_path)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build severity rows
        severity_rows = ""
        for severity in ("CRITICAL", "ERROR", "WARNING", "INFO"):
            count = scan_result.summary.get(severity, 0)
            color = {"CRITICAL": "#e74c3c", "ERROR": "#e67e22", "WARNING": "#f1c40f", "INFO": "#3498db"}.get(
                severity, "#95a5a6"
            )
            severity_rows += (
                f'<tr><td style="padding:6px 12px;border-bottom:1px solid #eee;">'
                f'<span style="color:{color};font-weight:bold;">{severity}</span></td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:right;">'
                f"{count}</td></tr>\n"
            )

        # Build top errors list
        from collections import Counter

        error_counter: Counter[str] = Counter()
        for m in scan_result.matches:
            if m.severity in ("ERROR", "CRITICAL"):
                error_counter[m.matched_text] += 1

        top_errors_html = ""
        for text, cnt in error_counter.most_common(10):
            escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            top_errors_html += f"<li><code>{escaped}</code> — {cnt} occurrence(s)</li>\n"

        if not top_errors_html:
            top_errors_html = "<li>No errors captured.</li>"

        github_url = os.environ.get(
            "LOGWATCH_GITHUB_URL", "https://github.com/logwatch"
        )

        return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#333;max-width:640px;margin:auto;">
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px;border-radius:8px 8px 0 0;">
    <h1 style="color:#fff;margin:0;font-size:22px;">🔔 LogWatch Alert</h1>
    <p style="color:#ccc;margin:4px 0 0;">Generated at {now_str}</p>
  </div>
  <div style="padding:20px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
    <h2 style="font-size:16px;">File: <code>{filename}</code></h2>
    <p>Scan completed in <strong>{scan_result.scan_time:.3f}s</strong>
       — <strong>{scan_result.total_lines:,}</strong> lines processed.</p>
    <h3 style="font-size:14px;">Severity Summary</h3>
    <table style="border-collapse:collapse;width:100%;">
      {severity_rows}
    </table>
    <h3 style="font-size:14px;margin-top:16px;">Top Errors</h3>
    <ol style="padding-left:20px;">
      {top_errors_html}
    </ol>
  </div>
  <p style="font-size:11px;color:#999;text-align:center;margin-top:12px;">
    Sent by LogWatch · <a href="{github_url}" style="color:#999;">GitHub</a>
  </p>
</body>
</html>"""
