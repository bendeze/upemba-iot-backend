# Upemba IoT: Machine Learning Architecture Guide

This document provides a highly detailed explanation of the Machine Learning (ML) engine powering the Upemba Predictive Maintenance System. It covers what algorithm we use, why we chose it, and exactly how it processes raw sensor data to predict equipment failures.

---

## 1. What Algorithm Are We Using?

We are using an algorithm called **Isolation Forest** (provided by the `scikit-learn` Python library).

### How does Isolation Forest work?
Most Machine Learning algorithms try to build a profile of what "Normal" looks like. Isolation Forest takes a completely different approach: it tries to isolate anomalies instead of profiling normal points.

Imagine a forest of decision trees. The algorithm randomly picks a sensor feature (like temperature) and randomly splits the data. 
- **Normal data points** are clustered tightly together, so it takes *many* random splits to isolate a normal point.
- **Anomalies** are weird and far away from the rest of the data. Because they are so different, it only takes a *few* random splits to isolate an anomaly.

If a data point is isolated very quickly (short path length in the tree), the algorithm flags it as an anomaly.

---

## 2. Why Did We Choose Isolation Forest?

We specifically chose Isolation Forest for this IoT project for three major reasons:

1. **It is "Unsupervised":** We do not have thousands of historical records labeled "Broken" or "Healthy". Unsupervised learning means the algorithm doesn't need labeled data. It just looks at the raw data flowing in and figures out the patterns on its own.
2. **It handles Multidimensional Data:** A simple rule like "Alert if Temp > 50°C" is easy. But what if Temp is 45°C (normal) AND Voltage drops slightly (normal) AND Vibration Z is slightly high (normal)? Individually, they are fine, but *together* they indicate a failing bearing. Isolation Forest looks at all 5 dimensions (Temp, Volt, VibX, VibY, VibZ) simultaneously.
3. **It is Extremely Fast:** IoT data flows rapidly. Isolation Forest has very low memory requirements and executes in fractions of a second, making it perfect for running on a Raspberry Pi.

---

## 3. How Are We Using It? (The Pipeline)

The ML pipeline is located in `backend/telemetry/services/ml_service.py` and is triggered by a background worker in `backend/telemetry/tasks.py`. Here is the exact step-by-step process of how data turns into a prediction.

### Step 3.1: The Data Threshold (The Rolling Window)
Machine Learning cannot make a prediction on a single data point in a vacuum. It needs context. 
Every 1 minute, the Django background worker wakes up and fetches exactly the **last 40 sensor readings** for a specific piece of equipment. If there are fewer than 40 readings, the model aborts and waits for more data.

### Step 3.2: Data Preprocessing (Pandas)
Raw IoT data is messy. Before the model sees it, we use the `pandas` library to clean it up:
1. **Interpolation:** If the Wi-Fi drops and a reading is missing, `pandas` draws a straight mathematical line between the reading before the dropout and the reading after to fill in the blank (`df.interpolate()`).
2. **Standardization:** Temperature is measured in tens (e.g., 30.5°C), while Vibration is measured in fractions (e.g., 0.05G). If we feed this directly into the model, it will think Temperature is 600x more important than Vibration simply because the numbers are bigger. We use `StandardScaler` to squash all values into a uniform mathematical scale (around 0) so every sensor is treated equally.

### Step 3.3: Dynamic Training
Unlike traditional ML models that are trained once in a lab and deployed, our model is **dynamically trained on the fly**. 
Every time the worker runs, it creates a brand new Isolation Forest and trains it strictly on those 40 recent records (`model.fit(df_scaled)`). This means the model learns the *current* operational baseline of the equipment. If the baseline shifts slowly over a year (e.g., summer vs. winter), the model adapts automatically!

### Step 3.4: Prediction & Scoring
Once the model learns the baseline from the 40 records, we isolate the **very last (newest)** record and ask the model to judge it.

The model outputs two things:
1. **Prediction:** `1` (Normal) or `-1` (Anomaly).
2. **Anomaly Score:** A raw mathematical number. Positive numbers mean the data is buried deep inside the "normal" cluster. Negative numbers mean the data was isolated quickly (it's an anomaly). The more negative the number, the worse the anomaly is.

### Step 3.5: Translating to Human Statuses
Finally, the Python code translates the mathematical score into the colors you see on the dashboard:
* **Score < -0.15:** `CRITICAL` (Red LED). Something is severely broken. This immediately triggers the `AlertService` to send an emergency email to the Park Rangers.
* **Score < 0.0:** `WARNING` (Yellow LED). The machine is behaving unusually. Maintenance should be scheduled.
* **Score > 0.0:** `NORMAL` (Green LED). The machine is running perfectly.

The status is saved to the PostgreSQL/SQLite database, and the Next.js frontend fetches it via the API to update the UI.
