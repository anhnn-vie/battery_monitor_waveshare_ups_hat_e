#!/usr/bin/env python3
"""
Battery Monitor - Pi OS
Theo dõi thời gian pin qua I2C (địa chỉ 0x2D)
Giao diện: Tkinter dark-theme – tối ưu cho màn hình 800×480
"""
import tkinter as tk
import threading
import time
import math
import collections
import os

# ══════════════════════════════════════════════════════════════════════════════
# CẤU HÌNH
# ══════════════════════════════════════════════════════════════════════════════
ADDR       = 0x2D
LOW_VOL    = 3150       # mV – ngưỡng pin thấp
POLL_MS    = 2000       # ms – chu kỳ cập nhật
WIN_W      = 800
WIN_H      = 480
CHART_HIST = 180        # số điểm lịch sử (~6 phút với poll 2 s)

# ══════════════════════════════════════════════════════════════════════════════
# MÀU SẮC
# ══════════════════════════════════════════════════════════════════════════════
BG     = "#0d1117"
PANEL  = "#161b22"
BORDER = "#30363d"
TEXT   = "#e6edf3"
DIM    = "#8b949e"
GREEN  = "#3fb950"
YELLOW = "#d29922"
RED    = "#f85149"
BLUE   = "#58a6ff"
TEAL   = "#39d353"

def bat_color(pct: int) -> str:
    if pct > 70: return GREEN
    if pct > 30: return YELLOW
    return RED

# ══════════════════════════════════════════════════════════════════════════════
# I2C / DEMO / TEMP / WEATHER
# ══════════════════════════════════════════════════════════════════════════════
try:
    import smbus
    bus = smbus.SMBus(1)
    DEMO_MODE = False
except Exception:
    DEMO_MODE = True

_demo_t = 0.0
def read_battery() -> dict:
    global _demo_t
    if DEMO_MODE:
        _demo_t += 0.05
        pct   = max(5, int(72 + 20 * math.sin(_demo_t)))
        cur   = int(-800 + 300 * math.sin(_demo_t * 0.7))
        vcell = 3700 + int(200 * math.sin(_demo_t * 0.3))
        return {
            "vbus_v":   5.12,
            "vbus_i":   1.2,
            "vbus_p":   6.14,
            "bat_v":    round((vcell + 50) * 4 / 1000.0, 2),
            "bat_i":    cur,
            "bat_pct":  pct,
            "remain":   int(pct * 40),
            "time_min": (int(pct * 2.4) if cur < 0 else int((100 - pct) * 1.8)),
            "charging": cur >= 0,
            "cell_v":   [vcell, vcell - 30, vcell + 20, vcell - 10],
            "low_cell": any(v < LOW_VOL for v in [vcell, vcell - 30, vcell + 20, vcell - 10]),
        }
    try:
        data = bus.read_i2c_block_data(ADDR, 0x02, 0x01) # Lấy trạng thái pin
        chargestatus = "Fast Charging" if (data[0] & 0x40) else \
                        "Charging" if (data[0] & 0x80) else \
                        "Idle" if (data[0] & 0x20) else \
                        "Discharge"
        
        d = bus.read_i2c_block_data(ADDR, 0x10, 0x06) # lay thong tin sac
        vbus_v = round((d[0] | d[1] << 8) / 1000.0, 1)
        vbus_i = round((d[2] | d[3] << 8) / 1000.0, 1)
        vbus_p = round((d[4] | d[5] << 8) / 1000.0, 1)

        d = bus.read_i2c_block_data(ADDR, 0x20, 0x0C) # lay thong tin pin
        bat_v    = round((d[0] | d[1] << 8) / 1000.0, 1)
        cur_raw  = d[2] | d[3] << 8
        bat_i    = cur_raw - 0xFFFF if cur_raw > 0x7FFF else cur_raw
        bat_pct  = int(d[4] | d[5] << 8)
        remain   = d[6] | d[7] << 8
        time_min = (d[8] | d[9] << 8) if bat_i < 0 else (d[10] | d[11] << 8)

        d = bus.read_i2c_block_data(ADDR, 0x30, 0x08) # lay thong tin cell
        cells = [d[i] | d[i+1] << 8 for i in range(0, 8, 2)]
        
        # Lấy nhiệt độ CPU (Sửa lỗi thụt lề và xử lý giá trị 47850)
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                # Đọc "47850", ép kiểu int, chia 1000 -> 47.85, làm tròn 1 chữ số -> 47.9
                cpu_temp = round(int(f.read().strip()) / 1000.0, 1)
        except:
            cpu_temp = 0.0
            
        def get_cpu_percent():
                def read_stat():
                        with open("/proc/stat") as f:
                                fields = f.readline().split()
                        idle = int(fields[4])
                        total = sum(int(x) for x in fields[1:])
                        return idle, total

                idle1, total1 = read_stat()
                time.sleep(0.1)
                idle2, total2 = read_stat()

                idle_delta  = idle2 - idle1
                total_delta = total2 - total1
                return round((1 - idle_delta / total_delta) * 100, 1)

        return {
            "chargestatus":     chargestatus,
            "vbus_v":   vbus_v,
            "vbus_i":   vbus_i,
            "vbus_p":   vbus_p,
            "bat_v":    bat_v,
            "bat_i":    bat_i,
            "bat_pct":  bat_pct,
            "remain":   remain,
            "time_min": time_min,
            "charging": bat_i >= 0,
            "cell_v":   cells,
            "low_cell": any(v < LOW_VOL for v in cells),
            "cpu_temp": cpu_temp,
            "cpu":      get_cpu_percent(),
        }
    except Exception as e:
        raise RuntimeError(f"I2C error: {e}")
    
      
    
