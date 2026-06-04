import atexit
import board
import busio
import time
from microcontroller import Pin
from adafruit_vl53l0x import VL53L0X
import digitalio

# Optional: Adjust the measurement timing budget
# This affects the balance between speed and accuracy.
# Default is 33ms. Higher values mean more accuracy, but slower readings.
# vl53.measurement_timing_budget = 20000  # Example: 20ms

class TOF:
    def __init__(self, sda = None, scl = None, xshuts: list[Pin] = None):
        self.sensors: list[VL53L0X] = []
        self.sda = sda or board.GP0
        self.scl = scl or board.GP1
        self.xshuts = [digitalio.DigitalInOut(pin) for pin in xshuts] if xshuts else []
        self.i2c = busio.I2C(board.GP1, board.GP0)

        atexit.register(self.deinit)

    def initialize_sensors(self):
        #self.i2c.scan()  # Ensure I2C is ready
        address = 0x29
        if not self.xshuts:
            self.sensors.append(VL53L0X(self.i2c))
        else:
            for pin in self.xshuts:
                pin.direction = digitalio.Direction.OUTPUT
                pin.value = False  # Disable all sensors

            time.sleep(0.1)  # Wait for sensors to shutdown

            for index, pin in enumerate(self.xshuts):
                pin.value = True  # Enable this sensor
                time.sleep(0.1)  # Wait for the sensor to boot up
                sensor = VL53L0X(self.i2c)
                if index < len(self.xshuts) - 1:
                    address += 1
                    sensor.set_address(address)  # Disable this sensor if not the last one
                self.sensors.append(sensor)
                print(f"Initialized sensor {index} on pin {pin}")

        for sensor in self.sensors:
            sensor.start_continuous()


    def run(self, frequency_hz = 10):
        while True:
            try:
                for index, sensor in enumerate(self.sensors):
                    print({"id": index, "type": "ir", "value": sensor.range})
                
            except Exception as e:
                print(f"Error reading sensor: {e}")
            except KeyboardInterrupt:
                print("Exiting...")
                break
            finally:
                time.sleep(1.0/frequency_hz)

    def deinit(self):
        for sensor in self.sensors:
            sensor.stop_continuous()
        self.i2c.deinit()   


if __name__ == "__main__":
    tof = TOF(xshuts=[board.GP2, board.GP3])
    tof.initialize_sensors()
    tof.run()