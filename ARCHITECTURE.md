# System Architecture & Technical Flowcharts: Upemba IoT

This document provides the complete collection of formal system architecture diagrams, sequence diagrams, entity-relationship models, and decision flowcharts for the **Upemba IoT Predictive Maintenance System**. All diagrams are structured in vertical layout (`TD` / top-to-bottom) for optimal rendering in academic reports, technical documentation, and book publications.

---

## Figure 1 — High-Level System Architecture

```mermaid
flowchart TD
    subgraph L1 ["1. Physical / Field Layer"]
        SOLAR["Solar Inverter Systems"]
        PUMP["Water Pumps & Electric Motors"]
        SERVER["Off-Grid Server Infrastructure"]
    end

    subgraph L2 ["2. IoT Sensing Layer (ESP32)"]
        SENS["MPU-6050 Accelerometer & Gyroscope\nVoltage Transducers & Temperature Probes"]
        ESP["ESP32-WROOM-32 Microcontroller\n(Dual Core LX6, 240MHz, 802.11 b/g/n)"]
        SENS -->|I2C: GPIO 21/22 & ADC| ESP
    end

    SOLAR -. Physical Vibration & Heat .-> SENS
    PUMP -. Physical Vibration & Heat .-> SENS
    SERVER -. Thermal & Voltage Drift .-> SENS

    subgraph L3 ["3. Network & Transport Layer"]
        WIFI["Local Wi-Fi Access Point (192.168.1.0/24)"]
        MQTT_PUB["MQTT Publisher Client (TCP Port 1883)"]
        ESP --> WIFI --> MQTT_PUB
    end

    subgraph L4 ["4. Edge Gateway Layer (Raspberry Pi 4B)"]
        MOSQ["Mosquitto MQTT Broker\nTopic: `upemba/sensors/+/telemetry`"]
        LISTENER["Django MQTT Ingestion Daemon\n`python manage.py mqtt_listener`"]
        Q_WORKER["Django Q2 Asynchronous Worker\n`python manage.py qcluster`"]
        DAPHNE["Daphne ASGI Web & WebSocket Server\n(HTTP/1.1 & WSS on Port 8000)"]
        
        MQTT_PUB --> MOSQ
        MOSQ --> LISTENER
    end

    subgraph L5 ["5. Data & Analytics Layer"]
        DB[(SQLite 3 Database: `db.sqlite3`)]
        CHAN["InMemoryChannelLayer (Channels)"]
        ML_ISO["Layer 1: Isolation Forest (scikit-learn)"]
        ML_HOLT["Layer 2: Holt's Linear Trend Forecaster"]
        ALERT_SVC["Alert Service (SMTP Dispatcher)"]

        LISTENER -->|Persist SensorReading| DB
        LISTENER -->|Broadcast `telemetry_reading`| CHAN
        Q_WORKER -->|Read Rolling W=40 Readings| DB
        Q_WORKER --> ML_ISO
        Q_WORKER --> ML_HOLT
        ML_ISO & ML_HOLT -->|Persist HealthStatus| DB
        Q_WORKER -->|Critical Anomaly Detected| ALERT_SVC
        Q_WORKER -->|Broadcast `health_update`| CHAN
    end

    subgraph L6 ["6. Presentation Layer (Client Terminals)"]
        NEXT["Next.js 16 SPA (React 19 / TypeScript)\nTanStack Query + Tailwind CSS + Recharts"]
        UI_3D["3D Isometric Chassis Deflection Engine"]
        UI_PRED["Predictive Trend & Horizon Visualizer"]
        
        DAPHNE <-->|REST API JSON| NEXT
        CHAN -->|WebSocket Push Events| NEXT
        NEXT --> UI_3D
        NEXT --> UI_PRED
    end

    subgraph L7 ["7. Human / Operational Layer"]
        RANGERS["Park Rangers (Field Operations)"]
        TECHS["Field Technicians & Engineers"]
        
        ALERT_SVC -->|SMTP Email Alert (Port 25/587)| TECHS
        NEXT -. Interactive Diagnostics & Logs .-> RANGERS
        NEXT -. Preventive Intervention Schedule .-> TECHS
    end
```

<div align="center">

### **Figure 1. High-Level Architecture of the Upemba IoT Predictive Maintenance System**

</div>

---

## Figure 2 — Physical and IoT Sensing Architecture

```mermaid
flowchart TD
    subgraph PhysicalMachinery ["Monitored Industrial Asset"]
        HOUSING["Equipment Housing / Inverter Casing"]
        POWER_RAIL["DC/AC Power Terminals"]
    end

    subgraph Transducers ["Sensor Transducer Modules"]
        MPU["MPU-6050 Sensor Board\n- Micro-Electro-Mechanical (MEMS) 3-Axis Accel\n- 3-Axis Gyroscope\n- Internal Temperature Sensor"]
        VOLT_MOD["Voltage Divider Transducer\n(0-25V DC Input -> 0-3.3V Output)"]
    end

    HOUSING ===|Rigid Mechanical Coupling / Epoxy| MPU
    POWER_RAIL ===|Galvanic / Resistor Isolation| VOLT_MOD

    subgraph MicrocontrollerUnit ["ESP32-WROOM-32 Microcontroller Node"]
        PIN_I2C["I2C Hardware Controller\nGPIO 21 (SDA) | GPIO 22 (SCL)\n3.3V Logic Level, 400 kHz Fast-Mode"]
        PIN_ADC["12-bit SAR ADC Controller\nAnalog Input: GPIO 34"]
        CPU["Dual-Core 32-bit Xtensa LX6 CPU\nClock Frequency: 240 MHz"]
        BUFFER["In-Memory JSON Serialization Buffer"]
        WIFI_RADIO["802.11 b/g/n Wi-Fi Transceiver"]

        MPU -->|I2C Bus Protocol| PIN_I2C
        VOLT_MOD -->|Analog Voltage Level| PIN_ADC
        PIN_I2C --> CPU
        PIN_ADC --> CPU
        CPU --> BUFFER
        BUFFER --> CPU
        CPU --> WIFI_RADIO
    end

    subgraph PowerSource ["Power Management"]
        PWR_OPT1["5V Micro-USB / USB-C Direct"]
        PWR_OPT2["5V DC-DC Buck Converter from Solar Battery"]
        REG["On-board 3.3V Low-Dropout (LDO) Regulator"]
        
        PWR_OPT1 --> REG
        PWR_OPT2 --> REG
        REG --> MicrocontrollerUnit
    end

    WIFI_RADIO -->|MQTT Publish: `upemba/sensors/<device_id>/telemetry`| GATEWAY["Raspberry Pi Edge Gateway"]
```

