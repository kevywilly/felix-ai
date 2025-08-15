
import Jetson.GPIO as GPIO
import time
import board
import click
from digitalio import DigitalInOut
from adafruit_vl53l0x import VL53L0X
from felix.bus import SimpleEventBus
from felix.service.base import BaseService
from lib.interfaces import Measurement
from lib.nodes.base import BaseNode
from lib.log import logger
from felix.topics import Topics
from felix.types import Measurement
import logging
import asyncio

logger = logging.getLogger("TOFService")

i2c = board.I2C()

def _get_sensor_instance(index: int) -> VL53L0X:
    try:
        sensor = VL53L0X(i2c, io_timeout_s = 1)
            # also performs VL53L0X hardware check
    except RuntimeError:
        logger.error(f"failed to initialize tof {index} trying again in 2 seconds.")
        time.sleep(2)
        sensor = VL53L0X(i2c, io_timeout_s = 1)
    return sensor

def _init_sensors() -> list[VL53L0X]:

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

class TOFService(BaseService):
    def __init__(self):
        super().__init__()

        self.sensors = []
        logger.info("Initializing TOF sensors")
        self.sensors = _init_sensors()
        logger.info("TOF sensors initialized")

        for sensor in self.sensors:
            sensor.start_continuous()

    def detect_range(self):
        for index, sensor in enumerate(self.sensors):
            m = Measurement(index, sensor.range)
            success = self.publish_message(Topics.TOF, m.dict)
            logger.debug(m)
            yield m
           

    def spinner(self):
        self.detect_range()
 

    def shutdown(self):
        try:
            for sensor in self.sensors:
                sensor.stop_continuous()
        finally:
            i2c.deinit()
            
    async def spinner(self):
        for range in self.detect_range():
            self.logger.debug(range)


async def run(frequency: int = 10):
    logging.basicConfig()
    cluster = TOFService()
    cluster.start()

    await cluster.spin(frequency_hz=frequency)

@click.command()
@click.option('--frequency', default=10, help='Frequency in Hz')
@click.option('--log-level', default='INFO', help='Logging level')
def cli(frequency, log_level):
    logging.basicConfig(level=getattr(logging, log_level.upper()))
    asyncio.run(run(frequency))
        
if __name__ == "__main__":
    cli()

