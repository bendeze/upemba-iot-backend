import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class TelemetryConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for streaming real-time sensor telemetry and health updates.
    Supports either equipment-specific stream or global stream.
    """

    async def connect(self):
        self.equipment_id = self.scope["url_route"]["kwargs"].get("equipment_id")
        self.groups_joined = []

        if self.equipment_id:
            # Subscribe to equipment-specific room
            self.equipment_group = f"equipment_{self.equipment_id}"
            await self.channel_layer.group_add(self.equipment_group, self.channel_name)
            self.groups_joined.append(self.equipment_group)
        else:
            # Subscribe to global room
            self.global_group = "global_telemetry"
            await self.channel_layer.group_add(self.global_group, self.channel_name)
            self.groups_joined.append(self.global_group)

        await self.accept()
        logger.info(
            f"[WebSocket] Client connected: {self.channel_name} (groups: {self.groups_joined})"
        )

    async def disconnect(self, close_code):
        for group in self.groups_joined:
            await self.channel_layer.group_discard(group, self.channel_name)
        logger.info(
            f"[WebSocket] Client disconnected: {self.channel_name} (code: {close_code})"
        )

    async def receive_json(self, content, **kwargs):
        """
        Handle incoming messages from the frontend client (e.g. heartbeat or subscribe).
        """
        msg_type = content.get("type")
        if msg_type == "ping":
            await self.send_json({"type": "pong", "timestamp": content.get("timestamp")})
        elif msg_type == "subscribe_equipment":
            new_eq_id = content.get("equipment_id")
            if new_eq_id:
                new_group = f"equipment_{new_eq_id}"
                await self.channel_layer.group_add(new_group, self.channel_name)
                if new_group not in self.groups_joined:
                    self.groups_joined.append(new_group)
                await self.send_json({"type": "subscribed", "equipment_id": new_eq_id})

    async def telemetry_reading(self, event):
        """
        Broadcast handler for new sensor reading from MQTT or simulator.
        """
        await self.send_json({
            "type": "telemetry_reading",
            "data": event.get("data"),
        })

    async def health_update(self, event):
        """
        Broadcast handler for ML health evaluation and predictive status updates.
        """
        await self.send_json({
            "type": "health_update",
            "data": event.get("data"),
        })

    async def alert_notification(self, event):
        """
        Broadcast handler for critical anomaly alerts.
        """
        await self.send_json({
            "type": "alert_notification",
            "data": event.get("data"),
        })
