import random
from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from inventory.models import Equipment
from telemetry.models import HealthStatus, SensorReading
from telemetry.services.ml_service import AnomalyDetector
from telemetry.services.prediction_service import SensorForecaster
from telemetry.tasks import evaluate_equipment_health_task
from telemetry.api.serializers import HealthStatusSerializer


@pytest.fixture
def sample_timestamps():
    base_time = timezone.now() - timedelta(minutes=200)
    return [base_time + timedelta(minutes=5 * i) for i in range(40)]


@pytest.fixture
def steady_readings(sample_timestamps):
    random.seed(42)
    return [
        {
            "timestamp": ts,
            "temperature": 25.0 + random.uniform(-0.2, 0.2),
            "voltage": 220.0 + random.uniform(-0.5, 0.5),
            "vib_x": 0.05 + random.uniform(-0.002, 0.002),
            "vib_y": 0.05 + random.uniform(-0.002, 0.002),
            "vib_z": 0.05 + random.uniform(-0.002, 0.002),
        }
        for ts in sample_timestamps
    ]


@pytest.fixture
def thermal_drift_readings(sample_timestamps):
    # Temperature steadily ramping from 25°C up to 55°C
    return [
        {
            "timestamp": ts,
            "temperature": 25.0 + (30.0 * (i / 39.0)),
            "voltage": 220.0,
            "vib_x": 0.05,
            "vib_y": 0.05,
            "vib_z": 0.05,
        }
        for i, ts in enumerate(sample_timestamps)
    ]


@pytest.fixture
def vibration_drift_readings(sample_timestamps):
    # Vibration steadily increasing from 0.05G to 0.8G
    return [
        {
            "timestamp": ts,
            "temperature": 25.0,
            "voltage": 220.0,
            "vib_x": 0.05 + (0.75 * (i / 39.0)),
            "vib_y": 0.05 + (0.75 * (i / 39.0)),
            "vib_z": 0.05 + (0.75 * (i / 39.0)),
        }
        for i, ts in enumerate(sample_timestamps)
    ]


class TestSensorForecaster:

    def test_insufficient_historical_data(self):
        forecaster = SensorForecaster(horizon_steps=6, min_history=10)
        few_records = [
            {"temperature": 25.0, "voltage": 220.0, "vib_x": 0.05, "vib_y": 0.05, "vib_z": 0.05}
            for _ in range(5)
        ]
        result = forecaster.generate_forecast(few_records)
        assert result["status"] == "insufficient_data"
        assert result["horizon_steps"] == 0
        assert result["forecast"] == []

    def test_empty_historical_data(self):
        forecaster = SensorForecaster(horizon_steps=6, min_history=10)
        result = forecaster.generate_forecast([])
        assert result["status"] == "insufficient_data"
        assert result["forecast"] == []

    def test_constant_signal_forecast(self, sample_timestamps):
        forecaster = SensorForecaster(horizon_steps=6, min_history=10, alpha=0.3, beta=0.1)
        constant_records = [
            {
                "timestamp": ts,
                "temperature": 25.0,
                "voltage": 220.0,
                "vib_x": 0.05,
                "vib_y": 0.05,
                "vib_z": 0.05,
            }
            for ts in sample_timestamps
        ]
        result = forecaster.generate_forecast(constant_records)
        assert result["status"] == "success"
        assert len(result["forecast"]) == 6
        for pt in result["forecast"]:
            assert pytest.approx(pt["temperature"], abs=0.1) == 25.0
            assert pytest.approx(pt["voltage"], abs=0.1) == 220.0
            assert pytest.approx(pt["vib_x"], abs=0.01) == 0.05

    def test_missing_values_interpolation(self, sample_timestamps):
        forecaster = SensorForecaster(horizon_steps=6, min_history=10)
        records = [
            {
                "timestamp": ts,
                "temperature": 25.0 if i % 4 != 0 else None,
                "voltage": 220.0 if i % 3 != 0 else None,
                "vib_x": 0.05,
                "vib_y": 0.05,
                "vib_z": 0.05,
            }
            for i, ts in enumerate(sample_timestamps)
        ]
        result = forecaster.generate_forecast(records)
        assert result["status"] == "success"
        assert len(result["forecast"]) == 6
        for pt in result["forecast"]:
            assert pt["temperature"] is not None
            assert pt["voltage"] is not None

    def test_irregular_timestamps_and_horizon(self):
        forecaster = SensorForecaster(horizon_steps=6, min_history=10)
        base = datetime(2026, 1, 1, 12, 0, 0)
        # Irregular gaps: 4m, 6m, 5m -> median = 3 mins = 180s
        times = [
            base + timedelta(minutes=i * 5 + (1 if i % 2 == 0 else -1))
            for i in range(20)
        ]
        records = [
            {
                "timestamp": t,
                "temperature": 25.0,
                "voltage": 220.0,
                "vib_x": 0.05,
                "vib_y": 0.05,
                "vib_z": 0.05,
            }
            for t in times
        ]
        result = forecaster.generate_forecast(records)
        assert result["status"] == "success"
        assert result["horizon_steps"] == 6
        assert result["horizon_minutes"] is not None
        assert pytest.approx(result["horizon_minutes"], abs=0.5) == 18.0

    def test_thermal_drift_forecast_trajectory(self, thermal_drift_readings):
        forecaster = SensorForecaster(horizon_steps=6, min_history=10, alpha=0.4, beta=0.2)
        result = forecaster.generate_forecast(thermal_drift_readings)
        assert result["status"] == "success"
        forecast = result["forecast"]
        assert len(forecast) == 6
        # Temperature should continue to increase in the forecast
        assert forecast[-1]["temperature"] > forecast[0]["temperature"]
        assert forecast[0]["temperature"] >= 50.0

    def test_vibration_drift_forecast_trajectory(self, vibration_drift_readings):
        forecaster = SensorForecaster(horizon_steps=6, min_history=10, alpha=0.4, beta=0.2)
        result = forecaster.generate_forecast(vibration_drift_readings)
        assert result["status"] == "success"
        forecast = result["forecast"]
        assert len(forecast) == 6
        assert forecast[-1]["vib_x"] > forecast[0]["vib_x"]


