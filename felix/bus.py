import zmq
import json
import numpy as np
import threading
import time
import logging
import uuid
from typing import Callable, Any

class SimpleEventBus:
    """
    ZeroMQ Event Bus with an embedded XPUB/XSUB proxy.
    - First process to start will bind XPUB/XSUB and run the proxy thread.
    - All processes publish to XSUB (fan-in) and subscribe from XPUB (fan-out).
    """
    def __init__(self, xpub_port: int = 5555, xsub_port: int = 5556):
        self.ctx = zmq.Context.instance()
        self.xpub_port = xpub_port
        self.xsub_port = xsub_port
        self.logger = logging.getLogger("SimpleEventBus")

        # Try to become the broker (bind XPUB/XSUB and start proxy)
        self._maybe_start_proxy()

        # Publisher: connect to XSUB (fan-in)
        self.publisher = self.ctx.socket(zmq.PUB)
        self.publisher.connect(f"tcp://127.0.0.1:{self.xsub_port}")

        # Subscriber: connect to XPUB (fan-out)
        self.subscriber = self.ctx.socket(zmq.SUB)
        self.subscriber.connect(f"tcp://127.0.0.1:{self.xpub_port}")

        self.topic_callbacks: dict[str, list[Callable]] = {}
        self.running = False
        self.listener_thread: threading.Thread | None = None

        # Allow sockets to connect
        time.sleep(0.2)
        self.logger.info(f"✅ Event Bus ready (XPUB:{self.xpub_port}, XSUB:{self.xsub_port})")

    def _maybe_start_proxy(self):
        # Bind XPUB/XSUB if available; otherwise assume proxy already running
        try:
            xsub = self.ctx.socket(zmq.XSUB)
            xsub.bind(f"tcp://*:{self.xsub_port}")

            xpub = self.ctx.socket(zmq.XPUB)
            # Enable verbose subscriptions if you want to log SUB/UNSUB
            # xpub.setsockopt(zmq.XPUB_VERBOSE, 1)
            xpub.bind(f"tcp://*:{self.xpub_port}")

            self.logger.info(f"🧩 Starting broker proxy (XSUB:{self.xsub_port} -> XPUB:{self.xpub_port})")

            def _proxy():
                try:
                    zmq.proxy(xsub, xpub)
                finally:
                    xsub.close(0)
                    xpub.close(0)

            t = threading.Thread(target=_proxy, daemon=True)
            t.start()
            # Small delay so the proxy is ready before clients connect
            time.sleep(0.1)
            self.is_broker = True
        except zmq.ZMQError:
            self.is_broker = False
            self.logger.info("🔗 Broker already running, connecting as client")

    def publish(self, topic: str, message: Any, sender_id: str = "unknown"):
        """Publish a JSON-serializable message (backwards compatible)."""
        payload = {
            "topic": topic,
            "message": message,
            "sender_id": sender_id,
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),
            "type": "json",
        }
        try:
            self.publisher.send_multipart([
                topic.encode("utf-8"),
                json.dumps(payload).encode("utf-8")
            ])
            self.logger.debug(f"📤 Published to {topic} : {type(message).__name__}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error publishing to {topic}: {e}")
            return False

    def publish_ndarray(self, topic: str, array: np.ndarray, sender_id: str = "unknown"):
        """Publish a numpy ndarray efficiently as a binary ZeroMQ frame with JSON header.

        The header contains shape/dtype so the subscriber can reconstruct the array.
        """
        try:
            if not array.flags.c_contiguous:
                array = np.ascontiguousarray(array)
            header = {
                "topic": topic,
                "sender_id": sender_id,
                "timestamp": time.time(),
                "message_id": str(uuid.uuid4()),
                "type": "ndarray",
                "shape": array.shape,
                "dtype": str(array.dtype),
            }
            self.publisher.send_multipart([
                topic.encode("utf-8"),
                json.dumps(header, separators=(",", ":")).encode("utf-8"),
                memoryview(array),
            ])
            self.logger.debug(f"📤 Published ndarray to {topic} : {array.shape} {array.dtype}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error publishing ndarray to {topic}: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable):
        if topic not in self.topic_callbacks:
            self.topic_callbacks[topic] = []
            self.subscriber.setsockopt(zmq.SUBSCRIBE, topic.encode("utf-8"))
            self.logger.info(f"🔔 Subscribed to topic: '{topic}'")
        self.topic_callbacks[topic].append(callback)
        if not self.running:
            self.start_listening()

    def subscribe_ndarray(self, topic: str, callback: Callable):
        """Subscribe to a topic expecting an image/ndarray.

        Ensures payload["message"] is a numpy.ndarray before invoking callback,
        converting from JSON/list if needed.
        """
        def _wrapper(payload: dict):
            try:
                msg = payload.get("message")
                if not isinstance(msg, np.ndarray):
                    # Convert JSON/list/object to ndarray (uint8 by default)
                    payload["message"] = np.array(msg, dtype=np.uint8)
                callback(payload)
            except Exception as e:
                self.logger.error(f"❌ subscribe_ndarray wrapper error for topic '{topic}': {e}")

        self.subscribe(topic, _wrapper)

    def start_listening(self):
        if self.running:
            return
        self.running = True
        self.listener_thread = threading.Thread(target=self._message_listener, daemon=True)
        self.listener_thread.start()
        self.logger.info("🎧 Started listening for messages")

    def stop(self):
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=1)
        try:
            self.publisher.close(0)
            self.subscriber.close(0)
        finally:
            # Do not terminate the shared Context; other components may use it
            pass
        self.logger.info("🛑 Event bus stopped")

    def _message_listener(self):
        poller = zmq.Poller()
        poller.register(self.subscriber, zmq.POLLIN)

        while self.running:
            try:
                socks = dict(poller.poll(100))
                if self.subscriber in socks and socks[self.subscriber] == zmq.POLLIN:
                    # Use zero-copy receive for potential binary frames
                    parts = self.subscriber.recv_multipart(flags=zmq.NOBLOCK, copy=False)
                    if len(parts) >= 2:
                        topic = parts[0].bytes.decode("utf-8")
                        body_frame = parts[1]
                        try:
                            payload = json.loads(body_frame.bytes.decode("utf-8"))
                        except Exception:
                            continue

                        # If this is an ndarray message and a binary frame is present, reconstruct
                        if payload.get("type") == "ndarray" and len(parts) >= 3:
                            bin_frame = parts[2]
                            try:
                                arr = np.frombuffer(memoryview(bin_frame.buffer), dtype=np.dtype(payload["dtype"]))
                                arr = arr.reshape(payload["shape"]).copy()  # copy to own memory
                                payload["message"] = arr
                            except Exception as e:
                                self.logger.error(f"❌ Failed to reconstruct ndarray for topic '{topic}': {e}")
                                continue

                        callbacks = self.topic_callbacks.get(topic, [])
                        for cb in callbacks:
                            try:
                                cb(payload)
                            except Exception as e:
                                self.logger.error(f"❌ Error in callback for topic '{topic}': {e}")
            except zmq.Again:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"❌ Error in message listener: {e}")