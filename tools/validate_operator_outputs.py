#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path

MOBILE_PROBES = [
    ipaddress.ip_network("2409:8000::/20"),
    ipaddress.ip_network("2409:2000::/31"),
]


def load(path: Path):
    result = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        result.append(ipaddress.ip_network(line, strict=False))
    return result


def overlaps_any(networks, probe):
    return [str(network) for network in networks if network.overlaps(probe)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--baseline-dir", type=Path)
    parser.add_argument("--report", type=Path, default=Path("validation-report.json"))
    args = parser.parse_args()

    unicom = load(args.output_dir / "chinaunicom_v6.txt")
    mobile = load(args.output_dir / "chinamobile_v6.txt")
    baseline_unicom = (
        load(args.baseline_dir / "chinaunicom_v6.txt") if args.baseline_dir else []
    )
    baseline_mobile = (
        load(args.baseline_dir / "chinamobile_v6.txt") if args.baseline_dir else []
    )

    report = {
        "counts": {
            "generated": {
                "chinaunicom_v6": len(unicom),
                "chinamobile_v6": len(mobile),
            },
            "baseline": {
                "chinaunicom_v6": len(baseline_unicom),
                "chinamobile_v6": len(baseline_mobile),
            } if args.baseline_dir else None,
        },
        "mobile_probe_results": [],
        "violations": [],
    }

    mobile_seen = False
    for probe in MOBILE_PROBES:
        u_hits = overlaps_any(unicom, probe)
        m_hits = overlaps_any(mobile, probe)
        if m_hits:
            mobile_seen = True
        entry = {
            "probe": str(probe),
            "generated_unicom_overlaps": u_hits,
            "generated_mobile_overlaps": m_hits,
        }
        if args.baseline_dir:
            entry.update({
                "baseline_unicom_overlaps": overlaps_any(baseline_unicom, probe),
                "baseline_mobile_overlaps": overlaps_any(baseline_mobile, probe),
            })
        report["mobile_probe_results"].append(entry)
        if u_hits:
            report["violations"].append(
                f"China Unicom output still overlaps China Mobile probe {probe}: {u_hits}"
            )

    if not mobile_seen:
        report["violations"].append(
            "The sampled collector did not produce any expected China Mobile IPv6 probe prefix"
        )

    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
