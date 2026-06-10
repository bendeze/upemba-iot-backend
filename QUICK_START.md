# Upemba IoT: Quick Start Guide

This is the cheat-sheet for starting the entire Upemba Predictive Maintenance system on the Raspberry Pi.

---

## The 1-Click Startup Script (Recommended)
We have created an automated script that creates the `tmux` session, splits the screen into 3 panels, activates the Python virtual environment, and runs all 3 services simultaneously.

1. SSH into your Raspberry Pi.
2. Navigate to your project folder:
   ```bash
   cd ~/iot-project/upemba-iot-project
   ```
3. Run the script:
   ```bash
   ./start_services.sh
   ```
*(To leave the services running in the background, press `Ctrl+B`, then `D`)*

---

## Manual Startup (Command Reference)

If you ever need to run them manually instead of using the script, run each of these in a separate terminal or tmux pane.

**1. The API Web Server (For the Frontend)**
```bash
cd ~/iot-project/upemba-iot-project/backend
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

**2. The MQTT Listener (Receives ESP32 Data)**
```bash
cd ~/iot-project/upemba-iot-project/backend
source .venv/bin/activate
python manage.py mqtt_listener
```

**3. The Machine Learning Worker (Generates Predictions)**
```bash
cd ~/iot-project/upemba-iot-project/backend
source .venv/bin/activate
python manage.py qcluster
```

---

## Helpful Commands

* **Find the Raspberry Pi IP Address:** `hostname -I`
* **Restart the Mosquitto Broker:** `sudo systemctl restart mosquitto`
* **View running tmux sessions:** `tmux ls`
* **Re-attach to background session:** `tmux attach -t upemba`
* **Kill the tmux session (Stops all services):** `tmux kill-session -t upemba`
