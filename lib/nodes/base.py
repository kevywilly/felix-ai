import asyncio
from abc import ABC, abstractmethod
import asyncio_atexit
from lib.log import logger

class BaseNode(ABC):

    logger = logger

    def __init__(self, **kwargs):
        self.frequency = kwargs.get('frequency', 10)
        
        self.logger.info("\n******************************************************************\n")
        self.logger.info(f"*\tStarting {self.__class__.__name__} Node @ {self.frequency}Hz\n")
        self.logger.info("******************************************************************\n")
        self._task = None

        asyncio_atexit.register(self._shutdown)

    def loaded(self):
        self.logger.info("\n******************************************************************\n")
        self.logger.info(f"*\t{self.__class__.__name__} Node is up\n")
        self.logger.info("******************************************************************\n")

    async def spinner(self):
        """Abstract method to be implemented by subclasses."""
        pass


    async def shutdown(self):
        """Abstract method to be implemented by subclasses for shutdown procedures."""
        pass

    async def _spin(self):
        """Private method that runs the spinner at the specified frequency."""
        try:
            while self._running:
                await self.spinner()
                await asyncio.sleep(1.0 / self.frequency)
        except asyncio.CancelledError:
            pass  # Handle any cleanup here if necessary

    async def spin(self, frequency: float = None):
        """
        Starts the spinner task.

        :param frequency: Frequency at which to run the spinner in Hz.
        """
        if frequency is not None:
            self.frequency = frequency
        self._running = True
        self._task = asyncio.create_task(self._spin())

    def spin_once(self):
        """
        Runs the spinner once.

        This method should be called within an event loop.
        """
        asyncio.run(self.spinner())

    async def _shutdown(self):
        """
        Shuts down the node and cancels the spinner task.
        """
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info(f'{self.__class__.__name__} shutting down')

        await self.shutdown()
        

    def stop(self):
        """
        Synchronous method to stop the node.

        This schedules the shutdown coroutine on the event loop.
        """
        asyncio.create_task(self._shutdown())