# ══════════════════════════════════════════════════════════════════════════════
# CỘT TRÁI – GAUGE % PIN
# ══════════════════════════════════════════════════════════════════════════════
class BatteryGauge(tk.Canvas):
    def __init__(self, master, size=170, **kw):
        super().__init__(master, width=size, height=size,
                         bg=BG, highlightthickness=0, **kw)
        self._size = size
        self._draw(0)

    def _draw(self, pct: int):
        color  = bat_color(pct)
        s, pad = self._size, 14
        self.delete("all")
        self.create_arc(pad, pad, s-pad, s-pad,
                        start=225, extent=-270,
                        style="arc", outline=BORDER, width=9)
        ext = int(-270 * pct / 100)
        if ext:
            self.create_arc(pad, pad, s-pad, s-pad,
                            start=225, extent=ext,
                            style="arc", outline=color, width=9)
        cx, cy = s // 2, s // 2
        self.create_text(cx, cy - 10, text=f"{pct}%",
                         fill=color, font=("Courier New", 26, "bold"))
        self.create_text(cx, cy + 18, text="BATTERY",
                         fill=DIM,   font=("Courier New", 14, "bold"))

    def update(self, data: dict):
        self._draw(data["bat_pct"])

# ══════════════════════════════════════════════════════════════════════════════
# CỘT TRÁI – TRẠNG THÁI SẠC / XẢ / NHIET DO
# ══════════════════════════════════════════════════════════════════════════════
class BatteryStatus(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=BG, **kw)
        self._chg_lbl = tk.Label(self, text="—", bg=BG, fg=GREEN,
                                  font=("Courier New", 11, "bold"))
        self._chg_lbl.pack(pady=(4, 0))
        self._time_lbl = tk.Label(self, text="—", bg=BG, fg=TEAL,
                                   font=("Courier New", 20, "bold"))
        self._time_lbl.pack()
        self._time_sub = tk.Label(self, text="", bg=BG, fg=DIM,
                                   font=("Courier New", 10, "bold"))
        self._time_sub.pack()

        # Tạo Frame bao quanh có viền
        self._temp_frame = tk.Frame(self, bg=BG, highlightbackground=GREEN, 
                            highlightthickness=2, width=160, height=110) # Đặt kích thước
        self._temp_frame.pack_propagate(False) # Ngăn frame tự co lại
        self._temp_frame.pack(pady=(15, 0))

        # Đặt các Label cũ VÀO TRONG self._temp_frame thay vì self
        self._temp_lbl = tk.Label(self._temp_frame, text="— °C", bg=BG, fg=TEAL,
                                  font=("Courier New", 18, "bold"))
        self._temp_lbl.pack()
        self._temp_sub = tk.Label(self._temp_frame, text="TEMP PC", bg=BG, fg=DIM,
                                  font=("Courier New", 12, "bold"))
        self._temp_sub.pack()
        
        # CPU USAGE
        self._cpu = tk.Label(self._temp_frame, text="", bg=BG, fg=TEAL,
                                  font=("Courier New", 18, "bold"))
        self._cpu.pack()
        self._cpu_sub = tk.Label(self._temp_frame, text="CPU LOAD", bg=BG, fg=DIM,
                                  font=("Courier New", 12, "bold"))
        self._cpu_sub.pack()

    def update(self, data: dict):
        m        = data["time_min"]
        time_str = f"{m//60}h {m%60:02d}m" if m >= 60 else f"{m} min"
        self._time_lbl.configure(text=time_str)
        status = data["chargestatus"]
        if status == "Fast Charging":
            self._chg_lbl.configure(text="▲ FAST CHARGING", fg=GREEN)
            self._time_sub.configure(text="Time until fully charged")
        elif status == "Charging":
            self._chg_lbl.configure(text="▲ CHARGING", fg=GREEN)
            self._time_sub.configure(text="Time until fully charged")
        elif status == "Discharge":
            self._chg_lbl.configure(text="▼ DISCHARGE", fg=YELLOW)
            self._time_sub.configure(text="Time remaining")
        else: # Trạng thái "Idle"
            self._chg_lbl.configure(text="● IDLE", fg=DIM)
            self._time_sub.configure(text="Battery Fully")
        # Hiển thị nhiệt độ CPU
        temp = data.get("cpu_temp", 0.0)
        self._temp_lbl.configure(text=f"{temp}°C")
        # Đổi màu cảnh báo nếu CPU quá nóng (> 60°C)
        if temp > 60:
            self._temp_lbl.configure(fg="red")
        else:
            self._temp_lbl.configure(fg=TEAL)
        # Hiển thị CPU Load
        cpu = data.get("cpu")
        self._cpu.configure(text=f"{cpu}%")
