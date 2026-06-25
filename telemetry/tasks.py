import time
import psutil
from inventory.models import Equipment
from telemetry.models import HealthStatus
from telemetry.models import SensorReading
from telemetry.services.alert_service import AlertService
from telemetry.services.ml_service import AnomalyDetector


def evaluate_equipment_health_task():
    """
    This is the Background Worker Task.
    It runs periodically (e.g., every 1 minute) to check the health of all equipment.
    """
    
    # 1. Find all active equipment in the database
    equipments = Equipment.objects.filter(is_active=True)
    
    # 2. Prepare the Machine Learning Brain
    # 'contamination=0.05' means we expect about 5% of our data might be anomalies.
    detector = AnomalyDetector(contamination=0.05, n_estimators=15)

    for eq in equipments:
        # 3. Get the latest 40 sensor readings for this specific equipment.
        # We order by '-timestamp' to quickly get the newest ones first.
        recent_qs = SensorReading.objects.filter(equipment=eq).order_by("-timestamp")[
            :40
        ]
        
        # 4. Format the data for the ML model
        # The ML model expects a list of dictionaries in chronological order (oldest -> newest).
        # We use '[::-1]' to reverse the list back into chronological order.
        recent_list = list(recent_qs.values(*detector.features, "timestamp"))[::-1]

        # 5. Check if we have enough data
        # If the ESP32 hasn't sent 40 readings yet, we skip this equipment and wait.
        if len(recent_list) < 40:
            # We don't have enough data to make an ML prediction yet
            continue

        # --- Track Performance Metrics (Section 3.5) ---
        start_time = time.perf_counter()
        
        # 6. Ask the ML model for a prediction
        # 'score' is a number (negative = bad, positive = good)
        # 'is_anomaly' is a simple True/False
        score, is_anomaly = detector.train_and_predict(recent_list)

        end_time = time.perf_counter()
        processing_latency_ms = (end_time - start_time) * 1000.0
        
        cpu_load_percent = psutil.cpu_percent(interval=None)
        # Convert used memory to MB
        ram_allocation_mb = psutil.virtual_memory().used / (1024 * 1024)

        # 7. Convert the ML score into a Human-Readable Status
        if score < -0.15:
            # Very negative score means something is severely wrong!
            status = HealthStatus.Status.CRITICAL
            latest_timestamp = recent_list[-1]["timestamp"]
            
            # Trigger an immediate alert (e.g., email or SMS) to warn the Park Rangers!
            AlertService.trigger_critical_alert(eq.name, score, latest_timestamp)
            
        elif is_anomaly or score < 0.0:
            # Slightly negative score, or flagged as an anomaly. Needs maintenance soon.
            status = HealthStatus.Status.WARNING
            
        else:
            # Positive score means everything is running perfectly fine.
            status = HealthStatus.Status.NORMAL

        # 8. Save the prediction and metrics to the database
        HealthStatus.objects.create(
            equipment=eq, 
            anomaly_score=score, 
            status=status,
            processing_latency_ms=processing_latency_ms,
            cpu_load_percent=cpu_load_percent,
            ram_allocation_mb=ram_allocation_mb
        )

    return f"Evaluated health for {equipments.count()} active equipment."
