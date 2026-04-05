# 🔋 Battery Monitor for Waveshare UPS HAT (E)

A real-time battery dashboard for the **Waveshare UPS HAT (E)** running on Raspberry Pi.  
Built with Python and Tkinter — optimized for an **800×480 touchscreen display**.

![Python](https://img.shields.io/badge/Python-3.7+-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red?logo=raspberrypi)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📸 Screenshot
![Screenshot](/discharged.png)
![Screenshot](/fastcharging.png)

---

## ✨ Features

- **Circular battery gauge** — shows charge percentage with color-coded status (green / yellow / red)
- **Charge status** — detects Fast Charging, Charging, Discharge, and Idle states
- **Time estimate** — time remaining on battery or time until fully charged
- **Battery info panel** — pack voltage, current (mA), and remaining capacity (mAh)
- **VBUS info panel** — input voltage, current, and power from the charger
- **4-cell voltage display** — individual cell voltages with visual bar indicators and low-voltage warnings (⚠)
- **Live voltage chart** — scrolling pack voltage history (~6 minutes) with charge/discharge background shading
- **CPU temperature & load** — reads directly from `/sys/class/thermal` and `/proc/stat`
- **Demo mode** — automatically activates when no I2C hardware is detected (useful for UI development)

---

## 🔧 Hardware Requirements

| Component | Details |
|---|---|
| Board | Raspberry Pi (any model with I2C) |
| UPS HAT | [Waveshare UPS HAT (E)](https://www.waveshare.com/wiki/UPS_HAT_(E)) |
| I2C Address | `0x2D` |
| Display | 800×480 (recommended) |

---

## 📦 Installation

### 1. Enable I2C on Raspberry Pi
```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
```

### 2. Install dependencies
```bash
sudo apt update
sudo apt install python3-smbus python3-tk -y
```

### 3. Clone this repository
```bash
git clone https://github.com/anhnn-vie/battery-monitor.git
cd battery-monitor
```

### 4. Run the app
```bash
python3 bat_monitor.py
```

> **No hardware?** The app automatically enters **Demo Mode** if the I2C bus is unavailable — great for testing the UI on any machine.

---

## ⚙️ Configuration

Edit the constants at the top of `bat_monitor.py`:
```python
ADDR       = 0x2D    # I2C slave address of the UPS HAT (E)
LOW_VOL    = 3150    # Low voltage threshold per cell (mV)
POLL_MS    = 2000    # Data refresh interval (milliseconds)
WIN_W      = 800     # Window width
WIN_H      = 480     # Window height
CHART_HIST = 180     # Number of data points in the voltage chart (~6 min at 2s poll)
```

---

## 📋 I2C Register Map (Waveshare UPS HAT E)

| Register | Length | Description |
|---|---|---|
| `0x02` | 1 byte | Charge status flags |
| `0x10` | 6 bytes | VBUS voltage, current, power |
| `0x20` | 12 bytes | Pack voltage, current, percentage, capacity, time |
| `0x30` | 8 bytes | Individual cell voltages (4 cells × 2 bytes) |

---

## 🖥️ Autostart on Boot (optional)

To launch the dashboard automatically on desktop startup, create an autostart entry:
```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/battery-monitor.desktop
```

Paste the following:
```ini
[Desktop Entry]
Type=Application
Name=Battery Monitor
Exec=python3 /home/pi/battery-monitor/bat_monitor.py
```

---

## 📁 Project Structure