# ══════════════════════════════════════════════════════════════════════════════
# CỘT PHẢI – PHẦN 1: THÔNG TIN PIN & THÔNG TIN SẠC
# ══════════════════════════════════════════════════════════════════════════════
class MetricRow(tk.Frame):
    def __init__(self, master, label: str, unit: str = "", **kw):
        super().__init__(master, bg=PANEL, **kw)
        tk.Label(self, text=label, bg=PANEL, fg=DIM,
                 font=("Courier New", 10), anchor="w", width=18).pack(side="left")
        if unit:
            tk.Label(self, text=unit, bg=PANEL, fg=DIM,
                     font=("Courier New", 10), width=4, anchor="w").pack(side="right")
        self._val = tk.Label(self, text="—", bg=PANEL, fg=TEXT,
                             font=("Courier New", 10, "bold"), anchor="e")
        self._val.pack(side="right")

    def set(self, value, color=TEXT):
        self._val.configure(text=str(value), fg=color)
class BatteryInfo(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=PANEL,
                         highlightbackground=BORDER, highlightthickness=1, **kw)
        tk.Label(self, text="BATTERY INFO", bg=PANEL, fg=DIM,
                 font=("Courier New", 11, "bold")).pack(anchor="w", padx=8, pady=(3, 1))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 3))

        self._bat_v = MetricRow(self, "Voltage",  "V")
        self._bat_i = MetricRow(self, "Current",      "mA")
        self._rem   = MetricRow(self, "Capacity",   "mAh")
        for r in [self._bat_v, self._bat_i, self._rem]:
            r.pack(fill="x", padx=8, pady=2)

    def update(self, data: dict):
        low_v = LOW_VOL * 4 / 1000.0
        self._bat_v.set(data["bat_v"], RED if data["bat_v"] < low_v else TEXT)
        cur = data["bat_i"]
        self._bat_i.set(f"{'+' if cur >= 0 else ''}{cur}",
                        GREEN if cur >= 0 else YELLOW)
        self._rem.set(data["remain"])


