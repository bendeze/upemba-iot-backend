import json
import logging

import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from inventory.models import Equipment
from telemetry.api.serializers import SensorReadingSerializer
from telemetry.models import SensorReading

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    This is a custom Django Command. You run it using `python manage.py mqtt_listener`.
    It runs forever in the background, constantly listening for new messages from the Mosquitto broker.
    """
    help = "Starts a long-running process that listens to the Mosquitto MQTT broker for ESP32 telemetry."

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """
        This function is called automatically the moment we successfully connect to the Mosquitto Broker.
        """
        if rc == 0:
            self.stdout.write(self.style.SUCCESS("Connected to Mosquitto MQTT Broker!"))
            
            # Get the topic we want to listen to from settings (e.g., 'upemba/sensors/+/telemetry')
            topic = getattr(settings, "MQTT_TELEMETRY_TOPIC", "upemba/telemetry")
            
            # Tell Mosquitto: "Send me every message published to this topic!"
            client.subscribe(topic)
            
            self.stdout.write(f"Subscribed to topic: {topic}")
        else:
            self.stderr.write(self.style.ERROR(f"Failed to connect, return code {rc}"))

    def on_message(self, client, userdata, msg):
        """
        This function is triggered EVERY TIME a new message arrives on the subscribed topic.
        It is responsible for reading the ESP32's data and saving it to our SQLite database.
        """
        # The ESP32 sends data as raw bytes. We decode it into a normal text string.
        payload = msg.payload.decode("utf-8")
        
        try:
            # Convert the text string (JSON) into a Python dictionary
            data = json.loads(payload)
            
            # Extract the equipment ID (e.g., 'EQUIP-INV-001')
            device_id = data.get("device_id")
            
            # Extract the actual sensor measurements
            telemetry = data.get("data", {})
            temp = telemetry.get("temp")
            volt = telemetry.get("volt")
            
            # Vibration is nested inside another dictionary, so we dig one level deeper
            vib = telemetry.get("vib", {})
            vib_x = vib.get("x")
            vib_y = vib.get("y")
            vib_z = vib.get("z")

            # Safety check: If the ESP32 forgot to send a measurement, we ignore the message
            if None in (device_id, temp, volt, vib_x, vib_y, vib_z):
                logger.warning(f"Incomplete payload missing keys: {payload}")
                return

            # Find the Equipment in our database. 
            # If it doesn't exist yet, automatically create a new entry for it!
            equipment, _ = Equipment.objects.get_or_create(
                mac_address=device_id,
                defaults={
                    "name": f"Sensor Node {device_id}",
                    "equipment_type": Equipment.Type.INVERTER,
                },
            )

            # Create a new row in the SensorReading database table with all the measurements
            reading = SensorReading.objects.create(
                equipment=equipment,
                temperature=temp,
                voltage=volt,
                vib_x=vib_x,
                vib_y=vib_y,
                vib_z=vib_z,
            )
            
            # Broadcast real-time sensor reading to WebSocket clients
            try:
                channel_layer = get_channel_layer()
                if channel_layer:
                    reading_data = SensorReadingSerializer(reading).data
                    # Equipment-specific group
                    async_to_sync(channel_layer.group_send)(
                        f"equipment_{equipment.id}",
                        {
                            "type": "telemetry_reading",
                            "data": reading_data,
                        },
                    )
                    # Global telemetry group
                    async_to_sync(channel_layer.group_send)(
                        "global_telemetry",
                        {
                            "type": "telemetry_reading",
                            "data": reading_data,
                        },
                    )
            except Exception as ws_err:
                logger.warning(f"Failed to broadcast telemetry via WebSockets: {ws_err}")

            # Print a success message to the terminal so the user knows it's working
            self.stdout.write(
                self.style.SUCCESS(
                    f"Saved & Broadcast reading for {device_id}: Temp {temp}, Volt {volt}",
                ),
            )

        except json.JSONDecodeError:
            # If the ESP32 sends garbage text instead of JSON, we log an error instead of crashing
            logger.exception(f"Malformed JSON payload: {payload}")
        except Exception as e:
            # Catch any other unexpected errors (like database connection issues)
            logger.exception(f"Error processing MQTT message: {e}")

    def handle(self, *args, **options):
        """
        This is the main entry point that runs when you type `python manage.py mqtt_listener`.
        It configures the MQTT client and starts the infinite listening loop.
        """
        
        # 1. Create the MQTT Client object
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="django_mqtt_listener",
        )
        
        # 2. Attach our custom functions to handle connecting and receiving messages
        client.on_connect = self.on_connect
        client.on_message = self.on_message

        # 3. Get connection details (IP address, Port) from Django settings
        broker_host = getattr(settings, "MQTT_BROKER_HOST", "mosquitto")
        broker_port = getattr(settings, "MQTT_BROKER_PORT", 1883)
        broker_user = getattr(settings, "MQTT_BROKER_USER", None)
        broker_pass = getattr(settings, "MQTT_BROKER_PASSWORD", None)

        if broker_user and broker_pass:
            client.username_pw_set(broker_user, broker_pass)

        self.stdout.write(f"Connecting to broker {broker_host}:{broker_port}...")

        try:
            # 4. Connect to the Mosquitto Broker on the network
            client.connect(broker_host, broker_port, 60)
            
            # 5. Start the infinite loop! This blocks the terminal and listens forever.
            client.loop_forever()
            
        except KeyboardInterrupt:
            # Handle the user pressing Ctrl+C gracefully
            self.stdout.write(self.style.WARNING("MQTT Listener stopped by user."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error connecting to MQTT Broker: {e}"))
