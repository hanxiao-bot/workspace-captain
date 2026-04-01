#!/usr/bin/env python3
"""服务健康监控 - 每15分钟检查一次，发现挂了立即尝试重启"""

import subprocess
import time
import json
import sys
from datetime import datetime

LOG_FILE = "/Users/dc/.openclaw/workspace-captain/logs/service_health.log"
STATE_FILE = "/Users/dc/.openclaw/workspace-captain/memory/service_health_state.json"

# 服务配置
SERVICES = [
    {
        "name": "Vue3 Frontend",
        "host": "localhost",
        "port": 5174,
        "check_path": "/",
        "start_cmd": "cd /Users/dc/.openclaw/workspace/clawd-stock-vue && /usr/bin/nohup /usr/local/bin/node /Users/dc/.openclaw/workspace/clawd-stock-vue/node_modules/.bin/vite --host 0.0.0.0 --port 5174 > /dev/null 2>&1 &",
        "pid": 17435
    },
    {
        "name": "FastAPI Backend",
        "host": "localhost",
        "port": 8000,
        "check_path": "/api/health",
        "start_cmd": "cd /Users/dc/clawd/stock-analysis-system && /usr/bin/nohup /usr/local/bin/python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &",
        "pid": 65140
    },
    {
        "name": "Ollama",
        "host": "localhost",
        "port": 11434,
        "check_path": "/api/version",
        "start_cmd": None,
        "pid": 1220
    },
    {
        "name": "Memos",
        "host": "localhost",
        "port": 5230,
        "check_path": "/",
        "start_cmd": None,
        "pid": 65761
    }
]

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def check_service(name, host, port, path):
    """检查服务是否响应"""
    import urllib.request
    import urllib.error
    url = f"http://{host}:{port}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200, None
    except urllib.error.HTTPError as e:
        return e.code in (200, 404), None
    except Exception as e:
        return False, str(e)

def is_process_running(pid):
    """检查进程是否存在"""
    try:
        subprocess.run(["ps", "-p", str(pid)], check=True, capture_output=True)
        return True
    except:
        return False

def restart_service(name, start_cmd, pid):
    """尝试重启服务"""
    if not start_cmd:
        log(f"  重启命令未知，跳过自动重启: {name}")
        return False

    log(f"  尝试重启 {name}...")

    # 如果有 PID，先 kill 旧进程
    if pid:
        try:
            subprocess.run(["kill", str(pid)], capture_output=True)
            time.sleep(1)
        except:
            pass

    # 启动新进程
    try:
        subprocess.Popen(start_cmd, shell=True)
        time.sleep(3)
        return True
    except Exception as e:
        log(f"  重启失败: {e}")
        return False

def save_state(results):
    with open(STATE_FILE, "w") as f:
        json.dump({
            "last_check": datetime.now().isoformat(),
            "results": results
        }, f, ensure_ascii=False, indent=2)

def main():
    log("=== 服务健康检查开始 ===")

    all_ok = True
    results = []

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]

        if svc.get("pid"):
            proc_ok = is_process_running(svc["pid"])
        else:
            proc_ok = None

        http_ok, err = check_service(name, svc["host"], port, svc["check_path"])

        status = "✅" if http_ok else "❌"
        proc_str = f"[进程 {'✅' if proc_ok else '❌'}]" if proc_ok is not None else ""
        log(f"{status} {name} ({svc['host']}:{port}) {proc_str}")

        if err:
            log(f"   错误: {err}")

        if not http_ok:
            all_ok = False
            if svc.get("start_cmd"):
                restarted = restart_service(name, svc["start_cmd"], svc.get("pid"))
                if restarted:
                    time.sleep(2)
                    http_ok2, _ = check_service(name, svc["host"], port, svc["check_path"])
                    if http_ok2:
                        log(f"  ✅ 重启成功！")
                        http_ok = True

        results.append({
            "name": name,
            "port": port,
            "http_ok": http_ok,
            "proc_ok": proc_ok
        })

    save_state(results)

    if all_ok:
        log("✅ 所有服务正常")
    else:
        log("⚠️ 部分服务异常，请检查")

    log("=== 检查完成 ===\n")
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
