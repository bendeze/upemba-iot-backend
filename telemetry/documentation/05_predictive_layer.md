# Short-Term Predictive Anomaly Detection Documentation

## 1. Overview
The short-term predictive layer extends Upemba's real-time Isolation Forest anomaly detector by forecasting multi-step sensor trajectories (Holt's Linear Trend method) and evaluating those projected points against the learned Isolation Forest baseline.

## 2. Service Architecture
File: `backend/telemetry/services/prediction_service.py`

### Mechanism:
1. **Historical Slicing**: Fetches up to `PREDICTION_HISTORY_WINDOW` (default: 40) recent sensor readings.
2. **Missing Data Handling**: Interpolates missing sensor packets linearly and applies forward/backward fills.
3. **Sampling Interval Estimation**: Calculates empirical median $\Delta t$ between consecutive observations.
4. **Holt's Linear Forecasting**: Computes local level $\ell_t$ and trend momentum $b_t$ for each feature independently:
   - $\ell_t = \alpha y_t + (1 - \alpha)(\ell_{t-1} + b_{t-1})$
   - $b_t = \beta(\ell_t - \ell_{t-1}) + (1 - \beta)b_{t-1}$
   - $\hat{y}_{t+h} = \ell_t + h \cdot b_t$
5. **Coupled Evaluation**: Forecasted points are standardized using the baseline historical `StandardScaler` and passed to `IsolationForest.decision_function()` and `predict()`.
6. **Persistence**: Saves `predicted_status`, `predictive_anomaly_score`, `prediction_horizon_steps`, `prediction_horizon_minutes`, and `forecasted_values` in `HealthStatus`.

## 3. Configuration Settings
* `PREDICTION_HISTORY_WINDOW`: Number of historical points to fetch (default: 40)
* `PREDICTION_MIN_HISTORY`: Minimum observations required before forecasting (default: 10)
* `PREDICTION_HORIZON_STEPS`: Number of future steps to forecast (default: 6)
* `PREDICTION_HOLT_ALPHA`: Level smoothing coefficient (default: 0.3)
* `PREDICTION_HOLT_BETA`: Trend smoothing coefficient (default: 0.1)

## 4. Evaluation Command
Run walk-forward validation:
```bash
python manage.py evaluate_prediction --sample-limit 1000
```
