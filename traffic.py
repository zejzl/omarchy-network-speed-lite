"""Read physical-interface byte counters; never include VPN/bridge duplicates."""

import argparse
import json
import time
from pathlib import Path


def counters(base=Path("/sys/class/net")):
    result = {}
    for interface in base.iterdir():
        try:
            if not (interface / "device").exists():
                continue
            if (interface / "operstate").read_text().strip() != "up":
                continue
            result[interface.name] = tuple(
                int((interface / "statistics" / name).read_text())
                for name in ("rx_bytes", "tx_bytes")
            )
        except (OSError, ValueError):
            continue
    return result


def rates(previous, current, elapsed):
    # A newly connected/reset interface needs another sample, not a spike.
    per = {}
    for name, values in current.items():
        old = previous.get(name)
        if old is None or any(now < before for now, before in zip(values, old)):
            per[name] = (0.0, 0.0)
            continue
        per[name] = tuple((values[i] - old[i]) / elapsed for i in (0, 1))
    return per


def sample(previous, before, base=Path("/sys/class/net")):
    """Take one measurement relative to `previous`/`before`; returns (line_dict, current, now)."""
    current = counters(base)
    now = time.monotonic()
    elapsed = max(now - before, 0.001)
    per = rates(previous, current, elapsed)
    download = sum(v[0] for v in per.values())
    upload = sum(v[1] for v in per.values())
    return {
        "download": download,
        "upload": upload,
        "interfaces": sorted(current),
        "perInterface": [
            {"name": n, "download": per[n][0], "upload": per[n][1]} for n in sorted(per)
        ],
    }, current, now, elapsed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="take a single measurement and exit, instead of looping forever",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="seconds between measurements (default: 2.0)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    previous = counters()
    before = time.monotonic()
    totals = [0.0, 0.0]
    peaks = [0.0, 0.0]

    if args.once:
        # A single sample has no prior baseline to diff against, so the first
        # measurement is always a zeroed reading by design (see `rates`).
        # Sleep briefly so a meaningful delta can still be reported on --once.
        time.sleep(args.interval)
        line, current, now, elapsed = sample(previous, before)
        totals[0] += line["download"] * elapsed
        totals[1] += line["upload"] * elapsed
        peaks[0] = max(peaks[0], line["download"])
        peaks[1] = max(peaks[1], line["upload"])
        line.update({
            "totalDown": totals[0], "totalUp": totals[1],
            "peakDown": peaks[0], "peakUp": peaks[1],
        })
        print(json.dumps(line), flush=True)
        return

    while True:
        time.sleep(args.interval)
        line, current, now, elapsed = sample(previous, before)
        totals[0] += line["download"] * elapsed
        totals[1] += line["upload"] * elapsed
        peaks[0] = max(peaks[0], line["download"])
        peaks[1] = max(peaks[1], line["upload"])
        line.update({
            "totalDown": totals[0], "totalUp": totals[1],
            "peakDown": peaks[0], "peakUp": peaks[1],
        })
        print(json.dumps(line), flush=True)
        previous, before = current, now


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
