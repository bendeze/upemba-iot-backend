# Upemba IoT: Hardware & Wiring Guide

This document outlines the hardware specifications and wiring diagrams for the ESP32 sensor nodes used in the Upemba IoT project. It is intended for field technicians installing or replacing hardware in the park.

## 1. Components List
* **Microcontroller:** ESP32 (WROOM-32 Development Board)
* **Vibration/Motion Sensor:** MPU6050 (6-axis Accelerometer & Gyroscope)
* **Temperature/Voltage:** (Depending on specific setup, either read via ADC pins or derived from MPU6050/external module)
* **Power Supply:** 5V USB Power Bank or 5V DC-DC Buck Converter tied to the solar inverter battery.

---

## 2. Wiring the MPU6050 to the ESP32

The MPU6050 uses the **I2C Protocol** to communicate with the ESP32. 

| MPU6050 Pin | ESP32 Pin | Description |
|---|---|---|
| **VCC** | **3V3** | Power (Do NOT use 5V unless your MPU6050 has a built-in voltage regulator!) |
| **GND** | **GND** | Ground |
| **SCL** | **GPIO 22** | I2C Clock Line |
| **SDA** | **GPIO 21** | I2C Data Line |
| INT | Not Connected | Interrupt pin (unused in current software) |

### Important Hardware Notes:
1. **Pull-up Resistors:** The ESP32 usually has internal pull-ups enabled for I2C, but if you experience `I2C connection failed` errors in the Serial Monitor, add 4.7kΩ resistors between SDA->3V3 and SCL->3V3.
2. **Mounting:** For accurate vibration readings, the MPU6050 must be physically bolted or firmly epoxied to the casing of the equipment you are monitoring. If it is hanging loose by its wires, the Machine Learning model will output garbage data.

---

## 3. Powering the Node

The ESP32 operates at 3.3V internally but the development board has a built-in regulator.
* **Option A (USB):** Plug a standard Micro-USB or USB-C cable directly into the ESP32.
* **Option B (Direct Wiring):** Connect a 5V power source to the **VIN / 5V** pin and the **GND** pin. *Never apply 5V to the 3V3 pin!*

## 4. Replacement Procedure
If a node is destroyed by lightning or animals:
1. Disconnect power.
2. Unbolt the old MPU6050 and ESP32.
3. Wire the new components exactly as shown in the table above.
4. Flash the ESP32 with the standard C++ firmware. **Crucial:** Remember to update `DEVICE_ID` in `config.h` before flashing!
5. Re-bolt the sensor to the equipment and restore power.
