# 🔍 LogWatch

```
 ╔═══════════════════════════════════════════════════════════╗
 ║                                                           ║
 ║   ██╗      ██████╗  ██████╗ ██╗    ██╗ █████╗ ████████╗  ║
 ║   ██║     ██╔═══██╗██╔════╝ ██║    ██║██╔══██╗╚══██╔══╝  ║
 ║   ██║     ██║   ██║██║  ███╗██║ █╗ ██║███████║   ██║     ║
 ║   ██║     ██║   ██║██║   ██║██║███╗██║██╔══██║   ██║     ║
 ║   ███████╗╚██████╔╝╚██████╔╝╚███╔███╔╝██║  ██║   ██║     ║
 ║   ╚══════╝ ╚═════╝  ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝     ║
 ║                                                           ║
 ║         DevOps Log Monitoring & Analysis Tool             ║
 ║                                                           ║
 ╚═══════════════════════════════════════════════════════════╝
```

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Dockerfile)
[![Version](https://img.shields.io/badge/Version-1.0.0-orange?style=for-the-badge)]()

**LogWatch** is a powerful, lightweight DevOps log monitoring and analysis tool built in Python. It scans log files for errors, warnings, and anomalies using built-in and custom regex patterns, then generates structured reports and optional email alerts — all deployable via Docker with cron-based scheduling.

---

## ✨ Features

- **🔎 Pattern-Based Scanning** — Detects errors, warnings, HTTP failures, stack traces, connection issues, and more using built-in regex patterns
- **📁 Multi-File Support** — Scan one or many log files in a single run with glob pattern support
- **👁️ Real-Time Watching** — Live `tail -f` style monitoring with instant pattern matching
- **📊 Structured Reports** — Export findings to CSV or JSON with timestamps, severity, source, and matched patterns
- **🚨 Email Alerts** — SMTP-based alerting with configurable thresholds, cooldowns, and recipient lists
- **⚙️ Flexible Configuration** — JSON and TOML config file support with environment variable overrides
- **🔧 Custom Patterns** — Add your own regex patterns for domain-specific log formats
- **📅 Date Range Filtering** — Filter scan results by date/time window
- **🏷️ Severity Filtering** — Include/exclude results by severity level
- **🔑 Keyword Filtering** — Include or exclude lines matching specific keywords
- **🐳 Docker Ready** — Production-ready Dockerfile and docker-compose with cron scheduling
- **💻 CLI Interface** — Clean command-line interface with three subcommands: `scan`, `watch`, `report`

---

## 🚀 Quick Start

### Local Installation

```bash
# Clone the repository
git clone https://github.com/your-org/logwatch.git
cd logwatch

# Install in development mode
pip install -e .

# Run a scan
logwatch scan /var/log/app.log

# Or use the module directly
python -m logwatch scan /var/log/app.log
```

### Docker

```bash
# Build and run with docker-compose
docker-compose up -d

# Or build and run manually
docker build -t logwatch .
docker run -v /var/log:/logs:ro -v ./reports:/reports logwatch scan /logs/app.log
```

---

## 📖 Usage

LogWatch provides three subcommands: **scan**, **watch**, and **report**.

### `scan` — Analyze Log Files

Scan one or more log files and output results to the console or a file.

```bash
# Basic scan
logwatch scan /var/log/app.log

# Scan multiple files with glob
logwatch scan /var/log/*.log

# Scan with custom config and CSV output
logwatch scan /var/log/app.log --config config/default.json --output report.csv

# Scan with severity filter
logwatch scan /var/log/app.log --severity ERROR CRITICAL

# Scan with date range
logwatch scan /var/log/app.log --from "2025-06-10 09:00:00" --to "2025-06-10 10:00:00"

# Scan with keyword filters
logwatch scan /var/log/app.log --include "database" --exclude "debug"

# Scan and send email alerts if thresholds are exceeded
logwatch scan /var/log/app.log --alert

# JSON output
logwatch scan /var/log/app.log --format json --output report.json
```

### `watch` — Real-Time Monitoring

Tail log files in real time and display matches as they appear.

```bash
# Watch a single file
logwatch watch /var/log/app.log

# Watch with severity filter
logwatch watch /var/log/app.log --severity ERROR CRITICAL WARNING

# Watch with alerts enabled
logwatch watch /var/log/app.log --alert --config config/default.json
```

### `report` — Generate Reports from Previous Scans

Re-process or combine existing scan results.

```bash
# Generate a summary report from a CSV
logwatch report reports/scan_20250610.csv

# Convert CSV results to JSON
logwatch report reports/scan_20250610.csv --format json --output summary.json
```

---

## ⚙️ Configuration

LogWatch supports configuration via **JSON** or **TOML** files. By default, it looks for `config/default.json` or `config/default.toml`.

### Configuration Sections

| Section       | Description                                           |
|---------------|-------------------------------------------------------|
| `general`     | Log level and date format settings                    |
| `scanner`     | Max line length, file encoding                        |
| `patterns`    | Custom regex patterns for domain-specific matching    |
| `filters`     | Severity, date range, and keyword filters             |
| `alerts`      | SMTP email alerting with thresholds and cooldowns     |
| `export`      | Default output format and directory                   |

### Example Configuration (JSON)

```json
{
  "general": {
    "log_level": "INFO",
    "date_format": "%Y-%m-%d %H:%M:%S"
  },
  "scanner": {
    "max_line_length": 10000,
    "encoding": "utf-8"
  },
  "patterns": {
    "custom": [
      "(?i)payment\\s+failed",
      "(?i)ssl\\s+handshake\\s+error"
    ]
  },
  "filters": {
    "severity": ["CRITICAL", "ERROR", "WARNING"],
    "date_from": "2025-06-10 00:00:00",
    "date_to": "2025-06-10 23:59:59",
    "keyword_include": ["database", "auth"],
    "keyword_exclude": ["healthcheck"]
  },
  "alerts": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "devops@example.com",
    "smtp_password": "app-password-here",
    "use_tls": true,
    "sender": "devops@example.com",
    "recipients": ["oncall@example.com", "team-lead@example.com"],
    "threshold_errors": 10,
    "threshold_window_minutes": 5,
    "cooldown_minutes": 30
  },
  "export": {
    "format": "csv",
    "output_dir": "./reports"
  }
}
```

### TOML Support

LogWatch also supports TOML configuration (requires `tomli` on Python < 3.11):

```toml
[general]
log_level = "INFO"
date_format = "%Y-%m-%d %H:%M:%S"

[patterns]
custom = [
    "(?i)payment\\s+failed",
    "(?i)ssl\\s+handshake\\s+error"
]
```

---

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

1. **Configure environment variables** in `docker-compose.yml` or use a `.env` file.

2. **Mount your log directory** by editing the volumes section:
   ```yaml
   volumes:
     - /path/to/your/logs:/logs:ro
   ```

3. **Build and start**:
   ```bash
   docker-compose up -d
   ```

4. **View cron output**:
   ```bash
   docker logs -f logwatch-monitor
   ```

5. **Run an ad-hoc scan**:
   ```bash
   docker-compose exec logwatch logwatch scan /logs/app.log
   ```

### Cron Schedule

By default, the Docker container runs a scan every **15 minutes** via cron. The schedule is defined in the `crontab` file:

```
*/15 * * * * root python -m logwatch scan /logs/*.log --config /app/config/default.json --output /reports/scan_YYYYMMDD_HHMM.csv --alert
```

To modify the schedule, edit the `crontab` file before building.

---

## 🌐 Environment Variables

All configuration values can be overridden via environment variables:

| Variable                   | Description                       | Default                        |
|----------------------------|-----------------------------------|--------------------------------|
| `LOGWATCH_CONFIG`          | Path to config file               | `/app/config/default.json`     |
| `LOGWATCH_LOG_DIR`         | Directory containing log files    | `/logs`                        |
| `LOGWATCH_REPORT_DIR`      | Directory for report output       | `/reports`                     |
| `LOGWATCH_SMTP_HOST`       | SMTP server hostname              | `smtp.gmail.com`               |
| `LOGWATCH_SMTP_PORT`       | SMTP server port                  | `587`                          |
| `LOGWATCH_SMTP_USER`       | SMTP authentication username      | —                              |
| `LOGWATCH_SMTP_PASSWORD`   | SMTP authentication password      | —                              |
| `LOGWATCH_SENDER`          | Alert email sender address        | —                              |
| `LOGWATCH_RECIPIENTS`      | Comma-separated recipient list    | —                              |

---

## 🔧 Custom Patterns

Add your own regex patterns to match domain-specific log entries. Patterns are defined in the config file under `patterns.custom`:

```json
{
  "patterns": {
    "custom": [
      "(?i)payment\\s+(failed|declined|error)",
      "(?i)ssl\\s+(handshake|certificate)\\s+(error|failed|expired)",
      "(?i)rate\\s+limit\\s+exceeded",
      "DEADLOCK\\s+DETECTED"
    ]
  }
}
```

Each pattern is a standard Python regex. Use `(?i)` for case-insensitive matching.

---

## 📋 Built-in Patterns

LogWatch ships with the following built-in detection patterns:

| Pattern Name          | Description                                 | Example Match                                |
|-----------------------|---------------------------------------------|----------------------------------------------|
| `ERROR`               | Lines containing ERROR severity             | `ERROR [db-pool] Connection failed`          |
| `WARNING`             | Lines containing WARNING severity           | `WARNING [api] High memory usage`            |
| `CRITICAL`            | Lines containing CRITICAL severity          | `CRITICAL [app] Out of memory`               |
| `HTTP 5xx`            | HTTP 500-599 status codes                   | `HTTP 503 Service Unavailable`               |
| `HTTP 4xx`            | HTTP 400-499 status codes                   | `HTTP 404 Not Found`                         |
| `Exception`           | Exception/Error class names                 | `NullPointerException`, `KeyError`           |
| `Traceback`           | Python-style traceback blocks               | `Traceback (most recent call last):`         |
| `Connection Error`    | Connection failures and timeouts            | `ConnectionTimeoutError`, `ETIMEDOUT`        |
| `Out of Memory`       | OOM conditions                              | `OutOfMemoryError`, `heap exceeded`          |
| `Disk Space`          | Disk full / low space warnings              | `No space left on device`                    |
| `Permission Denied`   | Access / permission errors                  | `PermissionError`, `Access denied`           |
| `Timeout`             | General timeout patterns                    | `TimeoutError`, `timed out`                  |
| `Stack Overflow`      | Stack overflow errors                       | `StackOverflowError`                         |
| `Segfault`            | Segmentation fault signals                  | `SIGSEGV`, `Segmentation fault`              |
| `Kill Signal`         | Process kill signals                        | `SIGKILL`, `OOM killer`                      |

---

## 📁 Project Structure

```
LogWatch/
├── config/
│   ├── default.json          # Default JSON configuration
│   └── default.toml          # Default TOML configuration
├── logwatch/
│   ├── __init__.py           # Package initialization
│   ├── __main__.py           # Module entry point
│   ├── cli.py                # CLI argument parsing
│   ├── config.py             # Configuration loader
│   ├── scanner.py            # Log scanning engine
│   ├── watcher.py            # Real-time file watcher
│   ├── patterns.py           # Built-in regex patterns
│   ├── filters.py            # Severity/date/keyword filters
│   ├── alerter.py            # SMTP email alerting
│   └── exporter.py           # CSV/JSON report exporter
├── sample_logs/
│   └── app.log               # Sample log file for testing
├── scripts/
│   └── entrypoint.sh         # Docker entrypoint script
├── reports/                  # Generated reports (git-ignored)
├── crontab                   # Cron schedule for Docker
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile                # Docker build file
├── .dockerignore             # Docker build exclusions
├── requirements.txt          # Python dependencies
├── setup.py                  # Package setup
└── README.md                 # This file
```

---

## 📄 License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2025 LogWatch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<p align="center">
  Built with ❤️ for DevOps teams who are tired of grepping logs manually.
</p>
