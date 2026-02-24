#!/usr/bin/env python3

import subprocess
import json
import platform
from datetime import datetime


def run_command(cmd):
    try:
        result = subprocess.check_output(cmd, shell=True, text=True)
        return result.strip()
    except subprocess.CalledProcessError:
        return "ERROR"


def get_uptime():
    if platform.system() == "Darwin":
        return run_command("uptime")
    else:
        return run_command("uptime -p")


def get_load():
    return run_command("uptime")


def get_memory():
    if platform.system() == "Darwin":
        return run_command("vm_stat | grep 'Pages active'")
    else:
        return run_command("free -h | awk '/Mem:/ {print $3 \"/\" $2}'")


def get_disk():
    return run_command("df -h / | awk 'NR==2 {print $3 \"/\" $2 \" (\" $5 \")\"}'")


def main():
    health_data = {
        "timestamp": datetime.now().isoformat(),
        "hostname": run_command("hostname"),
        "uptime": get_uptime(),
        "load_average": get_load(),
        "memory_usage": get_memory(),
        "root_disk_usage": get_disk(),
        "platform": platform.system()
    }

    print(json.dumps(health_data, indent=4))


if __name__ == "__main__":
    main()

