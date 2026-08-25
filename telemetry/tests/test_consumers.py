import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from config.asgi import application


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_equipment_telemetry_consumer():
    communicator = WebsocketCommunicator(application, "/ws/telemetry/equipment/1/")
    connected, _ = await communicator.connect()
    assert connected

    # Ping pong test
    await communicator.send_json_to({"type": "ping", "timestamp": 123456})
    response = await communicator.receive_json_from()
    assert response["type"] == "pong"
    assert response["timestamp"] == 123456

    # Test group broadcast
    channel_layer = get_channel_layer()
    test_reading = {
        "id": 1,
        "equipment": 1,
        "temperature": 45.2,
        "voltage": 220.5,
        "vib_x": 0.12,
        "vib_y": 0.05,
        "vib_z": 0.08,
        "timestamp": "2026-08-25T15:00:00Z",
    }
    await channel_layer.group_send(
        "equipment_1",
        {
            "type": "telemetry_reading",
            "data": test_reading,
        },
    )

    response = await communicator.receive_json_from()
    assert response["type"] == "telemetry_reading"
    assert response["data"]["temperature"] == 45.2

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_global_telemetry_consumer():
    communicator = WebsocketCommunicator(application, "/ws/telemetry/global/")
    connected, _ = await communicator.connect()
    assert connected

    channel_layer = get_channel_layer()
    test_health = {
        "id": 10,
        "equipment": 2,
        "equipment_name": "Turbine Alpha",
        "anomaly_score": -0.22,
        "status": "CRITICAL",
    }
    await channel_layer.group_send(
        "global_telemetry",
        {
            "type": "health_update",
            "data": test_health,
        },
    )

    response = await communicator.receive_json_from()
    assert response["type"] == "health_update"
    assert response["data"]["status"] == "CRITICAL"

    await communicator.disconnect()
