"""Read physical-interface byte counters; never include VPN/bridge duplicates."""

import json
import time
from pathlib import Path


def counters():
    result = {}
    for interface in Path("/sys/class/net").iterdir():
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


def main():
    previous = counters()
    before = time.monotonic()
    totals = [0.0, 0.0]
    peaks = [0.0, 0.0]
    while True:
        time.sleep(2)
        current = counters()
        now = time.monotonic()
        elapsed = max(now - before, 0.001)
        per = rates(previous, current, elapsed)
        download = sum(v[0] for v in per.values())
        upload = sum(v[1] for v in per.values())
        totals[0] += download * elapsed
        totals[1] += upload * elapsed
        peaks[0] = max(peaks[0], download)
        peaks[1] = max(peaks[1], upload)
        print(json.dumps({
            "download": download, "upload": upload,
            "interfaces": sorted(current),
            "perInterface": [{"name": n, "download": per[n][0], "upload": per[n][1]}
                             for n in sorted(per)],
            "totalDown": totals[0], "totalUp": totals[1],
            "peakDown": peaks[0], "peakUp": peaks[1],
        }), flush=True)
        previous, before = current, now


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
