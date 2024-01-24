from abc import abstractmethod
from traitlets.config.configurable import SingletonConfigurable
import threading
import time
import atexit
import logging

class Node(SingletonConfigurable):
    logger = logging.getLogger(__name__)
    
    def __init__(self, name: str, *args, **kwargs):
        super(Node, self).__init__(*args, **kwargs)
        atexit.register(self._shutdown)
        self._name = name
        self._spin_frequency=10
        self._running = False
        self._thread = None
        
        self.logger.info(f"Loaded {self._name}...")


    @abstractmethod
    def spinner(self):
        pass

    
    def _spin(self):
        while self._running:
            self.spinner()
            time.sleep(1.0/self._spin_frequency)

    
    def spin(self, frequency: int = 10):
        self._spin_frequency = frequency
        self._running = True
        self._thread = threading.Thread(target=self._spin)
        self._thread.start()

    
    def spin_once(self):
        self.spinner()


    def _shutdown(self):
        
        self._running = False
        if self._thread:
            print(f'{self._name} shutting down')
            self._thread.join()
            
        
        

    