class ChargeInfo(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=PANEL,
                         highlightbackground=BORDER, highlightthickness=1, **kw)
        tk.Label(self, text="VBUS (CHARGE INFO)", bg=PANEL, fg=DIM,
                 font=("Courier New", 11, "bold")).pack(anchor="w", padx=8, pady=(3, 1))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 3))

        self._vbus_v = MetricRow(self, "Voltage",   "V")
        self._vbus_i = MetricRow(self, "Current",      "A")
        self._vbus_p = MetricRow(self, "Power", "W")
        for r in [self._vbus_v, self._vbus_i, self._vbus_p]:
            r.pack(fill="x", padx=8, pady=2)

    def update(self, data: dict):
        self._vbus_v.set(data["vbus_v"])
        self._vbus_i.set(data["vbus_i"])
        self._vbus_p.set(data["vbus_p"])

# ══════════════════════════════════════════════════════════════════════════════
# CỘT PHẢI – PHẦN 2: ĐIỆN ÁP TỪNG CELL
# ══════════════════════════════════════════════════════════════════════════════
class CellBar(tk.Frame):
    def __init__(self, master, idx: int, **kw):
        super().__init__(master, bg=PANEL, pady=3, **kw)
        tk.Label(self, text=f"C{idx+1}", bg=PANEL, fg=DIM,
                 font=("Courier New", 12), width=3).pack(side="left")
        self._cv   = tk.Canvas(self, width=130, height=10,
                               bg=BORDER, highlightthickness=0)
        self._cv.pack(side="left", padx=4)
        self._fill = self._cv.create_rectangle(0, 0, 0, 10, fill=GREEN, width=0)
        self._lbl  = tk.Label(self, text="—", bg=PANEL, fg=TEXT,
                              font=("Courier New", 11))
        self._lbl.pack(side="left")

    def set(self, mv: int):
        ratio = max(0, min(1, (max(3000, min(4200, mv)) - 3000) / 1200))
        self._cv.coords(self._fill, 0, 0, int(130 * ratio), 10)
        self._cv.itemconfig(self._fill, fill=bat_color(int(ratio * 100)))
        warn = " ⚠" if mv < LOW_VOL else ""
        self._lbl.configure(text=f"{mv} mV{warn}",
                            fg=RED if mv < LOW_VOL else TEXT)


class CellVoltages(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=PANEL,
                         highlightbackground=BORDER, highlightthickness=1, **kw)
        tk.Label(self, text="BATTERY CELL VOLTAGE", bg=PANEL, fg=DIM,
                 font=("Courier New", 11, "bold")).pack(anchor="w", padx=8, pady=(3, 1))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 3))

        self._cells = []
        for row_idx in range(2):
            row = tk.Frame(self, bg=PANEL)
            row.pack(fill="x", padx=8, pady=(1, 2))
            for col_idx in range(2):
                cb = CellBar(row, row_idx * 2 + col_idx)
                cb.pack(side="left", expand=True, padx=2)
                self._cells.append(cb)

    def update(self, data: dict):
        for i, mv in enumerate(data["cell_v"]):
            self._cells[i].set(mv)