<div align="center">

### **Figure 2. Physical Sensing and IoT Device Architecture**

</div>

---

## Figure 3 — Edge Gateway Architecture

```mermaid
flowchart TD
    subgraph HardwareHost ["Raspberry Pi 4 Model B (4GB LPDDR4, ARM Cortex-A72 @ 1.5GHz)"]
        
        subgraph BrokerProcess ["1. Message Broker (Daemon Service)"]
            MOSQUITTO["Eclipse Mosquitto MQTT Broker\n- TCP Port: 1883 (Listening on 0.0.0.0)\n- Protocol: MQTT v3.1.1 / v5.0\n- QoS: 0 (Low Latency / Edge Tuned)"]
        end

        subgraph TmuxSession ["2. Process Orchestration (Tmux Session: 'upemba')"]
            
            subgraph Pane0 ["Pane 0: Application & WebSocket Server"]
                DAPHNE_SRV["Daphne ASGI Web Server\n`python manage.py runserver 0.0.0.0:8000`\n- HTTP/1.1 REST API\n- Django Channels WebSockets"]
            end

            subgraph Pane1 ["Pane 1: Telemetry Ingestion Daemon"]
                MQTT_LISTENER["MQTT Ingestion Command\n`python manage.py mqtt_listener`\n- Paho-MQTT Client Listener\n- Non-blocking Ingestion Loop"]
            end

            subgraph Pane2 ["Pane 2: Background Task Worker"]
                QCLUSTER["Django Q2 Worker Cluster\n`python manage.py qcluster`\n- Scheduled Periodic Task Runner\n- Dual-Layer ML Inference Worker"]
            end
        end

        subgraph LocalStorage ["3. Embedded Persistence & IPC"]
            SQLITE_DB[(SQLite 3 Database: `db.sqlite3`\n- SensorReading\n- HealthStatus\n- Equipment\n- MaintenanceLog\n- User)]
            CHANNEL_LAYER["InMemoryChannelLayer\n- Real-Time WebSocket Group IPC"]
        end

        subgraph LocalMailRelay ["4. Alert Dispatch"]
            SMTP_RELAY["Local / Uplink SMTP Relay Service\n(Port 25 / 587)"]
        end
    end

    MOSQUITTO -->|Deliver MQTT Messages| MQTT_LISTENER
    MQTT_LISTENER -->|ORM Insert: SensorReading| SQLITE_DB
    MQTT_LISTENER -->|Broadcast: `telemetry_reading`| CHANNEL_LAYER

    QCLUSTER -->|Query W=40 Readings| SQLITE_DB
    QCLUSTER -->|ORM Insert: HealthStatus| SQLITE_DB
    QCLUSTER -->|Trigger Email on Critical| SMTP_RELAY
    QCLUSTER -->|Broadcast: `health_update`| CHANNEL_LAYER

    DAPHNE_SRV <-->|Read / Write State| SQLITE_DB
    DAPHNE_SRV <-->|Subscribe & Stream Events| CHANNEL_LAYER
```

<div align="center">

### **Figure 3. Raspberry Pi Edge Gateway Architecture**

</div>

---

## Figure 4 — MQTT-Based Telemetry Communication Architecture

```mermaid
flowchart TD
    subgraph Publishers ["MQTT Publishers (Field Sensor Nodes)"]
        NODE1["ESP32 Node 1\n`device_id: EQUIP-INV-001`\nTopic: `upemba/sensors/EQUIP-INV-001/telemetry`"]
        NODE2["ESP32 Node 2\n`device_id: EQUIP-MOT-002`\nTopic: `upemba/sensors/EQUIP-MOT-002/telemetry`"]
        NODEN["ESP32 Node N\n`device_id: EQUIP-SRV-003`\nTopic: `upemba/sensors/EQUIP-SRV-003/telemetry`"]
    end

    subgraph BrokerCore ["Mosquitto MQTT Broker (TCP Port 1883)"]
        TOPIC_ROUTER{"Topic Namespace Router\nMatches against wildcard subscriptions"}
    end

    NODE1 -->|Publish Payload (QoS 0)| TOPIC_ROUTER
    NODE2 -->|Publish Payload (QoS 0)| TOPIC_ROUTER
    NODEN -->|Publish Payload (QoS 0)| TOPIC_ROUTER

    subgraph SubscriberBackend ["MQTT Subscriber (Django Ingestion Engine)"]
        SUB_CLIENT["Paho-MQTT v2 Client (`django_mqtt_listener`)"]
        SUB_TOPIC["Subscription: `upemba/sensors/+/telemetry`\n('+ ' Single-Level Wildcard matches all device IDs)"]
        CALLBACK["`on_message(client, userdata, msg)` Callback Handler"]
        
        SUB_CLIENT --> SUB_TOPIC
        SUB_TOPIC --> CALLBACK
    end

    TOPIC_ROUTER -->|Forward Matching Packets| SUB_CLIENT

    subgraph IngestionPipeline ["Data Ingestion Actions"]
        DECODE["Decode UTF-8 Byte Stream"]
        PARSE_JSON["Parse JSON Structure"]
        VALIDATE["Validate Required Keys:\n[device_id, temp, volt, vib.x, vib.y, vib.z]"]
        GET_OR_CREATE["Get or Auto-Provision `Equipment` in Registry"]
        INSERT_DB["INSERT into `telemetry_sensorreading`"]
        WS_FORWARD["Dispatch `telemetry_reading` to Django Channels"]

        CALLBACK --> DECODE --> PARSE_JSON --> VALIDATE --> GET_OR_CREATE --> INSERT_DB --> WS_FORWARD
    end
```

<div align="center">

### **Figure 4. MQTT-Based Telemetry Communication Architecture**

