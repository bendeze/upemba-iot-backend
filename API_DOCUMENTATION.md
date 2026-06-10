# Upemba IoT: API Documentation

This document outlines the REST API endpoints provided by the Django Backend. This API is consumed by the Next.js frontend to render the dashboards.

**Base URL:** `http://<RASPBERRY_PI_IP>:8000/api/`

---

## 1. Authentication
* **Endpoint:** `POST /api/token/`
* **Description:** Obtain a JWT Access and Refresh token.
* **Payload:** `{"username": "admin", "password": "yourpassword"}`
* **Usage:** Pass the resulting access token in the `Authorization: Bearer <token>` header for all subsequent requests.

---

## 2. Equipment Endpoint
* **Endpoint:** `GET /api/equipment/`
* **Description:** Retrieves a list of all registered sensor nodes and machinery.
* **Query Parameters:** None
* **Sample Response:**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Sensor Node EQUIP-INV-001",
      "mac_address": "EQUIP-INV-001",
      "equipment_type": "INVERTER",
      "is_active": true
    }
  ]
}
```

---

## 3. Health Status Endpoint
* **Endpoint:** `GET /api/health-status/`
* **Description:** Retrieves the Machine Learning health predictions. Ordered newest first.
* **Query Parameters (Filtering):**
  * `equipment`: Filter by equipment ID (e.g., `?equipment=1`)
  * `start_date`: Filter by ISO timestamp (e.g., `?start_date=2026-06-10T12:00:00Z`)
  * `end_date`: Filter by ISO timestamp
* **Sample Response:**
```json
{
  "count": 1,
  "results": [
    {
      "id": 15,
      "equipment": 1,
      "anomaly_score": 0.0452,
      "status": "NORMAL",
      "prediction_timestamp": "2026-06-10T14:30:00Z"
    }
  ]
}
```

---

## 4. Sensor Reading Endpoint
* **Endpoint:** `GET /api/sensor-readings/`
* **Description:** Retrieves the raw historical data points sent by the ESP32.
* **Query Parameters:** Supports the same filtering as Health Status (`equipment`, `start_date`, `end_date`).
* **Sample Response:**
```json
{
  "count": 40,
  "results": [
    {
      "id": 102,
      "equipment": 1,
      "temperature": 32.5,
      "voltage": 24.1,
      "vib_x": 0.05,
      "vib_y": -0.01,
      "vib_z": 0.98,
      "timestamp": "2026-06-10T14:29:55Z"
    }
  ]
}
```

## Pagination
All endpoints use DRF `PageNumberPagination`. If `count` exceeds the `PAGE_SIZE` (default 50), use the URL provided in the `next` field to fetch the next page.
