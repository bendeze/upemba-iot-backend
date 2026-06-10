# Upemba Predictive Maintenance IoT System

Welcome to the Upemba IoT project! This repository contains the complete stack (Hardware, Backend, Frontend, and Machine Learning) for an intelligent Predictive Maintenance system designed for the Upemba environment.

By utilizing ESP32 microcontrollers, a Raspberry Pi Edge Gateway, and an Unsupervised Machine Learning pipeline, this system predicts hardware failures *before* they happen.

---

## 📚 Project Documentation Library

To make navigating this complex system easy, we have divided the documentation into specific, highly-detailed guides. Please refer to the document that matches your current task:

### ⚙️ System & Server Deployment
* [MQTT & Deployment Setup Guide](MQTT_SETUP_GUIDE.md) - **Start Here.** Covers what MQTT is, how to set up the Mosquitto Broker, and how to run the Django servers on your Raspberry Pi using `tmux`.

### 🧠 Machine Learning
* [Machine Learning Architecture Guide](ML_ARCHITECTURE_GUIDE.md) - Explains how our Isolation Forest model works, why it's unsupervised, and how the rolling 40-record data pipeline functions.

### 🔧 Hardware & Field Operations
* [Hardware & Wiring Guide](HARDWARE_WIRING_GUIDE.md) - For field technicians. Covers ESP32 GPIO pinouts, MPU6050 I2C wiring, and power requirements.
* [Alerting & Maintenance SOP](ALERTING_AND_MAINTENANCE_SOP.md) - Standard Operating Procedures explaining exactly what humans must do when the system sends a RED/CRITICAL email alert.

### 💻 Software Development
* [API Documentation](API_DOCUMENTATION.md) - For frontend developers. Lists all REST API endpoints, JSON response formats, and filtering queries.

---

## System Architecture Summary

1. **Sensor Node (ESP32):** Reads raw vibration/temperature data and publishes JSON to Mosquitto via MQTT.
2. **Edge Gateway (Raspberry Pi):**
   * **Mosquitto:** Receives the MQTT data.
   * **Django MQTT Listener:** Subscribes to Mosquitto and saves raw data to SQLite.
   * **Django Q Worker (ML):** Wakes up every minute, runs the Isolation Forest algorithm on the recent data, and saves a Health Status (Normal/Warning/Critical).
   * **Django Web Server:** Serves the data via REST API.
3. **Frontend (Next.js):** Fetches the API data and visualizes it using beautiful, responsive Tailwind/Recharts dashboards.
