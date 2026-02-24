#!/usr/bin/env python3

import subprocess
import csv

NODES_FILE = "nodes.txt"
OUTPUT_FILE = "cluster_health_report.csv"


def run_remote_command(node, command):
    try:
        result = subprocess.check_output(
            f"ssh {node} '{command}'",
            shell=True,
            text=True
        )
        return result.strip()
    except subprocess.CalledProcessError:
        return "ERROR"


def collect_health(node):
    return {
        "node": node,
        "uptime": run_remote_command(node, "uptime -p"),
        "memory": run_remote_command(node, "free -h | awk '/Mem:/ {print $3 \"/\" $2}'"),
        "disk": run_remote_command(node, "df -h / | awk 'NR==2 {print $5}'")
    }


def main():
    with open(NODES_FILE) as f:
        nodes = [line.strip() for line in f if line.strip()]

    results = []

    for node in nodes:
        print(f"[+] Collecting data from {node}")
        results.append(collect_health(node))

    with open(OUTPUT_FILE, "w", newline="") as csvfile:
        fieldnames = ["node", "uptime", "memory", "disk"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(results)

    print(f"\nReport saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

