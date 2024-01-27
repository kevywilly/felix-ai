from abc import abstractmethod
import traitlets
from traitlets.config.configurable import Configurable
import threading
import time
import atexit
import logging

class Node(Configurable):

    logger = logging.getLogger(__name__)
    frequency = traitlets.Float(default_value=10).tag(config=True)

    def __init__(self, **kwargs):
        super(Node, self).__init__(**kwargs)
        self.logger.info(f"Starting {self.__class__.__name__} Node")
        atexit.register(self._shutdown)
        
        self._running = False
        self._thread = None
        
        self.logger.info(f"Loaded {self.__class__.__name__}")


    @abstractmethod
    def spinner(self):
        pass

    
    def _spin(self):
        while self._running:
            self.spinner()
            time.sleep(1.0/self.frequency)

    
    def spin(self, frequency: int = 10):
        self.frequency = frequency
        self._running = True
        self._thread = threading.Thread(target=self._spin)
        self._thread.start()

    
    def spin_once(self):
        self.spinner()


    def _shutdown(self):
        
        self._running = False
        if self._thread:
            print(f'{self.__class__.__name__} shutting down')
            try:
                self._thread.join()
            except:
                pass
            
        
        

    