class TestPredictiveIsolationForestIntegration:

    def test_steady_health_forecast_is_normal(self, steady_readings):
        detector = AnomalyDetector(contamination=0.05, n_estimators=20)
        forecaster = SensorForecaster(horizon_steps=6, min_history=10)
        
        # Fit baseline on steady readings
        curr_score, curr_anomaly = detector.train_and_predict(steady_readings)
        assert curr_anomaly is False

        # Generate and evaluate forecast
        forecast_res = forecaster.generate_forecast(steady_readings)
        worst_score, pred_status, eval_pts = detector.evaluate_forecast(forecast_res["forecast"])
        
        assert pred_status == "NORMAL"
        assert worst_score >= 0.0
        assert len(eval_pts) == 6

    def test_thermal_drift_forecast_triggers_predictive_warning_or_critical(self, thermal_drift_readings):
        detector = AnomalyDetector(contamination=0.05, n_estimators=20)
        forecaster = SensorForecaster(horizon_steps=6, min_history=10, alpha=0.4, beta=0.2)

        # First 35 points are steady normal, last 5 points start drifting
        mixed_readings = [
            {
                "timestamp": ts,
                "temperature": 25.0 + random.uniform(-0.2, 0.2),
                "voltage": 220.0,
                "vib_x": 0.05,
                "vib_y": 0.05,
                "vib_z": 0.05,
            }
            for ts in [datetime(2026, 1, 1) + timedelta(minutes=5 * i) for i in range(35)]
        ]
        # Append 5 rapidly rising temperature points (from 25 up to 45)
        for j in range(5):
            mixed_readings.append({
                "timestamp": datetime(2026, 1, 1) + timedelta(minutes=5 * (35 + j)),
                "temperature": 25.0 + (j + 1) * 4.0, # 29, 33, 37, 41, 45
                "voltage": 220.0,
                "vib_x": 0.05,
                "vib_y": 0.05,
                "vib_z": 0.05,
            })

        detector.train_and_predict(mixed_readings)
        forecast_res = forecaster.generate_forecast(mixed_readings)
        worst_score, pred_status, eval_pts = detector.evaluate_forecast(forecast_res["forecast"])
        
        # The forecasted future points (over 50°C) must be flagged as anomalous
        assert pred_status in ["WARNING", "CRITICAL"]
        assert worst_score < 0.0


@pytest.mark.django_db
class TestPredictiveTaskAndDatabase:

    def test_background_task_creates_predictive_health_record(self, steady_readings):
        equipment = Equipment.objects.create(
            name="Solar Inverter Alpha",
            mac_address="TEST-EQ-01",
            equipment_type=Equipment.Type.INVERTER,
            is_active=True,
        )

        for r in steady_readings:
            SensorReading.objects.create(
                equipment=equipment,
                temperature=r["temperature"],
                voltage=r["voltage"],
                vib_x=r["vib_x"],
                vib_y=r["vib_y"],
                vib_z=r["vib_z"],
            )

        msg = evaluate_equipment_health_task()
        assert "Evaluated health and predictive trajectories" in msg

        health = HealthStatus.objects.filter(equipment=equipment).latest("prediction_timestamp")
        assert health.status == HealthStatus.Status.NORMAL
        assert health.predicted_status == HealthStatus.Status.NORMAL
        assert health.prediction_horizon_steps == 6
        assert health.forecasted_values is not None
        assert len(health.forecasted_values) == 6

    def test_serializer_outputs_predictive_fields(self, steady_readings):
        equipment = Equipment.objects.create(
            name="Pump Station Beta",
            mac_address="TEST-EQ-02",
            equipment_type=Equipment.Type.MOTOR,
            is_active=True,
        )
        health = HealthStatus.objects.create(
            equipment=equipment,
            anomaly_score=0.12,
            status=HealthStatus.Status.NORMAL,
            predicted_status=HealthStatus.Status.WARNING,
            predictive_anomaly_score=-0.05,
            prediction_horizon_steps=6,
            prediction_horizon_minutes=30.0,
            forecasted_values=[{"step": 1, "temperature": 32.0}],
            prediction_generated_at=timezone.now(),
        )

        serializer = HealthStatusSerializer(health)
        data = serializer.data
        assert data["predicted_status"] == "WARNING"
        assert data["predictive_anomaly_score"] == -0.05
        assert data["prediction_horizon_steps"] == 6
        assert data["prediction_horizon_minutes"] == 30.0
        assert len(data["forecasted_values"]) == 1
