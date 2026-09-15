# Predictive Maintenance Firmware Architecture

## 1. Scope and Audit Result

This document describes the architecture implemented by the current repository as audited on 2026-08-26.

The repository contains firmware for one ESP32 edge node. It acquires temperature, AC voltage, and three-axis vibration readings, prints a local preview over Serial, and publishes JSON telemetry over MQTT. The MQTT broker and all downstream predictive-maintenance services are external to this repository.

The current firmware does **not** implement the following downstream functions:

- MQTT broker operation
- telemetry persistence or database storage
- dashboard presentation
- anomaly detection or machine-learning inference
- alert generation
- device authentication or encrypted MQTT transport
- automated unit tests

The project builds successfully with PlatformIO for the `esp32dev` target.

## 2. Repository Structure

```text
platformio.ini       PlatformIO target, framework, monitor speed, dependencies
include/config.h     Network, broker, device identity, topic, and timing constants
include/sensors.h    SensorData contract and sensor API
src/main.cpp         ESP32 lifecycle, connectivity, telemetry serialization, publishing
src/sensors.cpp      Sensor initialization and sensor acquisition/conversion
test/                PlatformIO test location; no project tests are currently present
lib/                 PlatformIO private-library location; no project library is present
```

## 3. System Context

**Figure 1. System context and external data-consumer boundary.**

```mermaid
flowchart LR
    Machine["Monitored machine"] --> T["Temperature sensor\nDallasTemperature / OneWire"]
    Machine --> V["AC voltage measurement\nEmonLib"]
    Machine --> A["3-axis vibration sensor\nADXL335-style analog outputs"]

    T --> ESP["ESP32 edge node\nArduino firmware"]
    V --> ESP
    A --> ESP

    ESP -->|"Wi-Fi / TCP"| NET["Local Wi-Fi network"]
    NET -->|"MQTT TCP\n192.168.1.68:1883"| BROKER["MQTT broker\nExternal Raspberry Pi or server"]
    BROKER --> CONSUMER["External MQTT consumer\nStorage / dashboard / analytics / alerts"]
    ESP -->|"115200 baud"| SERIAL["Serial monitor"]
```

### Boundary

The firmware owns sensor acquisition, unit conversion, device identity, JSON serialization, connectivity maintenance, and MQTT publication. The broker owns message routing. Any persistence, visualization, prediction, or alerting belongs to an external subscriber and is not represented as implemented code in this repository.

## 4. Hardware and Software Deployment

**Figure 2. Physical and software deployment architecture of the ESP32 edge node.**

```mermaid
flowchart TB
    subgraph NODE["ESP32 Dev Module / edge node"]
        FW["Arduino firmware\nmain.cpp + sensors.cpp"]
        TEMP["Temperature sensor\nOneWire data: GPIO 4"]
        VOLT["Voltage input\nEmonLib voltage: GPIO 35"]
        VIBX["Vibration X\nADC GPIO 32"]
        VIBY["Vibration Y\nADC GPIO 33"]
        VIBZ["Vibration Z\nADC GPIO 34"]
        FW --- TEMP
        FW --- VOLT
        FW --- VIBX
        FW --- VIBY
        FW --- VIBZ
    end

    NODE -->|"Wi-Fi"| WIFI["Wi-Fi access point"]
    WIFI -->|"LAN"| GATEWAY["MQTT broker\n192.168.1.68:1883"]
    GATEWAY -->|"Topic subscription"| SERVICES["External services"]
```

### Pin and conversion contract

| Signal | Implementation | Actual configuration |
|---|---|---|
| Temperature | `DallasTemperature` through `OneWire` | OneWire GPIO 4 |
| AC voltage | `EmonLib::EnergyMonitor` | GPIO 35, calibration `167.3`, phase shift `1.7` |
| Current input | Not used by the project | No current sensor is part of the active measurement or telemetry path |
| Vibration X | ESP32 ADC | GPIO 32; 12-bit ADC, 11 dB attenuation |
| Vibration Y | ESP32 ADC | GPIO 33; 12-bit ADC, 11 dB attenuation |
| Vibration Z | ESP32 ADC | GPIO 34; 12-bit ADC, 11 dB attenuation |

