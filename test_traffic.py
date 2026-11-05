"""Unit tests for traffic.py's sysfs-reading logic against a fake sysfs tree.

These tests never touch the real /sys/class/net; they build a temp directory
structure that mimics it, so results are deterministic and don't depend on
the machine's actual network interfaces.
"""

from pathlib import Path

import pytest

from traffic import counters, rates


def make_iface(base, name, rx_bytes=None, tx_bytes=None, operstate="up", has_device=True):
    """Create a fake /sys/class/net/<name>/ entry under `base`."""
    iface_dir = base / name
    iface_dir.mkdir(parents=True, exist_ok=True)
    if has_device:
        (iface_dir / "device").mkdir(exist_ok=True)
    if operstate is not None:
        (iface_dir / "operstate").write_text(operstate)
    if rx_bytes is not None or tx_bytes is not None:
        stats_dir = iface_dir / "statistics"
        stats_dir.mkdir(exist_ok=True)
        if rx_bytes is not None:
            (stats_dir / "rx_bytes").write_text(str(rx_bytes))
        if tx_bytes is not None:
            (stats_dir / "tx_bytes").write_text(str(tx_bytes))
    return iface_dir


@pytest.fixture
def fake_sys(tmp_path):
    base = tmp_path / "sys_class_net"
    base.mkdir()
    return base


class TestCountersNormalOperation:
    def test_reads_rx_tx_for_up_physical_interface(self, fake_sys):
        make_iface(fake_sys, "eth0", rx_bytes=1000, tx_bytes=500)

        result = counters(fake_sys)

        assert result == {"eth0": (1000, 500)}

    def test_multiple_interfaces(self, fake_sys):
        make_iface(fake_sys, "eth0", rx_bytes=1000, tx_bytes=500)
        make_iface(fake_sys, "wlan0", rx_bytes=2000, tx_bytes=1500)

        result = counters(fake_sys)

        assert result == {"eth0": (1000, 500), "wlan0": (2000, 1500)}

    def test_skips_interface_without_device(self, fake_sys):
        # e.g. loopback, bridges: no backing hardware device
        make_iface(fake_sys, "lo", rx_bytes=100, tx_bytes=100, has_device=False)
        make_iface(fake_sys, "eth0", rx_bytes=1000, tx_bytes=500)

        result = counters(fake_sys)

        assert result == {"eth0": (1000, 500)}

    def test_skips_interface_that_is_down(self, fake_sys):
        make_iface(fake_sys, "eth1", rx_bytes=100, tx_bytes=100, operstate="down")
        make_iface(fake_sys, "eth0", rx_bytes=1000, tx_bytes=500)

        result = counters(fake_sys)

        assert result == {"eth0": (1000, 500)}

    def test_empty_tree_returns_empty_dict(self, fake_sys):
        assert counters(fake_sys) == {}


class TestCountersInterfaceDisappearsMidRead:
    def test_missing_operstate_file_is_skipped(self, fake_sys):
        # device exists but operstate file vanished (e.g. unplugged mid-scan)
        iface_dir = fake_sys / "eth0"
        iface_dir.mkdir()
        (iface_dir / "device").mkdir()
        # no operstate file written at all

        result = counters(fake_sys)

        assert result == {}

    def test_missing_statistics_dir_after_operstate_check(self, fake_sys):
        # Interface reports "up" but its statistics directory is gone by the
        # time we try to read rx_bytes/tx_bytes (device removed mid-read).
        iface_dir = fake_sys / "eth0"
        iface_dir.mkdir()
        (iface_dir / "device").mkdir()
        (iface_dir / "operstate").write_text("up")
        # statistics/ deliberately not created

        result = counters(fake_sys)

        assert result == {}

    def test_one_interface_disappears_others_still_counted(self, fake_sys):
        make_iface(fake_sys, "eth0", rx_bytes=1000, tx_bytes=500)
        # eth1 claims to be up but has no statistics (vanished mid-read)
        broken = fake_sys / "eth1"
        broken.mkdir()
        (broken / "device").mkdir()
        (broken / "operstate").write_text("up")

        result = counters(fake_sys)

        assert result == {"eth0": (1000, 500)}

    def test_non_numeric_counter_value_is_skipped(self, fake_sys):
        # Simulates a half-written/garbled read during interface removal.
        iface_dir = make_iface(fake_sys, "eth0", operstate="up")
        stats_dir = iface_dir / "statistics"
        stats_dir.mkdir()
        (stats_dir / "rx_bytes").write_text("")
        (stats_dir / "tx_bytes").write_text("500")

        result = counters(fake_sys)

        assert result == {}


class TestRatesNormalOperation:
    def test_computes_rate_from_delta_over_elapsed(self):
        previous = {"eth0": (1000, 500)}
        current = {"eth0": (3000, 1500)}

        result = rates(previous, current, elapsed=2.0)

        assert result == {"eth0": (1000.0, 500.0)}

    def test_new_interface_has_no_baseline_reports_zero(self):
        previous = {}
        current = {"eth0": (1000, 500)}

        result = rates(previous, current, elapsed=2.0)

        assert result == {"eth0": (0.0, 0.0)}

    def test_multiple_interfaces_independent_rates(self):
        previous = {"eth0": (1000, 500), "wlan0": (5000, 5000)}
        current = {"eth0": (2000, 600), "wlan0": (5200, 5100)}

        result = rates(previous, current, elapsed=1.0)

        assert result == {"eth0": (1000.0, 100.0), "wlan0": (200.0, 100.0)}


class TestRatesCounterWrapOrReset:
    def test_counter_reset_to_zero_reports_zero_not_negative(self):
        # Interface reconnected/driver reset: counters restart from 0.
        previous = {"eth0": (100_000, 50_000)}
        current = {"eth0": (10, 5)}

        result = rates(previous, current, elapsed=2.0)

        assert result == {"eth0": (0.0, 0.0)}

    def test_counter_wraps_past_max_value_reports_zero(self):
        # e.g. a 32-bit counter wrapping around; current < previous looks
        # identical to a reset from this module's point of view, and must
        # not produce a huge negative-turned-positive spike.
        max_u32 = 2**32 - 1
        previous = {"eth0": (max_u32 - 10, max_u32 - 5)}
        current = {"eth0": (5, 2)}

        result = rates(previous, current, elapsed=1.0)

        assert result == {"eth0": (0.0, 0.0)}

    def test_only_one_direction_resets_still_reports_zero_for_both(self):
        # rx went backwards but tx kept climbing normally; treat as a full
        # reset for this interface rather than mixing a real and fake rate.
        previous = {"eth0": (5000, 1000)}
        current = {"eth0": (10, 1500)}

        result = rates(previous, current, elapsed=1.0)

        assert result == {"eth0": (0.0, 0.0)}

    def test_reset_interface_alongside_normal_interface(self):
        previous = {"eth0": (5000, 1000), "wlan0": (1000, 1000)}
        current = {"eth0": (10, 10), "wlan0": (3000, 2000)}

        result = rates(previous, current, elapsed=1.0)

        assert result == {"eth0": (0.0, 0.0), "wlan0": (2000.0, 1000.0)}
