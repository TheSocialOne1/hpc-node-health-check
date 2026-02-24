#!/usr/bin/env python3

import subprocess
import csv

NODES_FILE = "nodes.txt"
OUTPUT_FILE = "cluster_health_report.csv"


def run_command(cmd):
    """Run a local shell command and return output."""
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return "ERROR"


def run_remote_command(node, command):
    """
    Run a command locally if node is localhost,
    otherwise run via SSH.
    """
    if node in ("localhost", "127.0.0.1"):
        return run_command(command)

    # BatchMode avoids password prompts; fail fast if no key auth
    ssh_cmd = f"ssh -o BatchMode=yes -o ConnectTimeout=5 {node} '{command}'"
    return run_command(ssh_cmd)


def collect_health(node):
    # Use cross-platform-ish commands for disk and uptime
    uptime_cmd = "uptime"  # works on macOS and Linux
    disk_cmd = "df -h / | awk 'NR==2 {print $5}'"

    # Memory command differs per OS; for Linux nodes this will work.
    # For localhost on macOS we’ll use vm_stat so you can demo.
    if node in ("localhost", "127.0.0.1"):
        mem_cmd = "vm_stat | awk '/Pages free/ {print $3}' | tr -d '.'"
    else:
        mem_cmd = "free -h | awk '/Mem:/ {print $3 \"/\" $2}'"

    return {
        "node": node,
        "uptime": run_remote_command(node, uptime_cmd),
        "memory": run_remote_command(node, mem_cmd),
        "disk_used_pct": run_remote_command(node, disk_cmd),
    }


def main():
    with open(NODES_FILE) as f:
        nodes = [line.strip() for line in f if line.strip()]

    results = []

    for node in nodes:
        print(f"[+] Collecting data from {node}")
        results.append(collect_health(node))

    with open(OUTPUT_FILE, "w", newline="") as csvfile:
        fieldnames = ["node", "uptime", "memory", "disk_used_pct"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nReport saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

