"""
Simple ZeroMQ Event Bus Example with Two Generic Services
"""

import zmq
import json
import threading
import time
import logging
from typing import Callable, Any
import uuid
import logging
class SimpleEventBus:
    """Simplified ZMQ Event Bus for topic-based messaging"""
    
    def __init__(self, port=5555):
        self.context = zmq.Context()
        self.port = port
        self.logger = logging.getLogger("SimpleEventBus")
        
        # Publisher socket for sending messages
        self.publisher = self.context.socket(zmq.PUB)
        
        try:
            self.publisher.bind(f"tcp://*:{port}")
            self.is_main_publisher = True
            self.logger.info(f"📡 Bound as main publisher on port {port}")
        except zmq.ZMQError:
            # Port is taken, connect as secondary publisher
            self.publisher.close()
            self.publisher = self.context.socket(zmq.PUB)
            self.publisher.connect(f"tcp://localhost:{port}")
            self.is_main_publisher = False
            self.logger.info(f"🔗 Connected as secondary publisher to port {port}")
        
        # Subscriber socket for receiving messages - always connects
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.connect(f"tcp://localhost:{port}")
        
        # Topic callbacks
        self.topic_callbacks = {}
        self.running = False
        self.listener_thread = None
        
        # Give sockets time to connect/bind
        time.sleep(0.2)
        
        self.logger.info(f"✅ Event Bus initialized on port {port}")
    
    def publish(self, topic: str, message: Any, sender_id: str = "unknown"):
        """Publish a message to a topic"""
        payload = {
            'topic': topic,
            'message': message,
            'sender_id': sender_id,
            'timestamp': time.time(),
            'message_id': str(uuid.uuid4())
        }
        
        try:
            # Send topic as first frame, message as second frame
            self.publisher.send_multipart([
                topic.encode('utf-8'),
                json.dumps(payload).encode('utf-8')
            ])
            self.logger.debug(f"📤 Published to {topic} : {message}")
            return True
        except Exception as e:
            self.logger.info(f"❌ Error publishing to {topic}: {e}")
            return False
    
    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to a topic with a callback function"""
        if topic not in self.topic_callbacks:
            self.topic_callbacks[topic] = []
            # Subscribe to the topic in ZMQ
            self.subscriber.setsockopt(zmq.SUBSCRIBE, topic.encode('utf-8'))
            self.logger.info(f"🔔 Subscribed to topic: '{topic}'")
        
        self.topic_callbacks[topic].append(callback)
        
        # Start listener if not already running
        if not self.running:
            self.start_listening()
    
    def start_listening(self):
        """Start listening for messages in background thread"""
        if self.running:
            return
        
        self.running = True
        self.listener_thread = threading.Thread(target=self._message_listener, daemon=True)
        self.listener_thread.start()
        self.logger.info("🎧 Started listening for messages")
    
    def stop(self):
        """Stop the event bus"""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=1)
        
        self.publisher.close()
        self.subscriber.close()
        self.context.term()
        self.logger.info("🛑 Event bus stopped")
    
    def _message_listener(self):
        """Background thread that listens for incoming messages"""
        while self.running:
            try:
                # Non-blocking receive with timeout
                if self.subscriber.poll(100):  # 100ms timeout
                    message_parts = self.subscriber.recv_multipart(zmq.NOBLOCK)
                    
                    # Handle different message formats
                    if len(message_parts) >= 2:
                        topic = message_parts[0].decode('utf-8')
                        message_data = message_parts[1]
                        
                        try:
                            message_str = message_data.decode('utf-8')
                            
                            # Skip empty messages
                            if not message_str.strip():
                                continue
                                
                            payload = json.loads(message_str)
                            
                            # Call all callbacks registered for this topic
                            if topic in self.topic_callbacks:
                                for callback in self.topic_callbacks[topic]:
                                    try:
                                        callback(payload)
                                    except Exception as e:
                                        self.logger.info(f"❌ Error in callback for topic '{topic}': {e}")
                        
                        except json.JSONDecodeError as e:
                            # Skip non-JSON messages (ZMQ control messages)
                            continue
                        except UnicodeDecodeError:
                            # Skip binary/control messages from ZMQ
                            continue
                    else:
                        # Skip malformed messages
                        continue
            
            except zmq.Again:
                # No message available, continue
                continue
            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    self.logger.info(f"❌ Error in message listener: {e}")
