import pytest
from telemetry.services.ml_service import AnomalyDetector

import random

@pytest.fixture
def normal_data():
    # 40 records of normal data with slight variations so variance is not zero
    return [
        {
            "temperature": 25.0 + random.uniform(-1, 1), 
            "voltage": 220.0 + random.uniform(-2, 2), 
            "vib_x": 0.05 + random.uniform(-0.01, 0.01), 
            "vib_y": 0.05 + random.uniform(-0.01, 0.01), 
            "vib_z": 0.05 + random.uniform(-0.01, 0.01)
        }
        for _ in range(40)
    ]

class TestAnomalyDetector:

    def test_insufficient_data(self):
        detector = AnomalyDetector(contamination=0.05, n_estimators=15)
        # Less than 10 points
        data = [{"temperature": 25.0, "voltage": 220.0, "vib_x": 0.05, "vib_y": 0.05, "vib_z": 0.05} for _ in range(5)]
        score, is_anomaly = detector.train_and_predict(data)
        assert score == 1.0
        assert is_anomaly is False

    def test_predict_normal(self, normal_data):
        detector = AnomalyDetector(contamination=0.05, n_estimators=15)
        # Add another normal point as the latest
        data = normal_data + [{"temperature": 25.5, "voltage": 221.0, "vib_x": 0.06, "vib_y": 0.04, "vib_z": 0.05}]
        score, is_anomaly = detector.train_and_predict(data)
        assert is_anomaly == False
        assert score > 0.0

    def test_predict_thermal_anomaly(self, normal_data):
        detector = AnomalyDetector(contamination=0.05, n_estimators=15)
        # Add a high temperature anomaly as the latest point
        data = normal_data + [{"temperature": 60.0, "voltage": 220.0, "vib_x": 0.05, "vib_y": 0.05, "vib_z": 0.05}]
        score, is_anomaly = detector.train_and_predict(data)
        assert is_anomaly == True
        assert score < 0.0

    def test_predict_voltage_anomaly(self, normal_data):
        detector = AnomalyDetector(contamination=0.05, n_estimators=15)
        # Add a voltage spike anomaly as the latest point
        data = normal_data + [{"temperature": 25.0, "voltage": 260.0, "vib_x": 0.05, "vib_y": 0.05, "vib_z": 0.05}]
        score, is_anomaly = detector.train_and_predict(data)
        assert is_anomaly == True
        assert score < 0.0
