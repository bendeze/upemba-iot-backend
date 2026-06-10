# Upemba IoT: MQTT & Deployment Setup Guide

This guide provides a comprehensive overview of how MQTT is used in the Upemba IoT project, and step-by-step instructions for deploying and running the entire system using the Raspberry Pi as an Edge Gateway and the ESP32 as a sensor node.

---

## 1. What is MQTT?

**MQTT (Message Queuing Telemetry Transport)** is a lightweight, publish-subscribe network protocol designed specifically for Internet of Things (IoT) devices. It is perfect for low-bandwidth, high-latency, or unreliable networks.

Instead of devices talking directly to each other, MQTT relies on a central hub called a **Broker**. 
* **Publishers** send messages to the Broker on a specific "Topic".
* **Subscribers** tell the Broker they want to listen to a specific "Topic".
* When the Broker receives a message, it immediately forwards it to all interested Subscribers.

---

## 2. How We Are Using MQTT in Upemba IoT

In this project, the architecture works as follows:

1. **The Broker (Mosquitto on Raspberry Pi):** Acts as the central post office. It listens on port `1883`.
2. **The Publisher (ESP32):** Reads temperature, voltage, and vibration data. It packages this into a JSON payload and publishes it to the topic:
   `upemba/sensors/<DEVICE_ID>/telemetry`
3. **The Subscriber (Django Backend on Raspberry Pi):** A Python script (`mqtt_listener`) runs continuously in the background. It subscribes to the wildcard topic `upemba/sensors/+/telemetry` (the `+` means it listens to *all* devices). When a message arrives, it parses the JSON and saves it into the SQLite database so the frontend can display it on the charts.

---

## 3. Raspberry Pi Setup & Execution (Using Tmux)

The Raspberry Pi is the brain of the operation. It must run the Mosquitto Broker, the Django Web Server (API), and the Django MQTT Listener simultaneously. 

We will use **Tmux** (Terminal Multiplexer) to run these background processes easily. Tmux allows you to have multiple terminal "windows" inside a single SSH session that keep running even if you close your laptop.

### Step 3.1: Network & Broker Setup
1. Find your Raspberry Pi's IP address using `hostname -I`.
2. Ensure Mosquitto allows external connections:
   ```bash
   sudo nano /etc/mosquitto/conf.d/local.conf
   ```
   Add these lines:
   ```text
   listener 1883 0.0.0.0
   allow_anonymous true
   ```
3. Restart Mosquitto: `sudo systemctl restart mosquitto`

### Step 3.2: Starting the Tmux Session
Log into your Raspberry Pi via SSH and start a new tmux session named `upemba`:
```bash
tmux new -s upemba
```

### Step 3.3: Running the Backend Services
Once inside tmux, you will start your services in different panes.

**Pane 1: Django Web Server**
Navigate to your backend directory and start the server:
```bash
cd ~/iot-project/upemba-iot-project/backend
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

**Pane 2: MQTT Listener**
Split your tmux screen horizontally by pressing `Ctrl+B`, then `"` (shift + quote).
In this new bottom pane, start the listener:
```bash
cd ~/iot-project/upemba-iot-project/backend
source .venv/bin/activate
python manage.py mqtt_listener
```

**How to use Tmux:**
* To **switch** between the top and bottom panes: Press `Ctrl+B`, then the `Up` or `Down` arrow key.
* To **detach** (leave the programs running in the background and return to normal SSH): Press `Ctrl+B`, then `D`.
* To **re-attach** later (after logging back into the Pi): Run `tmux attach -t upemba`.

---

## 4. ESP32 Configuration & Flashing

The ESP32 is your remote sensor node. It needs to know exactly where the Raspberry Pi is located on the network.

### Step 4.1: Update `config.h`
In your ESP32 code, update the network settings to match your local Wi-Fi and point to the Raspberry Pi's IP address (the one you found in Step 3.1).

```cpp
#ifndef CONFIG_H
#define CONFIG_H

// Local Wi-Fi Network
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// Point this to the Raspberry Pi's IP address!
const char* MQTT_BROKER = "192.168.1.76"; 
const int   MQTT_PORT   = 1883;

// Equipment Identifier
const char* DEVICE_ID   = "EQUIP-INV-001"; 
const char* BASE_TOPIC  = "upemba/sensors/EQUIP-INV-001/telemetry";

const long REPORT_INTERVAL = 5000; // 5 seconds

#endif
```

### Step 4.2: Flash the ESP32
1. Connect the ESP32 to your computer via USB.
2. Compile and upload the code using PlatformIO or Arduino IDE.
3. Open the Serial Monitor (115200 baud rate).
4. You should see it connect to Wi-Fi, then print: `[MQTT] Data published successfully.`

If you re-attach to your Raspberry Pi tmux session (`tmux attach -t upemba`), you will see the `mqtt_listener` pane lighting up with `Saved reading for EQUIP-INV-001...` every 5 seconds!
