"""
Basic functional tests for I2CSensorSim.
Verifies the sensor responds correctly to standard register reads/writes.
"""
import pytest
from device.i2c_sensor_sim import I2CSensorSim


@pytest.fixture
def sensor():
    """Provides a fresh sensor instance for each test."""
    return I2CSensorSim()


def test_device_id_is_correct(sensor):
    """Device ID register (0xFF) must always return 0xA1."""
    device_id = sensor.read_register(0xFF)
    assert device_id == 0xA1, f"Expected 0xA1, got 0x{device_id:02X}"


def test_temperature_within_room_range(sensor):
    """Room temperature simulation should be 24.5-25.5 C."""
    temp = sensor.read_temperature_celsius()
    assert 24.0 <= temp <= 26.0, f"Temperature out of range: {temp} C"


def test_invalid_register_raises_error(sensor):
    """Reading a non-existent register must raise ValueError."""
    with pytest.raises(ValueError):
        sensor.read_register(0x99)


def test_device_id_is_read_only(sensor):
    """Writing to register 0xFF must raise PermissionError."""
    with pytest.raises(PermissionError):
        sensor.write_register(0xFF, 0x00)


def test_tx_count_increments(sensor):
    """Every read/write must increment tx_count."""
    assert sensor.tx_count == 0
    sensor.read_register(0xFF)
    sensor.read_register(0xFF)
    sensor.write_register(0x01, 0x60)
    assert sensor.tx_count == 3