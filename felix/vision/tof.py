
import time
import board
from digitalio import DigitalInOut
from adafruit_vl53l0x import VL53L0X
import atexit
import logging

class TOFArray:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.xshut = [
            DigitalInOut(board.D12),  # GP113_PWM7 (32)
            DigitalInOut(board.D13),  # GP115 (33)
        ]
        self.i2c = board.I2C()
        self.logger.info(f"TOF sensors found {self.i2c.scan()}")
        atexit.register(self.shutdown)
        self.logger.info("Initializing TOF sensors")
        self.sensors = self.init_sensors()

    def get_readings(self) -> list[int]:
        readings = []
        for index, sensor in enumerate(self.sensors):
            readings.insert(index, sensor.range)
        return readings
    
    def start_continuous(self):
        for sensor in self.sensors:
            sensor.start_continuous()

    def init_sensors(self) -> list[VL53L0X]:

        time.sleep(0.05)

        sensors = []

        for power_pin in self.xshut:
            power_pin.switch_to_output(value=False)
            power_pin.value = False
            time.sleep(0.02)

        for i, power_pin in enumerate(self.xshut):
            power_pin.value = True
            time.sleep(0.02)
            sensor = VL53L0X(self.i2c, io_timeout_s = 1)
            time.sleep(0.02)
            sensor.set_address(i + 0x30)
            time.sleep(0.02)

            # sensor.measurement_timing_budget = 2000000
            # sensor.measurement_timing_budget = 100000
            
            sensors.insert(i, sensor)

        return sensors

    def shutdown(self):
        try:
            for sensor in self.sensors:
                sensor.stop_continuous()
        except Exception as e:
            self.logger.error(f"Error stopping sensors: {e}")
        finally:
            self.i2c.deinit()
        print("I2C deinitialized and sensors stopped.")

if __name__ == "__main__":
    array = TOFArray()
    while True:
        print(array.get_readings())