The vibration conversion assumes 3.3 V ADC reference behavior, a 12-bit midpoint of `2048`, and approximately `330 mV/g` sensitivity. The resulting values are labeled in the Serial output as G values. Although the source currently contains an `EmonLib` current-channel configuration on GPIO 36, the project does not use a current input: current is not represented in `SensorData`, is not part of the documented hardware interface, and is not published in MQTT telemetry.

## 5. Firmware Component Architecture

**Figure 3. Logical component architecture of the ESP32 telemetry firmware.**

```mermaid
flowchart TD
    MAIN["main.cpp"] --> WIFI["Wi-Fi connection manager<br/>connectToNetwork()"]
    MAIN --> MQTT["MQTT connection manager<br/>reconnectMQTT()"]
    MAIN --> TELEMETRY["Telemetry publisher<br/>sendTelemetry()"]
    TELEMETRY --> SENSOR_API["Sensor API<br/>collectData()"]
    SENSOR_API --> SENSOR_IMPL["sensors.cpp"]
    SENSOR_IMPL --> TEMP_LIB["DallasTemperature"]
    SENSOR_IMPL --> EMON_LIB["EmonLib"]
    SENSOR_IMPL --> ADC["Arduino ESP32 ADC API"]
    TELEMETRY --> JSON["ArduinoJson"]
    JSON --> PUB["PubSubClient.publish()"]
    PUB --> BROKER["External MQTT broker"]
    CONFIG["config.h"] --> MAIN
    CONFIG --> SENSOR_IMPL
    MAIN --> SERIAL["Serial output"]
```

## 6. Configuration and Runtime Parameters

| Parameter | Current value | Purpose |
|---|---|---|
| Wi-Fi SSID | `CANALBOX-F262-2G` | Network to join |
| MQTT broker | `192.168.1.68` | Broker address |
| MQTT port | `1883` | Unencrypted MQTT port |
| Device ID | `EQUIP-INV-001` | MQTT client and payload identity |
| Base topic | `upemba/sensors/EQUIP-INV-001/telemetry` | Telemetry publication topic |
| Report interval | `30000 ms` | Approximately 30-second publication interval |
| Serial monitor | `115200 baud` | Local diagnostic output |

The README currently says telemetry repeats every 5 seconds, but the implemented `REPORT_INTERVAL` is 30 seconds. This architecture document follows the code: the actual interval is 30 seconds.

## 7. Telemetry Data Contract

Each successful `sendTelemetry()` call creates a JSON document with this shape:

```json
{
  "device_id": "EQUIP-INV-001",
  "data": {
    "temp": 25.4,
    "volt": 230.1,
    "vib": {
      "x": 0.02,
      "y": -0.01,
      "z": 1.01
    }
  }
}
```

The values above are illustrative; the firmware publishes the current readings. There is no timestamp, sequence number, quality flag, firmware version, or explicit unit metadata in the payload. Units are implicit: temperature is Celsius, voltage is RMS volts, and vibration values are intended to represent G.

**Figure 4. Sensor-to-MQTT telemetry publication sequence.**

```mermaid
sequenceDiagram
    participant S as Sensors
    participant E as ESP32 firmware
    participant J as ArduinoJson document
    participant M as MQTT broker
    participant C as External consumer

    E->>S: collectData()
    S-->>E: temperature, voltage, vibX/Y/Z
    E->>J: Add device_id and data object
    J-->>E: Serialize JSON buffer
    E->>M: publish(BASE_TOPIC, payload)
    M-->>C: Route message to subscribers
    E-->>E: Print success or failure to Serial
```

## 8. Startup Flow

**Figure 5. ESP32 firmware startup and sensor-initialization flowchart.**

