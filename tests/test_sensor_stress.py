"""
Stress tests with fault injection.

Verifies the driver's retry logic actually recovers from transient I2C NACKs.
Uses fixed random seed for reproducibility — same input -> same result.
"""
import random
import pytest
from device.i2c_sensor_sim import I2CSensorSim
from device.i2c_driver import I2CDriver


# ---------- Fixtures ----------

@pytest.fixture
def stable_driver():
    """Driver over a fault-free sensor."""
    sensor = I2CSensorSim(fault_rate=0.0)
    return I2CDriver(sensor)


@pytest.fixture
def flaky_driver():
    """Driver over a sensor with 30% NACK rate (seeded for reproducibility)."""
    random.seed(42)
    sensor = I2CSensorSim(fault_rate=0.30)
    return I2CDriver(sensor, max_retries=3)


@pytest.fixture
def broken_driver():
    """Driver over a sensor that always fails."""
    sensor = I2CSensorSim(fault_rate=1.0)
    return I2CDriver(sensor, max_retries=3)


# ---------- Tests ----------

def test_stable_sensor_no_retries(stable_driver):
    """Zero faults -> zero retries."""
    for _ in range(100):
        stable_driver.read_temperature()
    assert stable_driver.stats["total_retries"] == 0
    assert stable_driver.get_success_rate() == 100.0


def test_flaky_sensor_recovers_via_retry(flaky_driver):
    """30% fault rate, 3 retries -> driver should still recover most calls."""
    successes = 0
    failures = 0
    for _ in range(100):
        try:
            flaky_driver.read_temperature()
            successes += 1
        except IOError:
            failures += 1

    # With 30% per-attempt NACK and 4 attempts total (1 + 3 retries),
    # final failure prob ~= 0.30^4 = 0.0081 -> expect >95% success
    assert successes >= 95, (
        f"Recovery too weak: {successes}/100 succeeded. Stats: {flaky_driver.stats}"
    )
    assert flaky_driver.stats["total_retries"] > 0, "Expected some retries to occur"


def test_broken_sensor_eventually_gives_up(broken_driver):
    """100% fault rate -> driver must raise IOError after retries exhausted."""
    with pytest.raises(IOError):
        broken_driver.read_temperature()

    # 1 initial attempt + 3 retries = 4 total retries counted
    assert broken_driver.stats["failed_calls"] == 1
    assert broken_driver.stats["total_retries"] == 4


def test_retry_count_matches_attempts(broken_driver):
    """Each failed call should consume exactly (max_retries + 1) attempts."""
    for _ in range(5):
        with pytest.raises(IOError):
            broken_driver.read_temperature()

    expected_retries = 5 * (broken_driver.max_retries + 1)
    assert broken_driver.stats["total_retries"] == expected_retries


def test_stats_reset_clears_counters(flaky_driver):
    """reset_stats() must zero all counters."""
    try:
        flaky_driver.read_temperature()
    except IOError:
        pass

    flaky_driver.reset_stats()
    assert all(v == 0 for v in flaky_driver.stats.values())