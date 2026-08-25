import logging
import time
import psutil
from django.conf import settings
from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from inventory.models import Equipment
from telemetry.api.serializers import HealthStatusSerializer
from telemetry.models import HealthStatus
from telemetry.models import SensorReading
from telemetry.services.alert_service import AlertService
from telemetry.services.ml_service import AnomalyDetector
from telemetry.services.prediction_service import SensorForecaster

logger = logging.getLogger(__name__)


def evaluate_equipment_health_task():
    """
    This is the Background Worker Task.
    It runs periodically (e.g., every 1 minute) to check the current health of all equipment
    and forecast near-future telemetry trajectories to detect emerging anomalous conditions.
    """
    
    # 1. Find all active equipment in the database
    equipments = Equipment.objects.filter(is_active=True)
    
    history_window = getattr(settings, "PREDICTION_HISTORY_WINDOW", 40)
    min_history = getattr(settings, "PREDICTION_MIN_HISTORY", 10)
    horizon_steps = getattr(settings, "PREDICTION_HORIZON_STEPS", 6)

    # 2. Prepare the Machine Learning Detector & Forecaster
    detector = AnomalyDetector(contamination=0.05, n_estimators=15)
    forecaster = SensorForecaster(
        horizon_steps=horizon_steps,
        min_history=min_history,
    )

    for eq in equipments:
        # 3. Get the latest sensor readings for this specific equipment.
        recent_qs = SensorReading.objects.filter(equipment=eq).order_by("-timestamp", "-id")[
            :history_window
        ]
        
        # 4. Format the data for the ML model (chronological order)
        recent_list = list(recent_qs.values(*detector.features, "timestamp"))[::-1]

        # 5. Check if we have enough data
        if len(recent_list) < min_history:
            logger.info(f"Skipping {eq.name}: insufficient data ({len(recent_list)} < {min_history}).")
            continue

        # --- Track Performance Metrics ---
        start_time = time.perf_counter()
        
        # 6. Evaluate CURRENT Anomaly State
        score, is_anomaly = detector.train_and_predict(recent_list)

        # 7. Evaluate SHORT-TERM PREDICTIVE Trajectory
        predicted_status = None
        predictive_anomaly_score = None
        prediction_horizon_steps = horizon_steps
        prediction_horizon_minutes = None
        forecasted_values = None
        prediction_generated_at = None

        try:
            forecast_result = forecaster.generate_forecast(recent_list)
            if forecast_result.get("status") == "success" and forecast_result.get("forecast"):
                worst_score, pred_stat, _ = detector.evaluate_forecast(
                    forecast_result["forecast"]
                )
                predicted_status = pred_stat
                predictive_anomaly_score = worst_score
                prediction_horizon_steps = forecast_result.get("horizon_steps", horizon_steps)
                prediction_horizon_minutes = forecast_result.get("horizon_minutes")
                forecasted_values = forecast_result.get("forecast")
                prediction_generated_at = timezone.now()
        except Exception as pred_err:
            logger.warning(
                f"Predictive forecasting encountered an error for {eq.name}: {pred_err}",
                exc_info=True,
            )

        end_time = time.perf_counter()
        processing_latency_ms = (end_time - start_time) * 1000.0
        
        cpu_load_percent = psutil.cpu_percent(interval=None)
        ram_allocation_mb = psutil.virtual_memory().used / (1024 * 1024)

        # 8. Convert the ML score into a Human-Readable Current Status
        if score < -0.15:
            # Very negative score means something is severely wrong!
            status = HealthStatus.Status.CRITICAL
            latest_timestamp = recent_list[-1]["timestamp"]
            
            # Trigger an immediate alert to warn the Park Rangers!
            AlertService.trigger_critical_alert(eq.name, score, latest_timestamp)
            
        elif is_anomaly or score < 0.0:
            # Slightly negative score, or flagged as an anomaly. Needs maintenance soon.
            status = HealthStatus.Status.WARNING
            
        else:
            # Positive score means everything is running normally.
            status = HealthStatus.Status.NORMAL

        # 9. Save both Current and Predictive Health Assessments to the database
        health_record = HealthStatus.objects.create(
            equipment=eq, 
            anomaly_score=score, 
            status=status,
            predicted_status=predicted_status,
            predictive_anomaly_score=predictive_anomaly_score,
            prediction_horizon_steps=prediction_horizon_steps,
            prediction_horizon_minutes=prediction_horizon_minutes,
            forecasted_values=forecasted_values,
            prediction_generated_at=prediction_generated_at,
            processing_latency_ms=processing_latency_ms,
            cpu_load_percent=cpu_load_percent,
            ram_allocation_mb=ram_allocation_mb,
        )

        # Broadcast health status update to WebSocket clients
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                health_data = HealthStatusSerializer(health_record).data
                # Equipment specific
                async_to_sync(channel_layer.group_send)(
                    f"equipment_{eq.id}",
                    {
                        "type": "health_update",
                        "data": health_data,
                    },
                )
                # Global stream
                async_to_sync(channel_layer.group_send)(
                    "global_telemetry",
                    {
                        "type": "health_update",
                        "data": health_data,
                    },
                )
                # If Critical or Warning, send alert notification
                if status in (HealthStatus.Status.CRITICAL, HealthStatus.Status.WARNING):
                    async_to_sync(channel_layer.group_send)(
                        "global_telemetry",
                        {
                            "type": "alert_notification",
                            "data": {
                                "equipment_id": eq.id,
                                "equipment_name": eq.name,
                                "status": status,
                                "anomaly_score": score,
                                "timestamp": timezone.now().isoformat(),
                            },
                        },
                    )
        except Exception as ws_err:
            logger.warning(f"Failed to broadcast health update via WebSockets: {ws_err}")

    return f"Evaluated health and predictive trajectories for {equipments.count()} active equipment."

