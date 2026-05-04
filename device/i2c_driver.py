"""
I2C Driver Layer
Wraps I2CSensorSim with retry logic, timeout handling, and error recovery.
This is the layer that real firmware would have between application code
and the hardware abstraction layer (HAL).
"""
import time
import logging
from device.i2c_sensor_sim import I2CSensorSim


class I2CDriver:
    """
    Driver-level abstraction over I2C sensor.
    Handles transient I2C NACK errors with retry + exponential backoff.
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_MS = 1  # base backoff in milliseconds

    def __init__(self, sensor: I2CSensorSim,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 backoff_ms: int = DEFAULT_BACKOFF_MS):
        self.sensor = sensor
        self.max_retries = max_retries
        self.backoff_ms = backoff_ms

        # Statistics for autotest reporting
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_retries": 0,
        }
        logging.info(
            f"Driver init: max_retries={max_retries}, "
            f"backoff_ms={backoff_ms}"
        )

    def _read_with_retry(self, reg_addr: int) -> int:
        """Read a register with automatic retry on NACK."""
        self.stats["total_calls"] += 1
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                value = self.sensor.read_register(reg_addr)
                self.stats["successful_calls"] += 1
                if attempt > 0:
                    logging.info(
                        f"Recovered after {attempt} retries on reg "
                        f"0x{reg_addr:02X}"
                    )
                return value
            except IOError as e:
                last_error = e
                self.stats["total_retries"] += 1
                # Exponential backoff: 1ms, 2ms, 4ms, ...
                wait_ms = self.backoff_ms * (2 ** attempt)
                logging.warning(
                    f"Attempt {attempt + 1} failed on reg "
                    f"0x{reg_addr:02X}, retrying in {wait_ms}ms"
                )
                time.sleep(wait_ms / 1000.0)

        # All retries exhausted
        self.stats["failed_calls"] += 1
        logging.error(
            f"Read FAILED after {self.max_retries + 1} attempts "
            f"on reg 0x{reg_addr:02X}"
        )
        raise IOError(
            f"I2C read failed after {self.max_retries + 1} attempts: "
            f"{last_error}"
        )

    def read_temperature(self) -> float:
        """Read temperature in Celsius with retry logic."""
        raw = self._read_with_retry(0x00)
        if raw & 0x8000:
            raw -= 0x10000
        return raw * 0.0625

    def read_device_id(self) -> int:
        """Read device ID register with retry logic."""
        return self._read_with_retry(0xFF)

    def get_success_rate(self) -> float:
        """Return success rate as a percentage (0.0 - 100.0)."""
        if self.stats["total_calls"] == 0:
            return 0.0
        return (
            self.stats["successful_calls"]
            / self.stats["total_calls"]
            * 100.0
        )

    def reset_stats(self):
        """Reset all statistics counters."""
        for key in self.stats:
            self.stats[key] = 0
        logging.info("Driver stats reset")