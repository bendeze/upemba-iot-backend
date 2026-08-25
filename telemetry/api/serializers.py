from rest_framework import serializers

from telemetry.models import HealthStatus
from telemetry.models import SensorReading


class HealthStatusSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)

    class Meta:
        model = HealthStatus
        fields = [
            "id",
            "equipment",
            "equipment_name",
            "anomaly_score",
            "status",
            "prediction_timestamp",
            "predicted_status",
            "predictive_anomaly_score",
            "prediction_horizon_steps",
            "prediction_horizon_minutes",
            "forecasted_values",
            "prediction_generated_at",
            "processing_latency_ms",
            "cpu_load_percent",
            "ram_allocation_mb",
        ]
        read_only_fields = [
            "id",
            "prediction_timestamp",
            "equipment_name",
            "predicted_status",
            "predictive_anomaly_score",
            "prediction_horizon_steps",
            "prediction_horizon_minutes",
            "forecasted_values",
            "prediction_generated_at",
        ]


class SensorReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorReading
        fields = [
            "id",
            "equipment",
            "temperature",
            "voltage",
            "vib_x",
            "vib_y",
            "vib_z",
            "timestamp",
        ]
        read_only_fields = ["id", "timestamp"]
