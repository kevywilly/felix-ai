
import Jetson.GPIO as GPIO
import time
import board
from digitalio import DigitalInOut
from adafruit_vl53l0x import VL53L0X
from lib.interfaces import Measurement
from lib.nodes.base import BaseNode
from felix.signals import sig_tof

i2c = board.I2C()

def fancy_print(title: str, items: list[str] = []):
    print("------------------------------------")
    print(title)
    print("------------------------------------")

    for item in items:
        print(f"\t- {item}")

def _get_sensor_instance(index: int) -> VL53L0X:
    try:
        sensor = VL53L0X(i2c, io_timeout_s = 0.5)
            # also performs VL53L0X hardware check
    except RuntimeError:
        print(f"failed to initialize tof {index} trying again in 1 second.")
        time.sleep(1)
        sensor = VL53L0X(i2c, io_timeout_s = 0.5)
    return sensor

def init_sensors() -> list[VL53L0X]:

    time.sleep(0.05)

    xshut = [
        DigitalInOut(board.D12),
        DigitalInOut(board.D13),
    ]

    for power_pin in xshut:
        # make sure these pins are a digital output, not a digital input
        power_pin.switch_to_output(value=False)
        power_pin.value = False
        # These pins are active when Low, meaning:
        #   if the output signal is LOW, then the VL53L0X sensor is off.
        #   if the output signal is HIGH, then the VL53L0X sensor is on.
    # all VL53L0X sensors are now off

    # initialize a list to be used for the array of VL53L0X sensors
    vl53 = []

    # now change the addresses of the VL53L0X sensors
    for i, power_pin in enumerate(xshut):
        # turn on the VL53L0X to allow hardware check
        power_pin.value = True
        time.sleep(0.02)
        # instantiate the VL53L0X sensor on the I2C bus & insert it into the "vl53" list

        vl53.insert(i, _get_sensor_instance(i))

        # vl53[i].measurement_timing_budget = 2000000

        # vl53[i].measurement_timing_budget = 100000

        # no need to change the address of the last VL53L0X sensor
        if i < len(xshut) - 1:
            # default address is 0x29. Change that to something else
            vl53[i].set_address(i + 0x30)  # address assigned should NOT be already in use

        # start continous mode

    return vl53

class TOFCluster(BaseNode):
    def __init__(self, **kwargs):

        super(TOFCluster, self).__init__(**kwargs)

        self.sensors = []
        fancy_print("Initializing TOF sensors")
        self.sensors = init_sensors()
        fancy_print("TOF sensors initialized")

        for sensor in self.sensors:
            sensor.start_continuous()

    def detect_range(self):
        for index, sensor in enumerate(self.sensors):
            m = Measurement(index, sensor.range)
            sig_tof.send("tof", payload=m)
            if self.debug:
                print(m)
           

    def spinner(self):
        self.detect_range()
 

    def shutdown(self):
        try:
            for sensor in self.sensors:
                sensor.stop_continuous()
        finally:
            i2c.deinit()
            GPIO.cleanup()

        
if __name__ == "__main__":
    cluster = TOFCluster()
    while True:
        for range in cluster.detect_range():
            print(range)
            time.sleep(0.2)

    
else:
    print(
        "Multiple VL53L0X sensors' addresses are assigned properly\n"
        "execute detect_range() to read each sensors range readings.\n"
        "When you are done with readings, execute stop_continuous()\n"
        "to stop the continuous mode."
    )
