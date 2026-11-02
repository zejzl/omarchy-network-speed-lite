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
    total = [0.0, 0.0]
    for name, values in current.items():
        old = previous.get(name)
        if old is None or any(now < before for now, before in zip(values, old)):
            continue
        for index in (0, 1):
            total[index] += (values[index] - old[index]) / elapsed
    return total


def main():
    previous = counters()
    before = time.monotonic()
    while True:
        time.sleep(2)
        current = counters()
        now = time.monotonic()
        download, upload = rates(previous, current, max(now - before, 0.001))
        print(json.dumps({"download": download, "upload": upload,
                          "interfaces": sorted(current)}), flush=True)
        previous, before = current, now


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