# ══════════════════════════════════════════════════════════════════════════════
# CỘT PHẢI – PHẦN 3: ĐỒ THỊ VOLTAGE THEO THỜI GIAN
# ══════════════════════════════════════════════════════════════════════════════
class VoltageChart(tk.Frame):
    VMIN  = 14.0
    VMAX  = 17.0
    PAD_L = 44
    PAD_R = 10
    PAD_T = 10
    PAD_B = 24

    def __init__(self, master, **kw):
        super().__init__(master, bg=PANEL,
                         highlightbackground=BORDER, highlightthickness=1, **kw)
        self._history: collections.deque = collections.deque(maxlen=CHART_HIST)

        ctrl = tk.Frame(self, bg=PANEL)
        ctrl.pack(fill="x", padx=8, pady=(4, 0))
        tk.Label(ctrl, text="CHART VOLTAGE", bg=PANEL, fg=DIM,
                 font=("Courier New", 11, "bold")).pack(side="left")
        self._span_lbl = tk.Label(ctrl, text="", bg=PANEL, fg=DIM,
                                  font=("Courier New", 12))
        self._span_lbl.pack(side="right")

        self._canvas = tk.Canvas(self, bg=PANEL, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=4, pady=(2, 4))

    def update(self, data: dict):
        self._history.append({
            "ts":       time.time(),
            "bat_v":    data["bat_v"],
            "charging": data["charging"],
        })
        self._redraw()

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10 or not self._history:
            return

        pl, pr = self.PAD_L, self.PAD_R
        pt, pb = self.PAD_T, self.PAD_B
        gw = W - pl - pr
        gh = H - pt - pb

        def gy(v):
            return pt + gh - int((v - self.VMIN) / (self.VMAX - self.VMIN) * gh)

        def gx(i, total):
            return pl + gw if total <= 1 else pl + int(i / (total - 1) * gw)

        hist = list(self._history)
        n    = len(hist)

        # Nền sạc / xả
        seg_start = 0
        for i in range(1, n + 1):
            chg = hist[i-1]["charging"]
            end = (i == n) or (hist[i]["charging"] != chg)
            if end:
                bg_col = "#0d2b0d" if chg else "#2b1a0d"
                c.create_rectangle(gx(seg_start, n), pt,
                                   gx(i - 1, n),     pt + gh,
                                   fill=bg_col, outline="")
                if i < n:
                    seg_start = i

        # Grid & nhãn trục Y mỗi 1 V
        for v in range(int(self.VMIN), int(self.VMAX) + 1):
            y = gy(v)
            if pt <= y <= pt + gh:
                c.create_line(pl, y, pl + gw, y, fill=BORDER, dash=(3, 5))
                c.create_text(pl - 4, y, text=f"{v}V",
                              fill=DIM, font=("Courier New", 9), anchor="e")

        # Trục
        c.create_line(pl, pt,      pl,      pt + gh, fill=BORDER)
        c.create_line(pl, pt + gh, pl + gw, pt + gh, fill=BORDER)

        # Tick & nhãn trục X mỗi 30 s
        if n >= 2:
            span_s = hist[-1]["ts"] - hist[0]["ts"]
            self._span_lbl.configure(
                text=f"Up: {int(span_s//60)}:{int(span_s%60):02d}")
            t0, t_last = hist[0]["ts"], hist[-1]["ts"]
            prev_x = None
            for idx, entry in enumerate(hist):
                elapsed = entry["ts"] - t0
                if int(elapsed) % 30 == 0:
                    x = gx(idx, n)
                    if prev_x is None or abs(x - prev_x) > 20:
                        c.create_line(x, pt + gh, x, pt + gh + 4, fill=DIM)
                        ago = t_last - entry["ts"]
                        lbl = f"-{int(ago//60)}m" if ago >= 60 else f"-{int(ago)}s"
                        c.create_text(x, pt + gh + 12, text=lbl,
                                      fill=DIM, font=("Courier New", 9))
                        prev_x = x

        # Đường pack voltage
        if n >= 2:
            pts  = [(gx(i, n), gy(hist[i]["bat_v"])) for i in range(n)]
            flat = [v for p in pts for v in p]
            c.create_line(*flat, fill=BLUE, width=2, smooth=True)

        # Ngưỡng LOW
        low_v = LOW_VOL * 4 / 1000.0
        yl    = gy(low_v)
        if pt <= yl <= pt + gh:
            c.create_line(pl, yl, pl + gw, yl, fill=RED, dash=(6, 4), width=1)
            c.create_text(pl + gw - 2, yl - 6,
                          text=f"LOW {low_v:.2f}V",
                          fill=RED, font=("Courier New", 10), anchor="e")

        # Điểm & giá trị hiện tại
        if hist:
            y_now = gy(hist[-1]["bat_v"])
            c.create_oval(pl+gw-4, y_now-4, pl+gw+4, y_now+4,
                          fill=BLUE, outline="")
            c.create_text(pl+gw-6, y_now-10,
                          text=f"{hist[-1]['bat_v']} V",
                          fill=BLUE, font=("Courier New", 10), anchor="e")

