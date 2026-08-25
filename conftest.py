import pytest
from django.utils import timezone

from inventory.models import Equipment, MaintenanceLog
from telemetry.models import HealthStatus, SensorReading
from users.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        email="testuser@upemba.park",
        password="password123",
        role=User.Role.TECHNICIAN,
    )


@pytest.fixture
def equipment(db):
    return Equipment.objects.create(
        name="Main Solar Inverter",
        mac_address="INV-001",
        equipment_type=Equipment.Type.INVERTER,
        is_active=True,
    )


@pytest.fixture
def maintenance_log(db, equipment, user):
    return MaintenanceLog.objects.create(
        equipment=equipment,
        author=user,
        description="Overheating during peak sun",
        action_taken="Cleaned air filter and inspected cooling fan",
    )


@pytest.fixture
def sensor_reading(db, equipment):
    return SensorReading.objects.create(
        equipment=equipment,
        temperature=25.0,
        voltage=220.0,
        vib_x=0.05,
        vib_y=0.05,
        vib_z=0.05,
    )


@pytest.fixture
def health_status(db, equipment):
    return HealthStatus.objects.create(
        equipment=equipment,
        anomaly_score=0.15,
        status=HealthStatus.Status.NORMAL,
        predicted_status=HealthStatus.Status.NORMAL,
        predictive_anomaly_score=0.12,
        prediction_horizon_steps=6,
        prediction_horizon_minutes=30.0,
        forecasted_values=[],
    )
