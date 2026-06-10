#!/bin/bash
set -e

echo "========================================"
echo "  LogWatch — DevOps Log Monitor v1.0.0"
echo "========================================"
echo ""

# Pass environment variables to cron
printenv | grep -E '^LOGWATCH_' > /etc/environment_logwatch
echo "SHELL=/bin/bash" > /etc/cron.d/logwatch-env
echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" >> /etc/cron.d/logwatch-env

# Source env vars into cron
sed -i '1s|^|BASH_ENV=/etc/environment_logwatch\n|' /etc/cron.d/logwatch-cron

# Apply crontab
crontab /etc/cron.d/logwatch-cron
echo "[*] Cron schedule installed:"
echo "    - Scanning /logs/*.log every 15 minutes"
echo "    - Reports saved to /reports/"
echo ""

# Handle command
if [ "$1" = "cron" ]; then
    echo "[*] Starting cron daemon..."
    echo "[*] Logs: tail -f /var/log/cron.log"
    echo ""
    # Run initial scan
    echo "[*] Running initial scan..."
    python -m logwatch scan /logs/*.log --config ${LOGWATCH_CONFIG:-/app/config/default.json} 2>&1 || true
    echo ""
    echo "[*] Cron daemon running. Waiting for scheduled jobs..."
    cron -f
elif [ "$1" = "scan" ]; then
    shift
    python -m logwatch scan "$@"
elif [ "$1" = "watch" ]; then
    shift
    python -m logwatch watch "$@"
else
    exec "$@"
fi
