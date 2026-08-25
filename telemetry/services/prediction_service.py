import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from django.conf import settings

logger = logging.getLogger(__name__)


class SensorForecaster:
    """
    Short-Term Sensor Trajectory Forecaster using Holt's Linear Exponential Smoothing (Double Exponential Smoothing).
    
    This service models the local level and trend momentum for multidimensional sensor telemetry
    (temperature, voltage, vib_x, vib_y, vib_z) to project expected near-future sensor trajectories.
    
    The forecasted values are subsequently evaluated by the Isolation Forest model to detect whether 
    the system is on course to enter an anomalous operating regime.
    """

    def __init__(
        self,
        horizon_steps: Optional[int] = None,
        min_history: Optional[int] = None,
        alpha: Optional[float] = None,
        beta: Optional[float] = None,
    ):
        self.features = ["temperature", "voltage", "vib_x", "vib_y", "vib_z"]
        self.horizon_steps = horizon_steps or getattr(settings, "PREDICTION_HORIZON_STEPS", 6)
        self.min_history = min_history or getattr(settings, "PREDICTION_MIN_HISTORY", 10)
        self.alpha = alpha if alpha is not None else getattr(settings, "PREDICTION_HOLT_ALPHA", 0.3)
        self.beta = beta if beta is not None else getattr(settings, "PREDICTION_HOLT_BETA", 0.1)

    def _determine_sampling_interval(
        self, df: pd.DataFrame
    ) -> Tuple[Optional[timedelta], Optional[float]]:
        """
        Determines the empirical sampling interval from historical timestamps.
        Returns (timedelta_interval, interval_minutes).
        """
        if "timestamp" not in df.columns:
            default_min = getattr(settings, "PREDICTION_DEFAULT_INTERVAL_MINUTES", 5.0)
            return timedelta(minutes=default_min), default_min

        timestamps = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
        if len(timestamps) < 2:
            default_min = getattr(settings, "PREDICTION_DEFAULT_INTERVAL_MINUTES", 5.0)
            return timedelta(minutes=default_min), default_min

        diffs = timestamps.diff().dropna()
        if len(diffs) == 0:
            default_min = getattr(settings, "PREDICTION_DEFAULT_INTERVAL_MINUTES", 5.0)
            return timedelta(minutes=default_min), default_min

        # Compute median delta to be resilient against network dropouts/gaps
        median_seconds = diffs.dt.total_seconds().median()
        if median_seconds <= 0 or np.isnan(median_seconds):
            default_min = getattr(settings, "PREDICTION_DEFAULT_INTERVAL_MINUTES", 5.0)
            return timedelta(minutes=default_min), default_min

        interval_delta = timedelta(seconds=float(median_seconds))
        interval_minutes = float(median_seconds) / 60.0
        return interval_delta, interval_minutes

    def _holt_linear_forecast_series(
        self, series: np.ndarray, h: int, alpha: float, beta: float
    ) -> np.ndarray:
        """
        Applies Holt's Linear Trend method on a 1D NumPy array and produces h-step ahead forecasts.
        
        Equations:
            level_t = alpha * y_t + (1 - alpha) * (level_{t-1} + trend_{t-1})
            trend_t = beta * (level_t - level_{t-1}) + (1 - beta) * trend_{t-1}
            forecast_{t+k} = level_t + k * trend_t
        """
        n = len(series)
        if n == 0:
            return np.zeros(h)
        if n == 1:
            return np.full(h, series[0])

        # Initial level and trend estimation
        # Level starts at first observation; initial trend estimated from first few points or simple difference
        level = series[0]
        init_points = min(n, 4)
        trend = (series[init_points - 1] - series[0]) / max(init_points - 1, 1)

        for t in range(1, n):
            val = series[t]
            prev_level = level
            prev_trend = trend
            level = alpha * val + (1.0 - alpha) * (prev_level + prev_trend)
            trend = beta * (level - prev_level) + (1.0 - beta) * prev_trend

        # Forecast h steps into future
        forecasts = np.array([level + (step + 1) * trend for step in range(h)])
        return forecasts

    def generate_forecast(
        self, records_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates short-term multi-step forecasts for all 5 continuous telemetry features.
        
        Args:
            records_list: Chronologically ordered list of dictionaries containing sensor readings.
            
        Returns:
            Dict containing:
                - status: 'success' or 'insufficient_data' or 'error'
                - horizon_steps: int
                - horizon_minutes: float (or None)
                - sampling_interval_seconds: float (or None)
                - forecast: list of dicts with forecasted feature values and projected timestamps
        """
        if not records_list or len(records_list) < self.min_history:
            logger.warning(
                f"Insufficient historical data for forecasting ({len(records_list) if records_list else 0} < {self.min_history}). Skipping forecast."
            )
            return {
                "status": "insufficient_data",
                "horizon_steps": 0,
                "horizon_minutes": None,
                "sampling_interval_seconds": None,
                "forecast": [],
            }

        try:
            df = pd.DataFrame.from_records(records_list)

            # Ensure all required features are present
            for f in self.features:
                if f not in df.columns:
                    raise ValueError(f"Required telemetry feature '{f}' missing from records.")

            # Clean and interpolate missing sensor readings
            feature_df = df[self.features].copy()
            feature_df.interpolate(method="linear", limit_direction="both", inplace=True)
            feature_df.ffill(inplace=True)
            feature_df.bfill(inplace=True)

            # If NaNs remain (e.g. all empty), fill with 0.0
            feature_df.fillna(0.0, inplace=True)

            # Determine empirical time interval and project timestamps
            interval_delta, interval_minutes = self._determine_sampling_interval(df)
            
            last_timestamp = None
            if "timestamp" in df.columns and pd.notna(df["timestamp"].iloc[-1]):
                try:
                    last_timestamp = pd.to_datetime(df["timestamp"].iloc[-1])
                except Exception:
                    last_timestamp = None

            if last_timestamp is None:
                last_timestamp = datetime.now()

            # Forecast each feature using Holt's Linear Smoothing
            forecast_dict = {}
            for feature in self.features:
                series = feature_df[feature].to_numpy(dtype=float)
                forecast_dict[feature] = self._holt_linear_forecast_series(
                    series=series,
                    h=self.horizon_steps,
                    alpha=self.alpha,
                    beta=self.beta,
                )

            # Assemble structured forecast points
            forecast_points = []
            for step in range(self.horizon_steps):
                step_timestamp = last_timestamp + (interval_delta * (step + 1))
                point = {
                    "step": step + 1,
                    "timestamp": step_timestamp.isoformat(),
                }
                for feature in self.features:
                    val = float(forecast_dict[feature][step])
                    # Voltage and temperature lower physical bounds sanity check
                    if feature == "voltage" and val < 0:
                        val = 0.0
                    point[feature] = round(val, 4)
                forecast_points.append(point)

            total_horizon_minutes = (
                round(interval_minutes * self.horizon_steps, 2)
                if interval_minutes is not None
                else None
            )

            return {
                "status": "success",
                "horizon_steps": self.horizon_steps,
                "horizon_minutes": total_horizon_minutes,
                "sampling_interval_seconds": (
                    interval_delta.total_seconds() if interval_delta else None
                ),
                "forecast": forecast_points,
            }

        except Exception as e:
            logger.error(f"Error during sensor forecasting: {e}", exc_info=True)
            return {
                "status": "error",
                "error_message": str(e),
                "horizon_steps": 0,
                "horizon_minutes": None,
                "sampling_interval_seconds": None,
                "forecast": [],
            }
