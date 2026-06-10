FROM python:3.12-slim

LABEL maintainer="LogWatch" \
      description="DevOps Log Monitoring Tool" \
      version="1.0.0"

# Install cron
RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY logwatch/ ./logwatch/
COPY config/ ./config/
COPY setup.py .

# Install the package
RUN pip install --no-cache-dir -e .

# Copy cron and entrypoint
COPY crontab /etc/cron.d/logwatch-cron
COPY scripts/entrypoint.sh /entrypoint.sh

# Set permissions
RUN chmod 0644 /etc/cron.d/logwatch-cron \
    && chmod +x /entrypoint.sh \
    && mkdir -p /logs /reports

# Create log file for cron output
RUN touch /var/log/cron.log

ENTRYPOINT ["/entrypoint.sh"]
CMD ["cron"]