</div>

---

## Figure 5 — End-to-End Telemetry Data Flow

```mermaid
flowchart TD
    A["1. Physical Sensor Sampling\n(MPU-6050 Accelerometer & Voltage/Thermal Probes)"] --> B["2. Microcontroller Data Acquisition (ESP32)\n(I2C Fast-Mode & 12-bit ADC Reading)"]
    B --> C["3. JSON Payload Serialization\n(`{ device_id, data: { temp, volt, vib: {x,y,z} } }`)"]
    C --> D["4. MQTT Message Publication\n(Topic: `upemba/sensors/<device_id>/telemetry` via TCP:1883)"]
    D --> E["5. Mosquitto Broker Ingestion & Distribution\n(Forwarded to Wildcard Subscriber `upemba/sensors/+/telemetry`)"]
    E --> F["6. Backend Ingestion & Schema Validation\n(`mqtt_listener.py`: Null check, type enforcement)"]
    F --> G["7. Relational Persistence in SQLite Database\n(Created row in `telemetry_sensorreading` with timestamp index)"]
    
    G --> H["8. Real-Time WebSocket Streaming\n(Broadcast via `InMemoryChannelLayer` to `global_telemetry` group)"]
    H --> I["9. Instant Live Dashboard Update\n(Next.js TanStack Query optimistic cache mutation & 3D mesh rendering)"]
    
    G --> J["10. Scheduled Machine Learning Pipeline (~60s Task)\n(`evaluate_equipment_health_task` queries rolling W=40 window)"]
    J --> K["11. Data Preprocessing & Scaling\n(Linear interpolation + forward/backward fill + StandardScaler)"]
    K --> L["12. Layer 1: Real-Time Anomaly Detection\n(Isolation Forest computes current score & binary anomaly flag)"]
    K --> M["13. Layer 2: Short-Term Predictive Forecasting\n(Holt's Linear Trend extrapolates H=6 future multi-feature vectors)"]
    L & M --> N["14. Health Assessment & Horizon Evaluation\n(Evaluates projected points against fitted IF model; derives worst score)"]
    N --> O["15. Persistence of Health Status & Performance Metrics\n(Saved to `telemetry_healthstatus` with CPU/RAM/latency profiling)"]
    
    O --> P["16. WebSocket Broadcast of Health & Alert Updates\n(Pushed to Next.js clients for status badges and predictive curves)"]
    
    O --> Q{"17. Anomaly Score < -0.15\n(CRITICAL Fault)?"}
    Q -- Yes --> R["18. Automated SMTP Email Alert Dispatch\n(`AlertService` sends rich HTML email to Technicians & Admins)"]
    Q -- No --> S["19. Normal Continuous Monitoring Continues"]
    R --> T["20. Physical SOP Inspection & Maintenance Intervention"]
```

<div align="center">

### **Figure 5. End-to-End Telemetry Data Flow from Sensor Acquisition to Dashboard Visualization**

</div>

---

## Figure 6 — Backend Software Architecture

```mermaid
flowchart TD
    subgraph ConfigLayer ["Master Django Configuration (`config`)"]
        SETTINGS["`settings.py` (Environ injection, Q_CLUSTER, SimpleJWT, Database)"]
        MASTER_URLS["`urls.py` (Route Dispatcher)"]
        API_ROUTER["`api_router.py` (DRF DefaultRouter / SimpleRouter)"]
        ASGI_APP["`asgi.py` (ProtocolTypeRouter: HTTP + WebSockets)"]
    end

    subgraph UsersDomain ["`users` Application Domain"]
        USER_MOD["Model: `User` (AbstractUser + Role: ADMIN / TECHNICIAN / RANGER)"]
        USER_VIEWS["Views: `UserViewSet`, `RegisterView`, `ActivateUserView`, `ResendOTPView`"]
        USER_SERIAL["Serializers: `UserSerializer`, `RegisterSerializer`"]
    end

    subgraph InventoryDomain ["`inventory` Application Domain"]
        EQ_MOD["Model: `Equipment` (UUID PK, Name, Type, MAC Address, Active Flag)"]
        LOG_MOD["Model: `MaintenanceLog` (Equipment FK, Author FK, Description, Action)"]
        INV_VIEWS["Views: `EquipmentViewSet`, `MaintenanceLogViewSet`"]
        INV_SERIAL["Serializers: `EquipmentSerializer`, `MaintenanceLogSerializer`"]
    end

    subgraph TelemetryDomain ["`telemetry` Application Domain"]
        READ_MOD["Model: `SensorReading` (Equipment FK, Temp, Volt, Vib X/Y/Z, Timestamp)"]
        HEALTH_MOD["Model: `HealthStatus` (Current & Predictive Scores, Horizon JSON, Latency, CPU/RAM)"]
        TEL_VIEWS["Views: `HealthStatusViewSet`, `SensorReadingViewSet`"]
        TEL_SERIAL["Serializers: `HealthStatusSerializer`, `SensorReadingSerializer`"]
        WS_CONSUMER["Consumer: `TelemetryConsumer` (AsyncJsonWebsocketConsumer)"]
        
        subgraph TelemetryServices ["Domain Services & Workers"]
            TASK_EVAL["Task: `evaluate_equipment_health_task()`"]
            CMD_MQTT["Command: `mqtt_listener.py`"]
            SVC_ML["Service: `AnomalyDetector` (Isolation Forest)"]
            SVC_PRED["Service: `SensorForecaster` (Holt's Linear Trend)"]
            SVC_ALERT["Service: `AlertService` (SMTP Dispatcher)"]
        end
    end

    ASGI_APP --> MASTER_URLS
    ASGI_APP --> WS_CONSUMER
    MASTER_URLS --> API_ROUTER
    
    API_ROUTER --> USER_VIEWS
    API_ROUTER --> INV_VIEWS
    API_ROUTER --> TEL_VIEWS

    USER_VIEWS --> USER_SERIAL --> USER_MOD
    INV_VIEWS --> INV_SERIAL --> EQ_MOD & LOG_MOD
    TEL_VIEWS --> TEL_SERIAL --> READ_MOD & HEALTH_MOD

    CMD_MQTT --> EQ_MOD & READ_MOD
    TASK_EVAL --> READ_MOD & HEALTH_MOD
    TASK_EVAL --> SVC_ML & SVC_PRED & SVC_ALERT
```

