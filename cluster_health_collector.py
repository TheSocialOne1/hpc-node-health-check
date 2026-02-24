#!/usr/bin/env python3


import argparse
import json
import sys

#!/usr/bin/env python3

import subprocess
import csv
import re
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_NODES_FILE = "nodes.txt"


def run_command(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return "ERROR"


def run_remote_command(node, command):
    if node in ("localhost", "127.0.0.1"):
        return run_command(command)

    ssh_cmd = f"ssh -o BatchMode=yes -o ConnectTimeout=5 {node} '{command}'"
    return run_command(ssh_cmd)


def parse_disk_pct(disk_str):
    m = re.search(r"(\d+)%", disk_str)
    return int(m.group(1)) if m else None


def parse_load(uptime_str):
    m = re.search(r"load averages?:\s*([0-9.]+)", uptime_str)
    return float(m.group(1)) if m else None


def collect_health(node, disk_alert_pct, load_alert):
    uptime_cmd = "uptime"
    disk_cmd = "df -h / | awk 'NR==2 {print $5}'"

    if node in ("localhost", "127.0.0.1"):
        mem_cmd = "vm_stat | awk '/Pages free/ {print $3}' | tr -d '.'"
    else:
        mem_cmd = "free -h | awk '/Mem:/ {print $3 \"/\" $2}'"

    uptime_out = run_remote_command(node, uptime_cmd)
    disk_out = run_remote_command(node, disk_cmd)
    mem_out = run_remote_command(node, mem_cmd)

    disk_pct = parse_disk_pct(disk_out) if disk_out != "ERROR" else None
    load_1 = parse_load(uptime_out) if uptime_out != "ERROR" else None

    alerts = []
    errors = []

    if uptime_out == "ERROR":
        errors.append("UPTIME_ERROR")
    if disk_out == "ERROR":
        errors.append("DISK_ERROR")
    if mem_out == "ERROR":
        errors.append("MEM_ERROR")

    if disk_pct is not None and disk_pct >= disk_alert_pct:
        alerts.append(f"DISK>={disk_alert_pct}%")
    if load_1 is not None and load_1 >= load_alert:
        alerts.append(f"LOAD>={load_alert}")

    if errors:
        status = "ERROR"
    elif alerts:
        status = "ALERT"
    else:
        status = "OK"

    return {
        "node": node,
        "status": status,
        "alerts": alerts,
        "errors": errors,
        "load_1": load_1 if load_1 is not None else "",
        "disk_used_pct": f"{disk_pct}%" if disk_pct is not None else disk_out,
        "memory": mem_out,
        "uptime": uptime_out,
    }


def read_nodes(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def write_csv(path, results):
    with open(path, "w", newline="") as csvfile:
        fieldnames = ["node", "status", "alerts", "errors", "load_1", "disk_used_pct", "memory", "uptime"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                **r,
                "alerts": ";".join(r["alerts"]) if r["alerts"] else "",
                "errors": ";".join(r["errors"]) if r["errors"] else "",
            })


def main():
    p = argparse.ArgumentParser(description="Collect cluster health metrics over SSH and output CSV/JSON.")
    p.add_argument("--nodes", default=DEFAULT_NODES_FILE, help="Path to nodes file (one hostname per line).")
    p.add_argument("--out", default="cluster_health_report.csv", help="Output file path.")
    p.add_argument("--format", choices=["csv", "json"], default="csv", help="Output format.")
    p.add_argument("--disk-alert", type=int, default=80, help="Disk usage percent threshold for ALERT.")
    p.add_argument("--load-alert", type=float, default=5.0, help="Load threshold for ALERT.")
    p.add_argument("--workers", type=int, default=8, help="Parallel workers for fan-out.")
    args = p.parse_args()

    nodes = read_nodes(args.nodes)
    results = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(collect_health, node, args.disk_alert, args.load_alert): node for node in nodes}
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: r["node"])

    if args.format == "csv":
        write_csv(args.out, results)
    else:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)

    # Exit codes like monitoring tools
    statuses = {r["status"] for r in results}
    if "ERROR" in statuses:
        sys.exit(1)
    if "ALERT" in statuses:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3

import subprocess
import csv
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

NODES_FILE = "nodes.txt"
OUTPUT_FILE = "cluster_health_report.csv"

# Thresholds (tune as needed)
DISK_ALERT_PCT = 80
LOAD_ALERT = 5.0
MAX_WORKERS = 8


def run_command(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return "ERROR"


def run_remote_command(node, command):
    if node in ("localhost", "127.0.0.1"):
        return run_command(command)

    ssh_cmd = f"ssh -o BatchMode=yes -o ConnectTimeout=5 {node} '{command}'"
    return run_command(ssh_cmd)


def parse_disk_pct(disk_str):
    # expects like "33%"
    m = re.search(r"(\d+)%", disk_str)
    return int(m.group(1)) if m else None


def parse_load(uptime_str):
    # macOS: "load averages: 1.51 1.58 1.54"
    # Linux: "load average: 1.51, 1.58, 1.54"
    m = re.search(r"load averages?:\s*([0-9.]+)", uptime_str)
    return float(m.group(1)) if m else None


def collect_health(node):
    uptime_cmd = "uptime"
    disk_cmd = "df -h / | awk 'NR==2 {print $5}'"

    if node in ("localhost", "127.0.0.1"):
        mem_cmd = "vm_stat | awk '/Pages free/ {print $3}' | tr -d '.'"
    else:
        mem_cmd = "free -h | awk '/Mem:/ {print $3 \"/\" $2}'"

    uptime_out = run_remote_command(node, uptime_cmd)
    disk_out = run_remote_command(node, disk_cmd)
    mem_out = run_remote_command(node, mem_cmd)

    disk_pct = parse_disk_pct(disk_out) if disk_out != "ERROR" else None
    load_1 = parse_load(uptime_out) if uptime_out != "ERROR" else None

    alerts = []
    if disk_pct is not None and disk_pct >= DISK_ALERT_PCT:
        alerts.append(f"DISK>={DISK_ALERT_PCT}%")
    if load_1 is not None and load_1 >= LOAD_ALERT:
        alerts.append(f"LOAD>={LOAD_ALERT}")

    status = "OK" if not alerts else "ALERT"

    return {
        "node": node,
        "status": status,
        "alerts": ";".join(alerts) if alerts else "",
        "load_1": load_1 if load_1 is not None else "",
        "disk_used_pct": f"{disk_pct}%" if disk_pct is not None else disk_out,
        "uptime": uptime_out,
        "memory": mem_out,
    }


def main():
    with open(NODES_FILE) as f:
        nodes = [line.strip() for line in f if line.strip()]

    results = []

    # Parallel fan-out (HPC friendly)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(collect_health, node): node for node in nodes}
        for fut in as_completed(futures):
            node = futures[fut]
            print(f"[+] Collected: {node}")
            results.append(fut.result())

    # Stable output ordering
    results.sort(key=lambda r: r["node"])

    with open(OUTPUT_FILE, "w", newline="") as csvfile:
        fieldnames = ["node", "status", "alerts", "load_1", "disk_used_pct", "memory", "uptime"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nReport saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