# ══════════════════════════════════════════════════════════════════════════════
# APP CHÍNH
# ══════════════════════════════════════════════════════════════════════════════
class BatteryMonitorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Battery Monitor v2.3")
        self.configure(bg=BG)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self._build_ui()
        self._poll()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(hdr, text="The UPS HAT (E) WAVESHARE designed for the Raspberry Pi series",
                 bg=BG, fg=BLUE, font=("Courier New", 10, "bold")).pack(side="left")

        self._status_dot = tk.Label(hdr, text="●", bg=BG, fg=DIM,
                                    font=("Courier New", 16))
        self._status_dot.pack(side="right")
        self._status_lbl = tk.Label(hdr, text="connecting…",
                                    bg=BG, fg=DIM, font=("Courier New", 10))
        self._status_lbl.pack(side="right", padx=4)

        if DEMO_MODE:
            tk.Label(self, text="[ DEMO MODE ]", bg=BG, fg=YELLOW,
                     font=("Courier New", 10)).pack()

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=14, pady=2)

        # ── Body ────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # ── CỘT TRÁI: gauge + trạng thái ────────────────────────────────────
        left = tk.Frame(body, bg=BG, width=210)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        self._gauge  = BatteryGauge(left)
        self._gauge.pack(pady=(4, 0))

        self._status = BatteryStatus(left)
        self._status.pack(fill="x")

        # ── CỘT PHẢI: 3 phần xếp dọc ────────────────────────────────────────
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Phần 1: thông tin pin (trái) + thông tin sạc (phải)
        row1 = tk.Frame(right, bg=BG)
        row1.pack(fill="x")
        self._bat_info = BatteryInfo(row1)
        self._bat_info.pack(side="left", expand=True, fill="both",
                            padx=(0, 4), ipady=4)
        self._chg_info = ChargeInfo(row1)
        self._chg_info.pack(side="left", expand=True, fill="both", ipady=4)

        # Phần 2: điện áp cell
        self._cells = CellVoltages(right)
        self._cells.pack(fill="x", pady=(6, 0), ipady=2)

        # Phần 3: đồ thị
        self._chart = VoltageChart(right)
        self._chart.pack(fill="both", expand=True, pady=(6, 0))

        # ── Status bar ───────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=14, pady=2)
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=14, pady=(0, 6))

        self._ts_lbl = tk.Label(bar, text="", bg=BG, fg=DIM,
                                font=("Courier New", 10))
        self._ts_lbl.pack(side="left")
        tk.Label(bar, text=f"Low: {LOW_VOL} mV/cell",
                 bg=BG, fg=DIM, font=("Courier New", 10)).pack(side="right")

    def _poll(self):
        def worker():
            while True:
                try:
                    data = read_battery()
                    self.after(0, self._apply, data, None)
                except Exception as e:
                    self.after(0, self._apply, None, str(e))
                time.sleep(POLL_MS / 1000)
        threading.Thread(target=worker, daemon=True).start()

    def _apply(self, data, error):
        if error:
            self._status_dot.configure(fg=RED)
            self._status_lbl.configure(text=error, fg=RED)
            return

        # Cột trái
        self._gauge.update(data)
        self._status.update(data)

        # Cột phải – phần 1
        self._bat_info.update(data)
        self._chg_info.update(data)

        # Cột phải – phần 2
        self._cells.update(data)

        # Cột phải – phần 3
        self._chart.update(data)

        # Header status dot
        pct       = data["bat_pct"]
        dot_color = RED if data["low_cell"] else (GREEN if pct > 20 else YELLOW)
        status    = "⚠ LOW" if data["low_cell"] else ("GOOD" if pct > 20 else "LOW")
        self._status_dot.configure(fg=dot_color)
        self._status_lbl.configure(text=status, fg=dot_color)

        # Status bar timestamp
        self._ts_lbl.configure(text=f"Updated: {time.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    app = BatteryMonitorApp()
    app.mainloop()
