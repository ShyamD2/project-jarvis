"""
Hybrid Event Mesh client for J.A.R.V.I.S.
Publishes and routes events between Local Fast-Path (MQTT) and Cloud Heavy-Path (AWS EventBridge).
"""

from __future__ import annotations
import json
import threading
from typing import Callable, Dict, List, Optional
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    ClientError = Exception

from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisEventMesh")

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False


class EventMesh:
    def __init__(self):
        self._mqtt_client: Optional[Any] = None
        self._eventbridge_client = None
        self._subscribers: Dict[str, List[Callable[[JarvisEvent], None]]] = {}
        self._is_connected_mqtt = False

        # Initialize AWS / LocalStack EventBridge client
        if BOTO3_AVAILABLE:
            try:
                kwargs = {"region_name": config.aws_region}
                if config.use_localstack:
                    kwargs["endpoint_url"] = config.localstack_endpoint
                    kwargs["aws_access_key_id"] = "test"
                    kwargs["aws_secret_access_key"] = "test"
                from botocore.config import Config as BotoConfig
                kwargs["config"] = BotoConfig(connect_timeout=1.5, read_timeout=1.5, retries={"max_attempts": 1})
                self._eventbridge_client = boto3.client("events", **kwargs)
            except Exception as e:
                logger.warning(f"Could not initialize EventBridge client: {e}")
        else:
            logger.info("boto3 not installed; running in local in-memory event mesh mode.")

        # Initialize MQTT if library is present
        if PAHO_AVAILABLE:
            self._init_mqtt()
        else:
            logger.info("paho-mqtt not installed yet; running in local in-memory event mode.")

    def _init_mqtt(self):
        try:
            self._mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="jarvis_core_mesh")
            if config.mqtt_user and config.mqtt_password:
                self._mqtt_client.username_pw_set(config.mqtt_user, config.mqtt_password)

            self._mqtt_client.on_connect = self._on_mqtt_connect
            self._mqtt_client.on_message = self._on_mqtt_message

            # Connect non-blocking
            def connect_loop():
                try:
                    self._mqtt_client.connect(config.mqtt_broker, config.mqtt_port, keepalive=60)
                    self._mqtt_client.loop_start()
                except Exception as ex:
                    logger.warning(f"MQTT Broker at {config.mqtt_broker}:{config.mqtt_port} not reachable: {ex}. Fast-path will use in-memory dispatch.")

            t = threading.Thread(target=connect_loop, daemon=True)
            t.start()
        except Exception as e:
            logger.warning(f"Failed to start MQTT client: {e}")

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._is_connected_mqtt = True
            logger.info("Connected to Local Fast-Path MQTT Broker.")
            # Subscribe to all jarvis topics
            client.subscribe("jarvis/#")
        else:
            logger.warning(f"MQTT connection failed with code {rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            event = JarvisEvent.from_dict(payload)
            self._dispatch_local(event)
        except Exception as e:
            logger.error(f"Error parsing MQTT event: {e}")

    def subscribe(self, event_type: str, handler: Callable[[JarvisEvent], None]):
        """Subscribe an in-process callback to an event type (e.g., 'sensory.clap', '*')"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def _dispatch_local(self, event: JarvisEvent):
        """Dispatch event to local registered handlers"""
        # Exact match handlers
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler error for event {event.type}: {e}")
        # Wildcard handlers
        for handler in self._subscribers.get("*", []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Wildcard handler error: {e}")

    def publish(self, event: JarvisEvent, fast_path: bool = True, cloud_sync: bool = True):
        """
        Dual-dispatch:
        1. Fast-Path: In-memory & Local MQTT for instant <30ms reflex
        2. Heavy-Path: AWS EventBridge for telemetry, audit, and cloud coordination
        """
        # 1. In-process dispatch
        self._dispatch_local(event)

        # 2. Local MQTT fast-path publish
        if fast_path and self._is_connected_mqtt and self._mqtt_client:
            try:
                topic = f"jarvis/{event.type.replace('.', '/')}"
                self._mqtt_client.publish(topic, event.to_json())
            except Exception as e:
                logger.warning(f"MQTT publish failed: {e}")

        # 3. Cloud Heavy-Path EventBridge publish
        if cloud_sync and self._eventbridge_client:
            def publish_cloud():
                try:
                    self._eventbridge_client.put_events(
                        Entries=[
                            {
                                "Source": event.source,
                                "DetailType": event.type,
                                "Detail": json.dumps(event.data),
                                "EventBusName": config.event_bus_name,
                                "Time": event.time
                            }
                        ]
                    )
                except ClientError as ce:
                    logger.debug(f"EventBridge sync failed: {ce}")
                except Exception as ex:
                    logger.debug(f"Cloud sync error: {ex}")

            threading.Thread(target=publish_cloud, daemon=True).start()


# Global mesh instance
mesh = EventMesh()