<div align="center">

### **Figure 6. Backend Software Architecture of the IoT Monitoring Platform**

</div>

---

## Figure 7 — REST API Communication Architecture

```mermaid
flowchart TD
    subgraph ClientBrowser ["Next.js Frontend Client (Port 3000)"]
        USER_UI["User Interface Components\n(Dashboard, Predictions, Logs, Equipment, Settings)"]
        QUERY_CACHE["TanStack React Query Cache Layer\n(Keyed Queries: `equipment`, `sensor-readings`, `health-status`)"]
        AXIOS_CLIENT["Axios HTTP Client (`src/lib/api/`)"]
        AUTH_STORE["JWT Cookie Storage (`js-cookie`)"]

        USER_UI <--> QUERY_CACHE
        QUERY_CACHE <--> AXIOS_CLIENT
        AUTH_STORE -->|Inject `Authorization: Bearer <token>`| AXIOS_CLIENT
    end

    subgraph APIRoutes ["Django REST Framework API Gateway (Port 8000)"]
        
        subgraph AuthEndpoints ["Authentication & Account Endpoints"]
            EP_TOKEN["`POST /api/token/` (Obtain Access & Refresh JWT)"]
            EP_REFRESH["`POST /api/token/refresh/` (Rotate Access Token)"]
            EP_REG["`POST /api/register/` (Create User Account)"]
            EP_ACT["`POST /api/activate/` (Verify Email OTP)"]
            EP_RESEND["`POST /api/resend-otp/` (Generate Fresh OTP)"]
            EP_ME["`GET / PATCH /api/users/me/` (Profile Management)"]
            EP_PW["`POST /api/users/change-password/` (Password Update)"]
        end

        subgraph CoreDomainEndpoints ["Domain Resource Endpoints"]
            EP_EQUIP["`GET / POST /api/equipment/` (Equipment Registry & Search)"]
            EP_READINGS["`GET /api/sensor-readings/` (Filtered Telemetry Time-Series)"]
            EP_HEALTH["`GET /api/health-status/` (Current Health & Predictive Horizon)"]
            EP_LOGS["`GET / POST /api/maintenance-logs/` (Maintenance Logbook)"]
        end

        subgraph DocsEndpoints ["Documentation Endpoints"]
            EP_SCHEMA["`GET /api/schema/` (OpenAPI 3.0 YAML/JSON)"]
            EP_SWAGGER["`GET /api/docs/` (Interactive Swagger UI)"]
        end
    end

    subgraph DatabaseLayer ["Relational Persistence"]
        DB[(SQLite 3 Database: `db.sqlite3`)]
    end

    AXIOS_CLIENT ===|HTTP Request + JWT| AuthEndpoints
    AXIOS_CLIENT ===|HTTP Request + JWT| CoreDomainEndpoints
    AXIOS_CLIENT ===|HTTP Request| DocsEndpoints

    AuthEndpoints <--> DatabaseLayer
    CoreDomainEndpoints <--> DatabaseLayer
```

<div align="center">

### **Figure 7. REST API Communication Architecture**

</div>

---

