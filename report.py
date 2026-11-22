#!/usr/bin/env python3
"""Summarize validated CereX periodic-task timing captures."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def integer(record, key, minimum, maximum):
    value = record.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"invalid {key}")
    return value


def object_at(line, line_number):
    try:
        value = json.loads(line)
    except ValueError as error:
        raise ValueError(f"invalid JSON on line {line_number}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected an object on line {line_number}")
    return value


def summarize(path, budget_us, require_qnx):
    digest = hashlib.sha256()
    lateness = []
    last_cycle = 0
    with path.open("rb") as capture:
        line = capture.readline(1024)
        digest.update(line)
        header = object_at(line, 1)
        integer(header, "version", 1, 1)
        target = header.get("target")
        if target not in ("qnx-8", "posix-host") or (require_qnx and target != "qnx-8"):
            raise ValueError("expected a QNX 8 capture" if require_qnx else "unknown target")
        frequency = integer(header, "counter_hz", int(target == "qnx-8"), 2**64 - 1)
        if target == "posix-host" and frequency != 0:
            raise ValueError("POSIX capture has QNX counter metadata")
        sample_count = integer(header, "samples", 1, 10_000)
        period = integer(header, "period_ns", 1_000, 1_000_000_000)
        injection = integer(header, "injected_at", 0, sample_count)
        delay = integer(header, "delay_ns", 0, 1_000_000_000)
        if bool(injection) != bool(delay):
            raise ValueError("inconsistent delay metadata")
        for sample in range(1, sample_count + 1):
            line = capture.readline(1024)
            digest.update(line)
            sample_data = object_at(line, sample + 1)
            integer(sample_data, "sample", sample, sample)
            late_ns = integer(sample_data, "late_ns", 0, 2**64 - 1)
            cycle = integer(sample_data, "cycles", last_cycle, 2**64 - 1 if frequency else 0)
            if frequency and cycle == last_cycle:
                raise ValueError(f"QNX cycle counter did not advance at sample {sample}")
            lateness.append(late_ns)
            last_cycle = cycle
        if capture.read(1):
            raise ValueError("unexpected rows after the advertised sample count")

    exceedances = [index for index, late_ns in enumerate(lateness, 1) if late_ns > budget_us * 1000]
    return {
        "target_reported_by_probe": target,
        "capture_sha256": digest.hexdigest(),
        "sample_count": sample_count,
        "period_us": period / 1000,
        "jitter_budget_us": budget_us,
        "p95_lateness_us": sorted(lateness)[math.ceil(sample_count * 0.95) - 1] / 1000,
        "max_lateness_us": max(lateness) / 1000,
        "first_budget_miss": exceedances[0] if exceedances else None,
        "budget_miss_count": len(exceedances),
        "injected_delay": {"sample": injection, "duration_us": delay / 1000} if injection else None,
        "qnx_cycle_frequency_hz": frequency or None,
        "result": "miss" if exceedances else "pass",
    }


def compare(baseline_path, injected_path, budget_us, require_qnx):
    baseline = summarize(baseline_path, budget_us, require_qnx)
    injected = summarize(injected_path, budget_us, require_qnx)
    for field in ("target_reported_by_probe", "sample_count", "period_us", "qnx_cycle_frequency_hz"):
        if baseline[field] != injected[field]:
            raise ValueError(f"capture settings differ: {field}")

    if baseline["injected_delay"] is not None or injected["injected_delay"] is None:
        raise ValueError("comparison requires a clean capture followed by a capture with a configured delay")

    expected_sample = injected["injected_delay"]["sample"]
    confirmed = baseline["result"] == "pass" and injected["first_budget_miss"] == expected_sample
    return {
        "result": "injection_detected" if confirmed else "inconclusive",
        "expected_first_miss": expected_sample,
        "observed_first_miss": injected["first_budget_miss"],
        "baseline": baseline,
        "injected": injected,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--compare", type=Path, metavar="INJECTED_CAPTURE",
                        help="compare the baseline capture with a capture containing a configured delay")
    parser.add_argument("--budget-us", type=int, default=2500)
    parser.add_argument("--require-qnx", action="store_true")
    args = parser.parse_args()
    if args.budget_us < 1:
        parser.error("--budget-us must be positive")
    try:
        if args.compare is None:
            report = summarize(args.capture, args.budget_us, args.require_qnx)
        else:
            report = compare(args.capture, args.compare, args.budget_us, args.require_qnx)
    except (ValueError, OSError) as error:
        print(f"Capture rejected: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return int(report["result"] in {"miss", "inconclusive"})


if __name__ == "__main__":
    sys.exit(main())
