#!/usr/bin/env python3
"""数据库健康监控 + 自动修复"""

import sqlite3
import subprocess
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/Users/dc/clawd/stock-analysis-system/data/stocks.db")
UPDATE_SCRIPT = Path("/Users/dc/clawd/stock-analysis-system/scripts/update_daily_data.py")
STATE_FILE = Path("/Users/dc/.openclaw/workspace-captain/memory/db_health_state.json")
LOG_FILE = Path("/Users/dc/.openclaw/workspace-captain/logs/db_health.log")
FEISHU_NOTIFY = Path("/Users/dc/.openclaw/workspace-captain/automation/notify_feishu.py")

def get_latest_trade_date():
    """查询数据库最新交易日期"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT MAX(trade_date) FROM stock_daily")
        result = cur.fetchone()[0]
        conn.close()
        return result
    except Exception as e:
        log(f"查询失败: {e}")
        return None

def check_cron_running():
    """检查 cron 进程是否存在"""
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    return "update_daily_data" in result.stdout

def run_update_script():
    """运行数据更新脚本"""
    try:
        result = subprocess.run(
            ["python3", str(UPDATE_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def save_state(status, latest_date, action_taken):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "last_check": datetime.now().isoformat(),
        "status": status,
        "latest_trade_date": latest_date,
        "action_taken": action_taken
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def notify_feishu(status, message):
    """发送飞书告警"""
    if not FEISHU_NOTIFY.exists():
        return
    try:
        subprocess.run(
            ["python3", str(FEISHU_NOTIFY), status, message],
            capture_output=True,
            timeout=30
        )
    except Exception:
        pass

def main():
    log("=== 开始数据库健康检查 ===")

    # Step 1: 检查最新数据日期
    latest_date = get_latest_trade_date()
    today = datetime.now().strftime("%Y-%m-%d")

    if latest_date is None:
        log("❌ 数据库连接失败")
        save_state("error", None, "database_connection_failed")
        notify_feishu("error", "数据库连接失败，请检查 stocks.db 是否存在")
        return

    log(f"最新数据日期: {latest_date}，今日: {today}")

    # Step 2: 判断是否断更
    try:
        latest_dt = datetime.strptime(str(latest_date), "%Y-%m-%d")
        today_dt = datetime.strptime(today, "%Y-%m-%d")
        days_behind = (today_dt - latest_dt).days
    except Exception:
        days_behind = 999

    log(f"数据落后: {days_behind} 天")

    # Step 3: 根据情况处理
    if days_behind <= 1:
        log("✅ 数据正常，无需处理")
        save_state("healthy", latest_date, "none")
    else:
        log(f"⚠️ 数据断更 {days_behind} 天，尝试修复...")

        # 检查 cron 是否在跑
        cron_ok = check_cron_running()
        log(f"cron 进程状态: {'运行中' if cron_ok else '未运行'}")

        if not cron_ok:
            log("⚠️ cron 未运行，尝试重启...")
            save_state("warning", latest_date, "cron_not_running")

        # 尝试手动运行更新脚本补数据
        log("尝试手动运行数据更新脚本...")
        ok, stdout, stderr = run_update_script()

        if ok:
            new_date = get_latest_trade_date()
            log(f"✅ 数据更新成功！最新日期: {new_date}")
            save_state("fixed", new_date, "update_script_run")
            notify_feishu("fixed", f"数据已修复，最新日期: {new_date}")
        else:
            err_msg = stderr[:200] if stderr else "未知错误"
            log(f"❌ 数据更新失败: {err_msg}")
            save_state("failed", latest_date, f"update_failed: {err_msg[:100]}")
            notify_feishu("failed", f"数据更新失败 ({days_behind}天未更新): {err_msg}")

    log("=== 检查完成 ===\n")

if __name__ == "__main__":
    main()