```mermaid
flowchart TD
    START(["Power on / reset"]) --> SERIAL["Serial.begin(115200)"]
    SERIAL --> WIFI["connectToNetwork()"]
    WIFI --> WIFIOK{"Wi-Fi connected?"}
    WIFIOK -->|No| WAITWIFI["Wait 500 ms and retry"]
    WAITWIFI --> WIFIOK
    WIFIOK -->|Yes| SERVER["client.setServer(MQTT_BROKER, MQTT_PORT)"]
    SERVER --> SENSORINIT["initSensors()"]
    SENSORINIT --> TEMPINIT["Start DallasTemperature"]
    TEMPINIT --> EMONINIT["Configure EmonLib voltage input"]
    EMONINIT --> ADCINIT["Set 12-bit ADC and 11 dB attenuation"]
    ADCINIT --> READY["Print initialization complete"]
    READY --> LOOP(["Enter loop()"])
```

Wi-Fi connection is blocking during startup: the device does not proceed to sensor initialization until Wi-Fi reports `WL_CONNECTED`.

## 9. Main Runtime Flow

**Figure 6. Main runtime loop and periodic telemetry scheduling flowchart.**

```mermaid
flowchart TD
    LOOP(["loop()"]) --> WIFIQ{"Wi-Fi connected?"}
    WIFIQ -->|No| WIFI["connectToNetwork()<br/>blocking retry loop"]
    WIFIQ -->|Yes| MQTTQ{"MQTT connected?"}
    WIFI --> MQTTQ
    MQTTQ -->|No| MQTT["reconnectMQTT()<br/>blocking retry every 5 s"]
    MQTTQ -->|Yes| CLIENTLOOP["client.loop()"]
    MQTT --> CLIENTLOOP
    CLIENTLOOP --> TIMER{"millis() - lastMillis > 30000?"}
    TIMER -->|No| LOOP
    TIMER -->|Yes| SEND["sendTelemetry()"]
    SEND --> LOOP
```

The first telemetry publication normally occurs only after the 30-second timer condition becomes true. The timer is not reset after reconnecting, and failed publishes are logged but not queued for retry.

## 10. Sensor Acquisition Flow

**Figure 7. Sequential sensor acquisition and signal-conversion flowchart.**

```mermaid
flowchart TD
    START(["collectData()"]) --> TEMPREQ["requestTemperatures()"]
    TEMPREQ --> TEMPREAD["getTempCByIndex(0)"]
    TEMPREAD --> VOLTREAD["EmonLib calcVI(20, 2000)"]
    VOLTREAD --> VRMS["Read emon1.Vrms"]
    VRMS --> X["analogRead(GPIO 32)"]
    X --> XCONV["Convert ADC midpoint and sensitivity to vibX"]
    XCONV --> Y["analogRead(GPIO 33)"]
    Y --> YCONV["Convert ADC midpoint and sensitivity to vibY"]
    YCONV --> Z["analogRead(GPIO 34)"]
    Z --> ZCONV["Convert ADC midpoint and sensitivity to vibZ"]
    ZCONV --> RETURN["Return SensorData"]
```

The sensor reads are sequential. The implemented measurement path uses temperature, voltage, and vibration only. The current input is not used by this project and does not appear in `SensorData` or the MQTT payload. `EmonLib` performs the voltage calculation internally for 20 half-cycles with a 2000 ms timeout parameter.

## 11. Connectivity and Failure Flow

**Figure 8. Wi-Fi and MQTT connectivity-maintenance and publication-failure flowchart.**

```mermaid
flowchart TD
    CHECK([Runtime connectivity check]) --> WIFI_STATUS{"Wi-Fi status"}
    WIFI_STATUS -->|Disconnected| WIFI_RETRY["WiFi.begin()\nretry every 500 ms until connected"]
    WIFI_STATUS -->|Connected| MQTT_STATUS{"MQTT client connected?"}
    WIFI_RETRY --> MQTT_STATUS
    MQTT_STATUS -->|Disconnected| MQTT_RETRY["client.connect(DEVICE_ID)"]
    MQTT_RETRY --> CONNECTED{"Connection succeeds?"}
    CONNECTED -->|No| MQTT_WAIT["Log state and wait 5 s"]
    MQTT_WAIT --> MQTT_RETRY
    CONNECTED -->|Yes| LOOPWORK["Continue to client.loop()"]
    MQTT_STATUS -->|Connected| LOOPWORK
    LOOPWORK --> PUBLISH["Periodic publish"]
    PUBLISH --> PUBLISHED{"publish() succeeds?"}
    PUBLISHED -->|Yes| SUCCESS["Log published successfully"]
    PUBLISHED -->|No| FAILURE["Log broker offline / publish failed"]
    SUCCESS --> NEXT([Return to loop])
    FAILURE --> NEXT
```

