#!/usr/bin/env python3
"""飞书告警通知脚本"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 尝试读取飞书 webhook 配置
CONFIG_FILE = Path("/Users/dc/.openclaw/workspace-captain/memory/feishu_webhook.json")

def load_webhook():
    """加载飞书 webhook 配置"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f).get("webhook_url")
    return None

def send_feishu(status, message):
    """发送飞书消息"""
    webhook = load_webhook()
    if not webhook:
        print(f"[Feishu] 未配置 webhook，跳过通知 | status={status} | {message}")
        return

    try:
        import urllib.request
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"🚨 数据库监控告警\n状态: {status}\n消息: {message}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[Feishu] 发送成功: {resp.read().decode()}")
    except Exception as e:
        print(f"[Feishu] 发送失败: {e}")

if __name__ == "__main__":
    status = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    message = sys.argv[2] if len(sys.argv) > 2 else ""
    send_feishu(status, message)