## Figure 8 — Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    User ||--o{ MaintenanceLog : "authors"
    Equipment ||--o{ SensorReading : "generates"
    Equipment ||--o{ HealthStatus : "evaluated_for"
    Equipment ||--o{ MaintenanceLog : "associated_with"

    User {
        bigint id PK "Auto Increment"
        string username UK "Unique login handle"
        string email "Email address for alerts"
        string password "Hashed credentials"
        string role "ADMIN | TECHNICIAN | RANGER"
        string name "Full operator name"
        boolean is_active "Account status flag"
        datetime date_joined "Registration timestamp"
    }

    Equipment {
        uuid id PK "UUID4 primary key"
        string name "Human readable label"
        string equipment_type "INVERTER | MOTOR | SERVER"
        string mac_address UK "Hardware identifier / MAC"
        text location_notes "Physical deployment details"
        boolean is_active "Operational active flag"
        datetime created_at "Registration timestamp"
        datetime updated_at "Modification timestamp"
    }

    SensorReading {
        bigint id PK "Auto Increment"
        uuid equipment_id FK "References Equipment(id)"
        float temperature "Sensor reading in deg C"
        float voltage "Sensor reading in Vrms"
        float vib_x "Vibration X-axis in G"
        float vib_y "Vibration Y-axis in G"
        float vib_z "Vibration Z-axis in G"
        datetime timestamp "Indexed auto_now_add"
    }

    HealthStatus {
        bigint id PK "Auto Increment"
        uuid equipment_id FK "References Equipment(id)"
        float anomaly_score "Isolation Forest score at t=0"
        string status "NORMAL | WARNING | CRITICAL"
        datetime prediction_timestamp "Indexed auto_now_add"
        string predicted_status "Worst predicted status"
        float predictive_anomaly_score "Worst predicted score"
        int prediction_horizon_steps "Default: 6 steps"
        float prediction_horizon_minutes "Empirical duration"
        json forecasted_values "Array of projected points"
        datetime prediction_generated_at "Generation timestamp"
        float processing_latency_ms "Evaluation latency in ms"
        float cpu_load_percent "CPU load percentage"
        float ram_allocation_mb "RAM memory footprint in MB"
    }

    MaintenanceLog {
        bigint id PK "Auto Increment"
        uuid equipment_id FK "References Equipment(id)"
        bigint author_id FK "References User(id), Nullable"
        text description "Observed physical issue"
        text action_taken "Corrective maintenance steps"
        datetime timestamp "Indexed auto_now_add"
    }
```

<div align="center">

### **Figure 8. Entity-Relationship Model of the IoT Telemetry Database**

</div>

---

## Figure 9 — Machine Learning Pipeline

```mermaid
flowchart TD
    subgraph IngestionWindow ["1. Ingestion & Historical Windowing"]
        QUERY["Query last W=40 chronological records from `SensorReading`"]
        CHECK_LEN{"Dataset >= 10 points?"}
        QUERY --> CHECK_LEN
        CHECK_LEN -- No --> SKIP["Skip Evaluation (Insufficient baseline)"]
    end

    subgraph DataPrep ["2. Preprocessing & Standardization"]
        EXTRACT["Extract 5 Continuous Features:\n[temperature, voltage, vib_x, vib_y, vib_z]"]
        INTERP["Linear Interpolation (`df.interpolate(method='linear')`)\nHandles sensor dropouts"]
        FILL["Forward & Backward Fill (`df.ffill()`, `df.bfill()`)"]
        SCALER["StandardScaler Normalization ($z = \frac{x - \mu}{\sigma}$)\nZero-mean & unit-variance scaling"]

        CHECK_LEN -- Yes --> EXTRACT --> INTERP --> FILL --> SCALER
    end

    subgraph Layer1Pipeline ["3. Layer 1: Real-Time Anomaly Detection"]
        FIT_IF["Fit Isolation Forest on Scaled Window\n`IsolationForest(n_estimators=15, contamination=0.05)`"]
        PRED_NOW["Evaluate Present Reading ($t=0$)\n`decision_function(latest_reading)`"]
        SCORE_NOW["Compute Real-Time Decision Score $S_{t=0}$\nand Boolean `is_anomaly` Flag"]

        SCALER --> FIT_IF --> PRED_NOW --> SCORE_NOW
    end

    subgraph Layer2Pipeline ["4. Layer 2: Short-Term Predictive Forecasting"]
        HOLT_FIT["Holt's Linear Exponential Smoothing Model\n$\ell_t = \alpha y_t + (1-\alpha)(\ell_{t-1} + b_{t-1})$\n$b_t = \beta(\ell_t - \ell_{t-1}) + (1-\beta)b_{t-1}$"]
        PROJ_STEPS["Extrapolate $H=6$ Forward Steps\n$\hat{y}_{t+k} = \ell_t + k \cdot b_t$"]
        EMPIRICAL_DT["Calculate Empirical Sampling Interval ($\Delta t$)\n$\Delta t = \text{median}(\text{timestamp}_i - \text{timestamp}_{i-1})$\n$\text{Horizon (Minutes)} = H \times \Delta t_{\text{min}}$"]
        SCALE_FUT["Transform Projected Vectors using Baseline Scaler\n`scaler.transform(forecast_df)`"]
        EVAL_FUT["Evaluate Horizon Points against Fitted Isolation Forest\n`model.decision_function(scaled_points)`"]
        SIGMOID_CALIB["Calibrate Probabilities via Sigmoid:\n$P(\text{anomaly}) = \frac{1}{1 + e^{15 \cdot S}}$\n$\text{Confidence} = 100 \times (1 - P)$"]

        FILL --> HOLT_FIT --> PROJ_STEPS --> SCALE_FUT
        FILL --> EMPIRICAL_DT
        FIT_IF -. Fitted Model .-> EVAL_FUT
        SCALER -. Fitted Scaler .-> SCALE_FUT
        SCALE_FUT --> EVAL_FUT --> SIGMOID_CALIB
    end

    subgraph SynthesisLayer ["5. Classification & Database Persistence"]
        CLASSIFY["Synthesize Health Classes:\n- Score < -0.15 -> CRITICAL\n- Score < 0.0 -> WARNING\n- Score >= 0.0 -> NORMAL"]
        PROFILE["Capture System Metrics via `psutil`:\n- Latency (ms)\n- CPU Load (%)\n- RAM Allocation (MB)"]
        PERSIST_DB["INSERT into `telemetry_healthstatus`"]

        SCORE_NOW --> CLASSIFY
        EVAL_FUT --> CLASSIFY
        SIGMOID_CALIB --> PERSIST_DB
        EMPIRICAL_DT --> PERSIST_DB
        CLASSIFY --> PERSIST_DB
        PROFILE --> PERSIST_DB
    end
```

<div align="center">

### **Figure 9. Machine Learning Pipeline for Predictive Maintenance**

</div>

---

## Figure 10 — Predictive Maintenance Decision-Making Flow

```mermaid
flowchart TD
    START(["Start Scheduled Health Evaluation"]) --> FETCH_EQ["Retrieve Active Equipment Nodes"]
    FETCH_EQ --> LOOP_START["For Each Equipment Node"]
    
    LOOP_START --> FETCH_DATA["Query Last 40 Sensor Readings"]
    FETCH_DATA --> CHECK_COUNT{"Readings >= 10?"}
    
    CHECK_COUNT -- No --> LOG_SKIP["Log Warning: Insufficient Baseline Data"] --> NEXT_NODE["Move to Next Equipment"]
    
    CHECK_COUNT -- Yes --> PREPROC["Clean, Interpolate & Standardize Features"]
    PREPROC --> FIT_ML["Fit Isolation Forest & Predict Present Score $S_{t=0}$"]
    PREPROC --> RUN_FORECAST["Run Holt's Forecaster ($H=6$ Steps Ahead)"]
    
    FIT_ML & RUN_FORECAST --> EVAL_FUTURE["Evaluate Forecast Horizon against Fitted Model"]
    
    EVAL_FUTURE --> CHECK_CURRENT_CRIT{"$S_{t=0} < -0.15$?"}
    CHECK_CURRENT_CRIT -- Yes --> SET_CURR_CRIT["Status = CRITICAL\nTrigger Immediate Email Alert"]
    CHECK_CURRENT_CRIT -- No --> CHECK_CURRENT_WARN{"$S_{t=0} < 0.0$ OR\nis_anomaly == True?"}
    CHECK_CURRENT_WARN -- Yes --> SET_CURR_WARN["Status = WARNING"]
    CHECK_CURRENT_WARN -- No --> SET_CURR_NORM["Status = NORMAL"]

    SET_CURR_CRIT --> CHECK_PRED_CRIT{"Worst Forecast Score < -0.15?"}
    SET_CURR_WARN --> CHECK_PRED_CRIT
    SET_CURR_NORM --> CHECK_PRED_CRIT

    CHECK_PRED_CRIT -- Yes --> SET_PRED_CRIT["Predicted Status = CRITICAL"]
    CHECK_PRED_CRIT -- No --> CHECK_PRED_WARN{"Worst Forecast Score < 0.0?"}
    CHECK_PRED_WARN -- Yes --> SET_PRED_WARN["Predicted Status = WARNING"]
    CHECK_PRED_WARN -- No --> SET_PRED_NORM["Predicted Status = NORMAL"]

    SET_PRED_CRIT --> SAVE_HEALTH["Create `HealthStatus` Record in SQLite Database"]
    SET_PRED_WARN --> SAVE_HEALTH
    SET_PRED_NORM --> SAVE_HEALTH

    SAVE_HEALTH --> WS_PUSH["Broadcast `health_update` via Channels WebSockets"]
    WS_PUSH --> NEXT_NODE
    NEXT_NODE --> LOOP_START
```

<div align="center">

### **Figure 10. Predictive Maintenance Decision-Making Flow**

</div>

---

## Figure 11 — Alert Generation and Maintenance Response Workflow

```mermaid
flowchart TD
    subgraph TriggerLayer ["1. Trigger Condition"]
        EVAL_TASK["Django Q2 Health Task"]
        CRIT_FLAG{"Anomaly Score < -0.15\n(CRITICAL Alert)?"}
        EVAL_TASK --> CRIT_FLAG
    end

    subgraph NotificationDispatch ["2. Alert Notification Dispatch"]
        ALERT_SERVICE["`AlertService.trigger_critical_alert()`"]
        QUERY_RECIPIENTS["Query Active Users with Role in [ADMIN, TECHNICIAN] and valid Email"]
        HTML_TEMPLATE["Render `telemetry/email/critical_alert.html`\nwith Equipment Name, Timestamp, Anomaly Score"]
        SEND_EMAIL["Dispatch via Django `send_mail()` (SMTP Relay)"]
        WS_ALERT["Broadcast `alert_notification` via Django Channels"]

        CRIT_FLAG -- Yes --> ALERT_SERVICE
        ALERT_SERVICE --> QUERY_RECIPIENTS
        QUERY_RECIPIENTS --> HTML_TEMPLATE
        HTML_TEMPLATE --> SEND_EMAIL
        CRIT_FLAG -- Yes --> WS_ALERT
    end

    subgraph SOPResponse ["3. Standard Operating Procedure (SOP)"]
        RECEIVE_ALERT["Field Technician receives Email & Visual UI Warning Banner"]
        VERIFY_DASH["Step 1: Open Upemba Dashboard\nInspect Live Vibration Spectrum & 3D Isometric Deflection"]
        DISPATCH_RANGER["Step 2: Dispatch Field Ranger to Physical Site"]
        INSPECT_HARDWARE["Step 3: Check MPU-6050 Bolting & Cabling\n(Ensure sensor has not loosened or detached)"]
        INSPECT_MACHINE["Step 4: Inspect Physical Machinery\n(Check Inverter Fans, Motor Bearings, Thermal Overheating)"]
        PERFORM_REPAIR["Step 5: Perform Corrective Maintenance\n(Tighten Mounts / Clear Debris / Replace Failed Unit)"]
        RECORD_LOG["Step 6: Submit Maintenance Log entry via Web Dashboard"]
        AUTO_HEAL["Step 7: Automated Recovery\nSystem ingests 40 healthy readings and resets to NORMAL within ~3 minutes"]

        SEND_EMAIL --> RECEIVE_ALERT
        WS_ALERT --> RECEIVE_ALERT
        RECEIVE_ALERT --> VERIFY_DASH
        VERIFY_DASH --> DISPATCH_RANGER
        DISPATCH_RANGER --> INSPECT_HARDWARE
        INSPECT_HARDWARE --> INSPECT_MACHINE
        INSPECT_MACHINE --> PERFORM_REPAIR
        PERFORM_REPAIR --> RECORD_LOG
        RECORD_LOG --> AUTO_HEAL
    end
```

<div align="center">

### **Figure 11. IoT Alert Generation and Maintenance Response Workflow**

</div>

---

## Figure 12 — Real-Time Telemetry Processing Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Sensor as MPU-6050 & Transducers
    actor ESP as ESP32 Sensor Node
    actor Broker as Mosquitto MQTT Broker (1883)
    actor Listener as Django MQTT Listener
    actor DB as SQLite Database
    actor Worker as Django Q2 Worker
    actor Channels as Django Channels (ASGI)
    actor Dashboard as Next.js Dashboard
    actor Tech as Field Technician

    Note over Sensor,Dashboard: Step A: Telemetry Sampling & Real-Time Ingestion (Every ~30s)
    Sensor->>ESP: Read Accelerometer (X,Y,Z), Voltage, Temperature
    ESP->>Broker: MQTT PUBLISH `upemba/sensors/EQUIP-INV-001/telemetry` (QoS 0)
    Broker->>Listener: On-Message Callback (JSON Payload)
    Listener->>DB: INSERT `SensorReading` row
    Listener->>Channels: group_send('global_telemetry', 'telemetry_reading')
    Channels-->>Dashboard: WebSocket Push: Update Live Charts & 3D Canvas

    Note over Worker,Tech: Step B: Asynchronous Analytics & Predictive Forecasting (Every ~60s)
    Worker->>DB: SELECT last 40 `SensorReading` records
    Worker->>Worker: Preprocess & Normalize Features
    Worker->>Worker: Layer 1: Isolation Forest Anomaly Scoring
    Worker->>Worker: Layer 2: Holt's Linear Trend Extrapolation (H=6)
    Worker->>DB: INSERT `HealthStatus` assessment
    Worker->>Channels: group_send('global_telemetry', 'health_update')
    Channels-->>Dashboard: WebSocket Push: Update Health Status & Forecast Horizon

    opt Critical State Triggered (Score < -0.15)
        Worker->>Worker: Render `critical_alert.html` template
        Worker->>Tech: Dispatch SMTP Email Alert
        Worker->>Channels: group_send('global_telemetry', 'alert_notification')
        Channels-->>Dashboard: WebSocket Push: Display Critical Alert Banner
    end
```

<div align="center">

### **Figure 12. Sequence Diagram of Real-Time IoT Telemetry Processing**

</div>

---

## Figure 13 — Dashboard Data Retrieval Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Field Operator / Ranger
    participant Browser as Web Browser
    participant App as Next.js Single Page App
    participant Cache as TanStack React Query Cache
    participant Auth as JWT Storage (`js-cookie`)
    participant API as Django REST API (`/api/`)
    participant DB as SQLite Database

    Operator->>Browser: Access `/dashboard/predictions`
    Browser->>App: Mount Predictions Page Component
    App->>Cache: Check Cache for `health-status`
    
    alt Cache Miss / Stale Data (>30s)
        App->>Auth: Retrieve JWT `access_token`
        App->>API: GET `/api/health-status/?equipment=EQUIP-INV-001` (Bearer Token)
        API->>DB: Query `telemetry_healthstatus` (ORDER BY -prediction_timestamp)
        DB-->>API: Return Records & Forecast JSON
        API-->>App: 200 OK (Paginated JSON Response)
        App->>Cache: Populate Cache with New Data
    else Cache Hit (<30s)
        Cache-->>App: Return Cached Records
    end

    App->>App: Calculate Multi-Step Forecast Curves & Probabilities
    App-->>Browser: Render Recharts Trend Lines & 3D Trajectory Mesh
    Browser-->>Operator: Display Visual Prediction Diagnostics
```

<div align="center">

### **Figure 13. Sequence Diagram for Dashboard Telemetry Retrieval**

</div>

---

## Figure 14 — Deployment Architecture

```mermaid
flowchart TD
    subgraph SiteInstallation ["1. Field Installation (Monitored Apparatus)"]
        subgraph NodeBox ["Sensor Node Enclosure (NEMA IP65)"]
            ESP_DEV["ESP32-WROOM-32 Development Board"]
            MPU_DEV["MPU-6050 Sensor Board (Epoxied to Casing)"]
            PWR_SUPPLY["5V DC-DC Buck Converter / USB Power Bank"]
            
            PWR_SUPPLY --> ESP_DEV
            MPU_DEV -->|I2C 3.3V| ESP_DEV
        end
    end

    subgraph EdgeControlRoom ["2. Edge Site Gateway (Solar Station Control Room)"]
        WIFI_ROUTER["Local Wi-Fi Router / Access Point\nSubnet: `192.168.1.0/24`\nSSID: `Upemba-IoT-Net`"]
        
        subgraph GatewayBox ["Raspberry Pi 4B Gateway Station (`192.168.1.76`)"]
            MOSQ_DAEMON["Mosquitto MQTT Broker (Port 1883)"]
            DAPHNE_DAEMON["Daphne ASGI Web Server (Port 8000)"]
            Q_DAEMON["Django Q2 Worker Cluster (2 Processes)"]
            SQLITE_FILE["SQLite 3 Database File (`db.sqlite3`)"]
            LOCAL_SMTP["Postfix Local Mail Relay (Port 25)"]

            DAPHNE_DAEMON <--> SQLITE_FILE
            Q_DAEMON <--> SQLITE_FILE
            Q_DAEMON --> LOCAL_SMTP
        end

        WIFI_ROUTER <--> MOSQ_DAEMON
        WIFI_ROUTER <--> DAPHNE_DAEMON
    end

    ESP_DEV -->|802.11 b/g/n Wi-Fi| WIFI_ROUTER

    subgraph OperatorTerminals ["3. Client Terminals (Laptops / Tablets)"]
        CLIENT_DEVICE["Field Operator Terminal (`192.168.1.50 - 99`)\n- Web Browser (Chromium / Firefox / Safari)\n- Next.js Single Page Application (Port 3000)"]
        
        CLIENT_DEVICE <-->|Wi-Fi Connection| WIFI_ROUTER
    end
```

<div align="center">

### **Figure 14. Deployment Architecture of the Upemba IoT System**

</div>

---

## Figure 15 — Network and Communication Architecture

```mermaid
flowchart TD
    subgraph NetworkSegment ["Local Area Network Boundary (192.168.1.0/24)"]
        
        subgraph NodeSubnet ["Sensor Node IP Range (`192.168.1.100 - 150`)"]
            ESP_NODES["ESP32 Microcontrollers\n- Static / DHCP IP Allocation\n- Port: Outbound TCP"]
        end

        subgraph GatewaySubnet ["Edge Gateway Node (`192.168.1.76`)"]
            GATEWAY_HOST["Raspberry Pi 4B\n- MQTT Ingestion Port: 1883\n- HTTP/REST API Port: 8000\n- WebSocket (WSS/WS) Port: 8000\n- SMTP Relay Port: 25 / 587"]
        end

        subgraph ClientSubnet ["Operator Terminal Range (`192.168.1.50 - 99`)"]
            CLIENT_HOSTS["Field Tablets, Laptops, Mobile Terminals\n- Outbound HTTP to Port 8000\n- Outbound WS to Port 8000\n- Next.js Web Server Port 3000"]
        end
    end

    ESP_NODES ===|MQTT over TCP (Port 1883)| GATEWAY_HOST
    CLIENT_HOSTS ===|HTTP/1.1 REST API (Port 8000)| GATEWAY_HOST
    CLIENT_HOSTS ===|Full-Duplex WebSocket (Port 8000)| GATEWAY_HOST
    GATEWAY_HOST ===|SMTP Email Notifications (Port 25/587)| CLIENT_HOSTS
```

<div align="center">

### **Figure 15. Network Communication Architecture of the IoT Infrastructure**

</div>

---

## Figure 16 — Security Architecture

```mermaid
flowchart TD
    subgraph PerimeterSec ["1. Perimeter & Network Isolation"]
        AIR_GAP["Isolated Physical LAN / Local Subnet (Zero Cloud Dependency)"]
        CORS_FILTER["Django CORS Middleware (`CORS_ALLOWED_ORIGINS` Validation)"]
        HOST_FILTER["Django `ALLOWED_HOSTS` Restriction"]
    end

    subgraph IngestionSec ["2. Telemetry Ingestion Security"]
        TOPIC_VAL["Strict Topic Hierarchy Enforcement (`upemba/sensors/+/telemetry`)"]
        PAYLOAD_VAL["JSON Schema Validation & Missing-Key Rejection"]
        BOUND_CHECK["Sensor Value Boundary Clamping (Reject Impossible Voltages/Temps)"]
    end

    subgraph AuthSec ["3. Authentication & Access Control"]
        JWT_AUTH["SimpleJWT Bearer Token Authentication (60-minute Expiry)"]
        REFRESH_ROT["Refresh Token Rotation & Automatic Blacklisting"]
        RBAC_MODEL["Role-Based Access Control (`ADMIN`, `TECHNICIAN`, `RANGER`)"]
        EMAIL_OTP["Cryptographic 4-Byte Hex Email OTP Account Activation"]
        PW_HASH["Argon2 / PBKDF2 Password Cryptographic Hashing"]
    end

    subgraph PersistenceSec ["4. Data & Configuration Protection"]
        ENV_SECRETS["Environment Variable Isolation in `.env.local`"]
        PARAM_SQL["Parameterized ORM Queries (SQL Injection Immunity)"]
        READ_ONLY_API["Read-Only ViewSets on Telemetry & Health Endpoints"]
    end

    AIR_GAP --> CORS_FILTER --> HOST_FILTER
    HOST_FILTER --> TOPIC_VAL --> PAYLOAD_VAL --> BOUND_CHECK
    BOUND_CHECK --> JWT_AUTH --> REFRESH_ROT --> RBAC_MODEL
    RBAC_MODEL --> EMAIL_OTP --> PW_HASH
    PW_HASH --> ENV_SECRETS --> PARAM_SQL --> READ_ONLY_API
```

<div align="center">

### **Figure 16. Security Architecture of the IoT Predictive Maintenance Platform**

</div>

---

## Figure 17 — Fault Detection, Handling, and Recovery Flow

```mermaid
flowchart TD
    START_MONITOR(["Continuous Fault Detection Active"]) --> DETECT{"Identify Fault Event"}

    DETECT -- "Wi-Fi Packet Dropout / Incomplete Stream" --> FAULT_1["Fault 1: Missing Sensor Reading"]
    DETECT -- "Corrupted / Non-JSON MQTT Byte Stream" --> FAULT_2["Fault 2: Malformed Payload"]
    DETECT -- "Sensor Detachment / Loose MPU-6050" --> FAULT_3["Fault 3: Physical Transducer Error"]
    DETECT -- "Database Empty / Insufficient Records (<10)" --> FAULT_4["Fault 4: Insufficient Baseline"]
    DETECT -- "SMTP Server Unreachable / Mail Down" --> FAULT_5["Fault 5: Email Dispatch Failure"]
    DETECT -- "Client Browser Disconnects from WebSocket" --> FAULT_6["Fault 6: WebSocket Link Drop"]

    FAULT_1 --> REC_1["Pandas Linear Interpolation + Forward/Backward Fill Imputation in ML Engine"]
    FAULT_2 --> REC_2["`json.JSONDecodeError` Caught Gracefully in Exception Block; Listener Continues Running"]
    FAULT_3 --> REC_3["Isolation Forest Flags Anomaly; Technician SOP Identifies Detached Sensor Module"]
    FAULT_4 --> REC_4["ML Evaluation Skips Gracefully with Informational Log until 10 Readings Accumulate"]
    FAULT_5 --> REC_5["SMTP Exception Caught; Dev OTP/Alert Output to Console; Background Task Survives"]
    FAULT_6 --> REC_6["Frontend Exponential Backoff Auto-Reconnect Loop (1s, 2s, 4s, max 10s)"]

    REC_1 --> RECOVERED(["System Remains Healthy & Operational"])
    REC_2 --> RECOVERED
    REC_3 --> RECOVERED
    REC_4 --> RECOVERED
    REC_5 --> RECOVERED
    REC_6 --> RECOVERED
```

<div align="center">

### **Figure 17. Fault Detection, Handling, and Recovery Flow**

</div>

---

## Figure 18 — System Operational Lifecycle

```mermaid
stateDiagram-v2
    [*] --> NodeBoot: Power Applied to Hardware
    
    state NodeBoot {
        [*] --> HardwareInit: Initialize I2C Bus & ADC GPIO
        HardwareInit --> Wi-FiConnect: Connect to Local Wi-Fi AP
        Wi-FiConnect --> BrokerConnect: Connect to Mosquitto Port 1883
    }

    NodeBoot --> IngestionActive: Broker Handshake Success

    state IngestionActive {
        [*] --> SampleSensors: Read MPU-6050 & Transducers
        SampleSensors --> BuildJSON: Format Telemetry Payload
        BuildJSON --> MQTTPublish: Publish QoS 0 Message
        MQTTPublish --> SleepCycle: Sleep 30 Seconds
        SleepCycle --> SampleSensors
    }

    state EdgeProcessing {
        [*] --> IngestPacket: Listener Receives Packet
        IngestPacket --> StoreDatabase: Save SensorReading Row
        StoreDatabase --> PushWebSocket: Broadcast to UI Clients
        PushWebSocket --> ScheduledTask: 60s Periodic Task Fires
        
        state ScheduledTask {
            [*] --> FitIsolationForest: Train on Last 40 Points
            FitIsolationForest --> HoltForecasting: Project +6 Horizon Steps
            HoltForecasting --> AssessHealthState: Classify Health Status
        }
    }

    IngestionActive --> EdgeProcessing: Telemetry Arrives

    state HealthClassification {
        AssessHealthState --> NormalState: Anomaly Score >= 0.0
        AssessHealthState --> WarningState: Anomaly Score in [-0.15, 0.0)
        AssessHealthState --> CriticalState: Anomaly Score < -0.15
    }

    state OperationalResponse {
        CriticalState --> SendSMTPAlert: Trigger Critical Email
        SendSMTPAlert --> DispatchTech: Dispatch Field Technician
        DispatchTech --> PerformInspection: Check Machinery & Sensor Bolting
        PerformInspection --> MechanicalRepair: Execute Fix
        MechanicalRepair --> BaselineHealing: Machinery Restored to Normal
    }

    BaselineHealing --> NormalState: 40 Clean Readings Ingested
```

<div align="center">

### **Figure 18. Operational Lifecycle of the IoT Predictive Maintenance System**

</div>