There is no local buffering, exponential backoff, watchdog recovery, or offline persistence. A failed publication is discarded. MQTT is configured on port 1883 without TLS or credentials in the current code.

## 12. Build and Dependency Architecture

**Figure 9. PlatformIO build and firmware dependency architecture.**

```mermaid
flowchart LR
    SRC["src/*.cpp"] --> PIO["PlatformIO"]
    INC["include/*.h"] --> PIO
    CFG["platformio.ini"] --> PIO
    PIO --> FW["ESP32 Arduino firmware"]
    PIO --> WIFI["WiFi"]
    PIO --> MQTT["PubSubClient 2.8"]
    PIO --> JSON["ArduinoJson 7.x"]
    PIO --> TEMP["DallasTemperature 4.0.6"]
    PIO --> ENERGY["EmonLib 1.1.0"]
    FW --> UPLOAD["USB / PlatformIO upload"]
    FW --> MONITOR["Serial monitor at 115200"]
```

## 13. Audit Findings and Recommended Next Steps

### Confirmed implementation facts

- Target is an ESP32 Dev Module using the Arduino framework.
- Telemetry is published to `upemba/sensors/EQUIP-INV-001/telemetry`.
- Publication is configured for approximately every 30 seconds.
- Wi-Fi and MQTT reconnection loops block the main loop until they succeed.
- MQTT uses client ID `EQUIP-INV-001` and no username/password.
- The broker address is a fixed private IPv4 address.
- The repository contains no backend, model, dashboard, persistence, or test implementation.

### Risks and gaps

1. Wi-Fi credentials are stored as plaintext in `include/config.h`; they should be moved to an untracked secrets file or build-time environment variables.
2. MQTT uses unauthenticated, unencrypted port 1883; production deployment needs broker authentication and TLS where practical.
3. There is no payload timestamp, making server-side ordering and time-series analysis dependent on broker receipt time.
4. Sensor errors are not validated. For example, a missing temperature sensor can produce an invalid reading, and ADC values are accepted without range or plausibility checks.
5. Failed MQTT publishes are discarded and there is no offline queue.
6. The README interval statement should be changed from 5 seconds to 30 seconds, or `REPORT_INTERVAL` should be changed if 5 seconds is the intended requirement.
7. `config.h` defines non-`static` global pointer variables in a header. This is currently safe for the single translation-unit usage pattern but should be changed to `constexpr` or `inline constexpr` configuration values as the project grows.
8. The current repository has no automated tests for conversion formulas, JSON shape, timing, reconnection, or sensor failure handling.

## 14. Suggested Production Extension

The intended end-to-end predictive-maintenance architecture would extend the external consumer boundary as follows:

**Figure 10. Proposed extension from MQTT ingestion to predictive-maintenance services.**

```mermaid
flowchart LR
    ESP["ESP32 edge node"] -->|"MQTT telemetry"| BROKER["MQTT broker"]
    BROKER --> INGEST["Ingestion service"]
    INGEST --> VALIDATE["Schema and quality validation"]
    VALIDATE --> DB["Time-series database"]
    DB --> FEATURES["Feature extraction"]
    FEATURES --> MODEL["Anomaly / predictive model"]
    MODEL --> ALERT["Alert and notification service"]
    DB --> DASH["Monitoring dashboard"]
    MODEL --> DASH
```

This extension is a target architecture, not a claim about functionality currently present in this repository.
