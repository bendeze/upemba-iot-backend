import pytest
from django.utils import timezone
from datetime import timedelta
from inventory.models import Equipment
from telemetry.models import SensorReading, HealthStatus
from telemetry.tasks import evaluate_equipment_health_task

@pytest.mark.django_db
class TestTelemetryIntegration:
    
    @pytest.fixture
    def equipment(self):
        return Equipment.objects.create(name="Test Tower", mac_address="TEST-MAC-01", equipment_type="SERVER", is_active=True)

    @pytest.fixture
    def setup_normal_readings(self, equipment):
        import random
        random.seed(42)
        base_time = timezone.now() - timedelta(minutes=100)
        readings = []
        for i in range(40):
            r = SensorReading(
                equipment=equipment,
                temperature=25.0 + random.uniform(-0.5, 0.5),
                voltage=220.0 + random.uniform(-1, 1),
                vib_x=0.05 + random.uniform(-0.005, 0.005),
                vib_y=0.05 + random.uniform(-0.005, 0.005),
                vib_z=0.05 + random.uniform(-0.005, 0.005),
            )
            r.timestamp = base_time + timedelta(minutes=i)
            readings.append(r)
            
        SensorReading.objects.bulk_create(readings)
        return equipment

    def test_evaluate_equipment_health_normal(self, setup_normal_readings):
        # Run the background task
        result = evaluate_equipment_health_task()
        assert "Evaluated health" in result
        
        # Verify a HealthStatus was created
        health = HealthStatus.objects.filter(equipment=setup_normal_readings).latest("prediction_timestamp")
        assert health.status == HealthStatus.Status.NORMAL
        assert health.anomaly_score > 0.0
        assert health.processing_latency_ms is not None
        assert health.cpu_load_percent is not None
        assert health.ram_allocation_mb is not None

    def test_evaluate_equipment_health_anomaly(self, setup_normal_readings):
        # Inject one anomalous reading
        SensorReading.objects.create(
            equipment=setup_normal_readings,
            temperature=60.0,
            voltage=260.0, # Spike
            vib_x=0.85,
            vib_y=0.85,
            vib_z=0.85,
        )
        
        # Run the background task
        evaluate_equipment_health_task()
        
        # Verify the new HealthStatus flags it as WARNING or CRITICAL
        health = HealthStatus.objects.filter(equipment=setup_normal_readings).latest("prediction_timestamp")
        assert health.status in [HealthStatus.Status.WARNING, HealthStatus.Status.CRITICAL]
        assert health.anomaly_score < 0.0
