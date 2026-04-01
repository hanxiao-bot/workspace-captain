#!/bin/bash
# 设置数据库监控 cron：每天 06:00 和 18:00 运行健康检查

SCRIPT="/Users/dc/.openclaw/workspace-captain/automation/db_health_monitor.py"
LOG="/Users/dc/.openclaw/workspace-captain/logs/db_cron.log"
PYTHON="/usr/bin/python3"
CRON_LINE="0 6,18 * * * $PYTHON $SCRIPT >> $LOG 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "db_health_monitor.py"; then
    echo "✅ cron 已存在，无需重复添加"
    exit 0
fi

# 添加新的 cron 任务
( crontab -l 2>/dev/null; echo "$CRON_LINE" ) | crontab -
echo "✅ cron 已添加：每天 06:00 和 18:00 运行健康检查"
crontab -l | grep db_health
