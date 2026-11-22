# CereX QNX Timing Lab

A competition prototype for teams verifying timing-sensitive software. A small probe runs a periodic workload and records wake-up lateness. The host-side reporter identifies deadline-budget misses, locates a known injected delay, and generates a JSON result that can be compared across repeated runs.

## Validate the host path

Requires a C11 compiler, Make and Python 3. No package installation is needed.

```sh
make host
./timing-probe-host 20 10000 > host-baseline.jsonl
./timing-probe-host 20 10000 8 18000 > host-injected.jsonl
python3 report.py host-baseline.jsonl --compare host-injected.jsonl --budget-us 5000
```

The deliberate delay exceeds the 5 ms budget. The comparison reports `injection_detected` when the baseline stays within budget and the first miss matches the configured injection sample. It rejects captures with incompatible target metadata or timing settings. Each result includes the original capture SHA-256 digests and per-run statistics.

Comparison exit codes are `0` for a detected injection, `1` for an inconclusive experiment, and `2` for malformed or incompatible captures. Single-capture reporting is also available by omitting `--compare`. Its exit codes are `0` for a pass, `1` for a valid capture with a budget miss, and `2` for a malformed or unsupported capture. Use `--require-qnx` to require the QNX 8 target metadata and a progressing cycle counter for both captures.

## Collect an actual QNX 8 result

1. Use a licensed QNX SDP 8.0 installation and boot an x86-64 QNX 8 Quick Start Target Image in QEMU. Enable the host-side QNX environment using the script from that installation.
2. Run `make qnx`. If your licensed target is a different architecture, select the matching compiler variant with `QNX_VARIANT`.
3. Transfer the binary to the lab guest using its configured transport. On the guest, run the probe once without an injected delay and once with one.

```sh
./timing-probe-qnx 20 10000 > qnx-baseline.jsonl
./timing-probe-qnx 20 10000 8 18000 > qnx-injected.jsonl
```

Bring both files back to the host and compare them:

```sh
python3 report.py qnx-baseline.jsonl --compare qnx-injected.jsonl --budget-us 5000 --require-qnx
```

Keep the raw captures alongside the report. The QNX build records `ClockCycles()` and the cycle frequency from the QNX system page. The local host build omits that information. Input checks establish consistency. A recording of QNX startup, compilation and execution supplies live evidence. Report the measurements as results from the virtual guest when using QEMU.

## Current evidence

The POSIX host build and report path were validated. The QNX cross-compile and guest execution remain pending. A public submission will need the verified guest captures, source and build instructions, and a video of the workflow.

- [QNX Everywhere documentation](https://www.qnx.com/developers/docs/qnxeverywhere/index.html)
- [QNX ClockCycles reference](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/c/clockcycles.html)
