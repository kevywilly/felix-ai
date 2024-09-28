import asyncio
from abc import ABC, abstractmethod
import atexit
from lib.log import logger

class BaseNode(ABC):

    logger = logger

    def __init__(self, **kwargs):
        self.frequency = kwargs.get('frequency', 10)
        atexit.register(self._shutdown)

    def loaded(self):
        self.logger.info(f"*\t{self.__class__.__name__} Node is Initialized")

    def spinner(self):
        """Abstract method to be implemented by subclasses."""
        pass

    def shutdown(self):
        """Abstract method to be implemented by subclasses for shutdown procedures."""
        pass

    async def spin(self, frequency: float = None):
        """
        Starts the spinner task.

        :param frequency: Frequency at which to run the spinner in Hz.
        """
        if frequency is not None:
            self.frequency = frequency
        self._running = True

        self.logger.info(f"*\t{self.__class__.__name__} is spinning at {self.frequency} Hz")

        while self._running:
            self.spinner()
            await asyncio.sleep(1/self.frequency)

    def spin_once(self):
        """
        Runs the spinner once.

        This method should be called within an event loop.
        """
        self.spinner()

    def _shutdown(self):
        """
        Shuts down the node and cancels the spinner task.
        """
        self._running = False

        logger.info(f'{self.__class__.__name__} shutting down')

        self.shutdown()
        

    def stop(self):
        """
        Synchronous method to stop the node.

        This schedules the shutdown coroutine on the event loop.
        """
        asyncio.create_task(self._shutdown())