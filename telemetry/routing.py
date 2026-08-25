from django.urls import re_path, path
from telemetry.consumers import TelemetryConsumer

websocket_urlpatterns = [
    path("ws/telemetry/equipment/<int:equipment_id>/", TelemetryConsumer.as_asgi()),
    path("ws/telemetry/global/", TelemetryConsumer.as_asgi()),
    re_path(r"^ws/telemetry/?$", TelemetryConsumer.as_asgi()),
]
