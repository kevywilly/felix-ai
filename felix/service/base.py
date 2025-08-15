from abc import abstractmethod
import asyncio
import time
from felix.bus import SimpleEventBus
from typing import Any
import logging 
import atexit
import numpy as np

class BaseService:
    """Base class for services using the event bus"""
    
    def __init__(self):
        self.event_bus = SimpleEventBus()
        self.service_name = self.__class__.__name__
        self.logger = logging.getLogger(self.service_name)
        self.service_id = f"{self.service_name}_{int(time.time() * 1000)}"

        self.running = False
        self.frequency_hz = 10  # Default to 10 Hz if not specified
        
        self.logger.info(f"🚀 Service '{self.service_name}' created with ID: {self.service_id}")

        atexit.register(self.stop)
    
    def start(self):
        """Start the service"""
        self.running = True
        self.setup_subscriptions()
        self.logger.info(f"✅ Service '{self.service_name}' started")
    
    def on_stop(self):
        pass

    def stop(self):
        """Stop the service"""
        self.running = False
        self.on_stop()
        self.logger.info(f"🛑 Service '{self.service_name}' stopped")
    
    def setup_subscriptions(self):
        """Override this method to subscribe to topics"""
        pass
    
    def publish_message(self, topic: str, message: Any):
        """Publish a message to the event bus"""
        return self.event_bus.publish(topic, message, self.service_id)

    def publish_ndarray(self, topic: str, array: np.ndarray):
        """Publish a numpy array efficiently via the event bus."""
        return self.event_bus.publish_ndarray(topic, array, self.service_id)
    
    def subscribe_to_topic(self, topic: str, callback_method):
        """Subscribe to a topic"""
        self.event_bus.subscribe(topic, callback_method)

    def subscribe_to_image(self, topic: str, callback_method):
        """Subscribe to an image/ndarray topic with auto-conversion to numpy arrays."""
        self.event_bus.subscribe_ndarray(topic, callback_method)

    def loaded(self):
        self.logger.info(f"{self.service_name} is loaded and ready...")

    @abstractmethod
    async def spinner(self):
        """Main loop to be overridden by subclasses"""
        pass
    
    async def spin(self, frequency_hz: int = 10):
        """Main loop to be overridden by subclasses"""
        self.logger.debug(f"{self.service_name} spinning...")
        while self.running:
            await self.spinner()
            await asyncio.sleep(1.0 / frequency_hz)
