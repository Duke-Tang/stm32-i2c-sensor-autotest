"""
I2C Temperature Sensor Simulator
Simulates a TMP102-like I2C sensor (addr 0x48).
Mimics register-level behavior of an STM32 I2C slave device.

Registers:
  0x00: Temperature (16-bit, signed, 0.0625 degC per LSB)
  0x01: Config
  0xFF: Device ID (always 0xA1)
"""
import random
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)


class I2CSensorSim:
    DEVICE_ID = 0xA1
    I2C_ADDR = 0x48

    def __init__(self, fault_rate=0.0):
        self.registers = {0x00: 0, 0x01: 0x60, 0xFF: self.DEVICE_ID}
        self.fault_rate = fault_rate
        self.tx_count = 0
        logging.info(f"Sensor init at addr 0x{self.I2C_ADDR:02X}")

    def read_register(self, reg_addr):
        self.tx_count += 1

        if random.random() < self.fault_rate:
            logging.warning(f"NACK on read reg 0x{reg_addr:02X} (injected fault)")
            raise IOError("I2C NACK")

        if reg_addr == 0x00:
            temp_raw = int((25.0 + random.uniform(-0.5, 0.5)) / 0.0625)
            self.registers[0x00] = temp_raw & 0xFFFF

        if reg_addr not in self.registers:
            logging.error(f"Read from invalid reg 0x{reg_addr:02X}")
            raise ValueError(f"Invalid register: 0x{reg_addr:02X}")

        value = self.registers[reg_addr]
        logging.info(f"READ  reg 0x{reg_addr:02X} -> 0x{value:04X}")
        return value

    def write_register(self, reg_addr, value):
        self.tx_count += 1
        if reg_addr == 0xFF:
            raise PermissionError("Device ID register is read-only")
        self.registers[reg_addr] = value
        logging.info(f"WRITE reg 0x{reg_addr:02X} <- 0x{value:04X}")

    def read_temperature_celsius(self):
        raw = self.read_register(0x00)
        if raw & 0x8000:
            raw -= 0x10000
        return raw * 0.0625