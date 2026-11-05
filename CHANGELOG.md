# Changelog

All notable changes to Network Speed Lite are documented here.

## [Unreleased]

- Added a `test_traffic.py` unit test suite exercising `counters()`/`rates()`
  against a fake `/sys/class/net` tree built in a temp directory, covering
  normal operation, an interface disappearing mid-read, and counters that
  reset or wrap.
- Added a `--once` CLI flag to `traffic.py` for scripting/testing: takes a
  single measurement and exits instead of looping forever. Added `--interval`
  to control the sample period (default 2.0s, matching prior hardcoded
  behavior).
- Confirmed no stray `.bak` files are present in the repo.

## [1.1.0] - 2026-11-02

- Left-click opens a details popup: current, peak and session-total
  download/upload, plus a per-interface breakdown.
- Right-click switches between the normal view and a compact view (`↓ ↑`
  arrows that light up while traffic flows).
- Added preview screenshot.

## [1.0.0] - 2026-11-02

- Initial release: zero-config bar widget showing live download/upload
  rates, summing active physical interfaces only (excludes loopback, VPN
  tunnels, bridges, Docker interfaces) so traffic is never double-counted.
- Switches between KiB/s and MiB/s automatically.
- Starts a fresh baseline instead of showing a spike when an interface
  reconnects or its counters reset.
- Shows `offline` when no physical interface is up.
