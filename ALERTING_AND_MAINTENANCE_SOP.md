# Upemba IoT: Alerting & Maintenance SOP
**(Standard Operating Procedure)**

This document is for Park Rangers, Technicians, and Administrators. It defines exactly what to do when the Predictive Maintenance Machine Learning model flags an anomaly.

---

## 1. Understanding the Alerts

The system has three tiers of health statuses:

### 🟢 NORMAL (Green)
* **What it means:** The ML model confirms the vibration and temperature signatures are identical to healthy historical baselines.
* **Action Required:** None.

### 🟡 WARNING (Yellow)
* **What it means:** The ML model detected a slight drift in data. For example, vibrations are slowly increasing over a week, but are not yet at dangerous levels.
* **Action Required:** 
  1. Open the dashboard and review the specific sensor charts.
  2. Schedule a routine visual inspection for the next available maintenance window (within 7 days).

### 🔴 CRITICAL (Red)
* **What it means:** The ML model detected a severe and sudden anomaly. This triggers an automated emergency email to all Technicians and Admins.
* **Action Required:** IMMEDIATE physical inspection. See procedure below.

---

## 2. Emergency Procedure for CRITICAL Alerts

If you receive an automated email stating: `CRITICAL ALERT: [Equipment Name] Failure Predicted`:

**Step 1: Verify on Dashboard**
* Log into the Upemba IoT web dashboard.
* Navigate to the Telemetry page and look at the raw data charts for that specific equipment.
* Check if the data looks like a sensor glitch (e.g., Temperature instantly spiked to 999°C) or a real mechanical issue (e.g., Vibration Z-axis oscillating wildly).

**Step 2: Physical Inspection**
Dispatch a technician to the physical location of the equipment. Check for:
* **Inverters:** Overheating, burning smell, loose mounting brackets, or fan failure.
* **Pumps/Motors:** Grinding noises, loose bearings, physical shaking, or fluid leaks.

**Step 3: Sensor Node Verification**
Sometimes the machinery is fine, but the sensor node itself is failing.
* Ensure the MPU6050 sensor is still firmly bolted to the machine. If it is hanging by its wires, it will record extreme vibrations and trigger false CRITICAL alerts.
* Ensure the ESP32 is protected from rain and wildlife.

**Step 4: Resolution & Reset**
* Once the physical issue is resolved (e.g., a bolt was tightened), monitor the dashboard.
* The ML model evaluates data dynamically. As soon as the machine begins running smoothly again, the system will automatically process the new 40 healthy readings and transition the status back to **NORMAL** within 3 minutes.
