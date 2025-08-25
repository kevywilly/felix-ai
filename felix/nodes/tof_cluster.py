
import time
from felix.signals import Topics
from felix.vision.tof import TOFArray
from lib.interfaces import Measurement
from lib.nodes.base import BaseNode

class TOFCluster(BaseNode):
    def __init__(self, **kwargs):

        super(TOFCluster, self).__init__(**kwargs)

        self.logger.info("Initializing TOF sensors")
        self.tof = TOFArray()
        self.tof.start_continuous()
        self.logger.info("TOF sensors initialized")

    def detect_range(self):
        for index, reading in enumerate(self.tof.get_readings()):
            m = Measurement(index, reading)
            Topics.tof.send("tof", payload=m)
            self.logger.debug(m)
            return m
           

    def spinner(self):
        self.detect_range()
            

        
if __name__ == "__main__":
    cluster = TOFCluster()
    while True:
        for range in cluster.detect_range():
            print(range)
            time.sleep(0.2)