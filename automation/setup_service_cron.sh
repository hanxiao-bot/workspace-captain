#!/bin/bash
# 设置服务健康监控 cron：每15分钟运行一次
CRON_CMD="*/15 * * * * /usr/bin/python3 /Users/dc/.openclaw/workspace-captain/automation/service_health_monitor.py >> /Users/dc/.openclaw/workspace-captain/logs/service_cron.log 2>&1"

if crontab -l 2>/dev/null | grep -q "service_health_monitor.py"; then
    echo "cron 已存在，跳过"
else
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo "cron 已添加"
fi
