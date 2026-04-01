#!/usr/bin/env python3
"""服务健康报告 - 读取状态文件和日志，生成人类可读简报"""

import json
import os
from datetime import datetime

STATE_FILE = "/Users/dc/.openclaw/workspace-captain/memory/service_health_state.json"
LOG_FILE = "/Users/dc/.openclaw/workspace-captain/logs/service_health.log"

def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE) as f:
        return json.load(f)

def load_recent_logs(n=30):
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        lines = f.readlines()
    return lines[-n:]

def main():
    print("=" * 50)
    print("  📊 服务健康监控报告")
    print("=" * 50)

    state = load_state()
    if state:
        last_check = state.get("last_check", "未知")
        print(f"\n🕐 最新检查时间: {last_check}\n")
        print("📋 各服务状态:")
        for r in state.get("results", []):
            status = "✅ 正常" if r["http_ok"] else "❌ 异常"
            proc = f" (进程 {'✅' if r['proc_ok'] else '❌'})" if r["proc_ok"] is not None else ""
            print(f"   • {r['name']}:{r['port']} - {status}{proc}")
    else:
        print("\n⚠️ 暂无状态数据，请先运行健康检查脚本")

    print(f"\n📜 最近日志 (共30条):")
    print("-" * 50)
    recent = load_recent_logs(30)
    if recent:
        for line in recent:
            print(line.rstrip())
    else:
        print("(暂无日志)")

    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()
