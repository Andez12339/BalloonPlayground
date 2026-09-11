"""
USELESS PROJECT — Balloon Desktop Toy (v3.2)
--------------------------------------------
Run:  python useless_balloon.py

Features:
  - Screen-Wide Freedom: The balloon can move, float, bounce, and be flung
    anywhere across your entire desktop screen.
  - Transparent Click-Through: Uses dynamic window masking so clicks outside
    the balloon pass directly through to your desktop and other apps.
  - Intelligent Breath / Blow Detection: Autocorrelation pitch filtering +
    FFT turbulence analysis ensures the balloon only inflates when blowing air
    into the microphone (ignores regular speech, music, and whistling).
  - Full Bluetooth Headset Support (AirPods, etc.): Native sample rate negotiation,
    auto-detection, live audio test meter, and sensitivity slider in Setup.
  - Interactive Physics:
    * Inflate: Click & hold balloon, blow into mic to fill with air.
    * Tie: Press Enter to tie off knot and string.
    * Throw / Fling: Drag and toss the tied balloon across your screen.
    * Wind: Blowing into the mic pushes the tied balloon through the air.
    * Static Rub & Pop: Rub with mouse to create friction squeaks until it POPs with confetti!
"""

import os
# Prevent OpenBLAS thread allocation issues on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import sys, math, random
import numpy as np
import sounddevice as sd
from PyQt5.QtWidgets import (
    QWidget, QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QComboBox, QGridLayout, QPushButton, QSlider,
    QMenu, QAction
)
from PyQt5.QtGui import (
    QPainter, QPainterPath, QColor, QRadialGradient, QLinearGradient,
    QPen, QBrush, QFont, QRegion, QCursor, QDesktopServices
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QPointF, QRect, QRectF, QUrl

SAMPLE_RATE = 44100

# ---- Balloon style presets ----
BALLOON_STYLES = [
    {"name": "Ruby",   "color": QColor(230,  50,  85)},
    {"name": "Sky",    "color": QColor( 50, 150, 235)},
    {"name": "Lime",   "color": QColor( 70, 210,  80)},
    {"name": "Gold",   "color": QColor(240, 190,  30)},
    {"name": "Violet", "color": QColor(170,  70, 230)},
    {"name": "Coral",  "color": QColor(255, 110,  75)},
    {"name": "Mint",   "color": QColor( 50, 220, 180)},
    {"name": "Rose",   "color": QColor(255, 105, 170)},
]

# ---- synthesized sound effects ----
def play_tone(freq=440, duration=0.15, volume=0.3, kind='sine'):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    if kind == 'sine':
        wave = np.sin(freq * t * 2 * np.pi)
    else:  # noise
        wave = np.random.uniform(-1, 1, t.shape)
    envelope = np.linspace(1, 0, wave.shape[0])
    audio = (wave * envelope * volume).astype(np.float32)
    try:
        sd.play(audio, SAMPLE_RATE)
    except Exception:
        pass

def play_pop():
    play_tone(freq=180, duration=0.14, volume=0.8, kind='noise')

def play_hiss(duration=0.5):
    play_tone(duration=duration, volume=0.22, kind='noise')

def play_tie_squeak():
    play_tone(freq=950, duration=0.09, volume=0.35, kind='sine')

def play_rub():
    play_tone(freq=random.randint(280, 520), duration=0.04, volume=0.15, kind='noise')


# ---- Intelligent Breath / Blow Detector ----
class BreathDetector:
    """
    Distinguishes the turbulent, unvoiced friction of blowing into a microphone
    from speech (voiced harmonics/pitch), ambient noise, or whistling.
    """
    def __init__(self, sample_rate=44100, sensitivity=1.3):
        self.sample_rate = sample_rate
        self.sensitivity = max(float(sensitivity), 0.2)
        self.ambient_rms = 0.005
        self.is_blowing = False
        self.strength = 0.0
        self.raw_level = 0.0

    def process(self, block):
        if block is None or len(block) == 0:
            return False, 0.0, 0.0

        data = block.flatten().astype(np.float32)
        data = data - np.mean(data)
        rms = float(np.sqrt(np.mean(data ** 2)))
        self.raw_level = rms

        # Track ambient noise floor adaptively
        if rms < self.ambient_rms * 1.5:
            self.ambient_rms = 0.96 * self.ambient_rms + 0.04 * max(rms, 0.0008)

        # Baseline threshold dynamically adjusted for sensitivity
        thresh = max(0.004 / self.sensitivity, self.ambient_rms * 1.25)

        if rms < thresh:
            self.is_blowing = False
            self.strength = 0.0
            return False, 0.0, rms

        # 1. Pitch / Voicing check via autocorrelation:
        min_lag = max(int(self.sample_rate * 0.0022), 2)
        max_lag = min(int(self.sample_rate * 0.0180), len(data) - 1)
        max_pitch_corr = 0.0

        if max_lag > min_lag:
            r = np.correlate(data, data, mode='full')
            r = r[len(data) - 1:]
            r_norm = r / (r[0] + 1e-9)
            max_pitch_corr = float(np.max(r_norm[min_lag:max_lag]))

        # 2. Spectral energy distribution via FFT:
        fft = np.abs(np.fft.rfft(data))
        freqs = np.fft.rfftfreq(len(data), 1.0 / self.sample_rate)
        tot_energy = float(np.sum(fft ** 2)) + 1e-9

        # Turbulent breath band: 40 Hz to 1400 Hz (air hitting capsule)
        turb_band = (freqs >= 40) & (freqs <= 1400)
        turb_ratio = float(np.sum(fft[turb_band] ** 2)) / tot_energy

        # High frequency band (> 3600 Hz): detect sibilance ('s'/'sh') or keyboard clicks
        hi_band = (freqs >= 3600)
        hi_ratio = float(np.sum(fft[hi_band] ** 2)) / tot_energy

        # 3. Spectral crest (peakiness) to reject tonal whistling
        peak_val = float(np.max(fft))
        mean_val = float(np.mean(fft)) + 1e-9
        crest = peak_val / mean_val

        # Blowing condition:
        # - Not voiced speech (max_pitch_corr < 0.52)
        # - Strong low/mid turbulence (turb_ratio > 0.30)
        # - Not high hiss (hi_ratio < 0.45)
        # - Not tonal whistle (crest < 35.0)
        detected = (max_pitch_corr < 0.52) and (turb_ratio > 0.30) and (hi_ratio < 0.45) and (crest < 35.0)

        if detected:
            self.is_blowing = True
            norm_rms = (rms / (thresh * 4.0)) * self.sensitivity
            self.strength = float(np.clip(norm_rms, 0.2, 1.0))
        else:
            self.is_blowing = False
            self.strength = 0.0

        return self.is_blowing, self.strength, rms


# ---- Microphone Listener with Decoupled Processing (No GIL Deadlocks) ----
class MicListener:
    def __init__(self, device_index=None, sensitivity=1.3):
        self.detector = BreathDetector(sample_rate=44100, sensitivity=sensitivity)
        self.stream = None
        self.fallback_stream = None
        self.active_device = device_index
        self.sample_rate = 44100
        self.running = True
        self.latest_block_pri = None
        self.latest_block_fb = None
        self.is_blowing = False
        self.blow_strength = 0.0
        self.level = 0.0

        # Open primary device
        if device_index is not None:
            self.stream = self._open_stream(device_index, is_fallback=False)

        # Open fallback stream on system default
        if device_index is None:
            self.stream = self._open_stream(None, is_fallback=False)
        else:
            self.fallback_stream = self._open_stream(None, is_fallback=True)

    def _open_stream(self, dev_idx, is_fallback=False):
        rates = []
        try:
            target = dev_idx if dev_idx is not None else sd.default.device[0]
            info = sd.query_devices(target)
            native_sr = int(info.get('default_samplerate') or 44100)
            rates.append(native_sr)
        except Exception:
            pass
        rates.extend([44100, 48000, 16000, 8000])

        seen = set()
        rates = [r for r in rates if not (r in seen or seen.add(r))]

        cb = self._fb_cb if is_fallback else self._pri_cb
        for sr in rates:
            try:
                s = sd.InputStream(
                    device=dev_idx,
                    callback=cb,
                    channels=1,
                    samplerate=sr,
                    blocksize=1024,
                )
                s.start()
                if not is_fallback:
                    self.sample_rate = sr
                    self.detector.sample_rate = sr
                return s
            except Exception:
                pass
        return None

    # Ultra-fast non-blocking callbacks: only save latest buffer
    def _pri_cb(self, indata, frames, time_info, status):
        if self.running:
            self.latest_block_pri = indata[:, 0].copy()

    def _fb_cb(self, indata, frames, time_info, status):
        if self.running:
            self.latest_block_fb = indata[:, 0].copy()

    # Processing called safely from GUI thread (tick / meter_timer)
    def update(self):
        pri_block = self.latest_block_pri
        fb_block = self.latest_block_fb
        self.latest_block_pri = None
        self.latest_block_fb = None

        target_block = None
        if pri_block is not None:
            target_block = pri_block
        elif fb_block is not None:
            target_block = fb_block

        if target_block is not None:
            blowing, strength, raw_lvl = self.detector.process(target_block)
            self.is_blowing = blowing
            self.blow_strength = strength
            self.level = raw_lvl

    def set_sensitivity(self, val):
        self.detector.sensitivity = max(float(val), 0.2)

    def close(self):
        self.running = False
        for s_attr in ('stream', 'fallback_stream'):
            s = getattr(self, s_attr, None)
            if s is not None:
                try:
                    s.abort()
                except Exception:
                    pass
                try:
                    s.close()
                except Exception:
                    pass
                setattr(self, s_attr, None)


# ---- Balloon Model ----
class Balloon:
    MIN_R = 12.0
    MAX_R = 110.0
    POP_THRESHOLD = 380.0

    def __init__(self, x, y, color):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.r = 0.0            # starts fully deflated (0)
        self.color = color
        self.state = 'idle'     # 'idle', 'held', 'tied', 'deflating', 'popped'
        self.silence_timer = 0.0
        self.sway_phase = random.uniform(0, math.tau)
        self.rub_score = 0.0
        self.puff_pulse = 0.0

    def contains(self, px, py):
        eff_r = max(self.r, 24.0)
        dx = px - self.x
        dy = py - self.y
        if (dx * dx + dy * dy) <= (eff_r * 1.15) ** 2:
            return True
        if self.r < 15:
            return abs(dx) <= 30 and abs(dy) <= 22
        return False

    def update_string(self):
        knot_x = self.x
        knot_y = self.y + self.r * 0.95
        pts = [QPointF(knot_x, knot_y)]
        cur_x, cur_y = knot_x, knot_y
        seg_len = 16.0
        for i in range(4):
            lag_vx = -self.vx * 1.8
            sway = math.sin(self.sway_phase + i * 0.8) * (3.0 + i * 1.5)
            cur_x += (lag_vx + sway) * 0.3
            cur_y += seg_len
            pts.append(QPointF(cur_x, cur_y))
        return pts


# ---- Confetti Particle Effect upon Popping ----
class Particle:
    def __init__(self, x, y, color):
        self.x = float(x)
        self.y = float(y)
        angle = random.uniform(0, math.tau)
        speed = random.uniform(4.0, 16.0)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 3.0
        self.color = color
        self.life = 1.0
        self.size = random.uniform(4.0, 9.0)
        self.decay = random.uniform(0.015, 0.035)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.35
        self.vx *= 0.98
        self.life -= self.decay
        return self.life > 0


# ---- Setup Dialog: Device with Bluetooth Detection + Live Breath Test ----
class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Balloon Setup — Microphone & Color")
        self.setFixedSize(500, 560)
        self.setStyleSheet("""
            QDialog { background: #161626; }
            QLabel  { color: #e4e4f4; font-family: 'Segoe UI', sans-serif; }
            QComboBox {
                background: #20203c; color: #ffffff;
                border: 1px solid #4a4a75; border-radius: 8px;
                padding: 8px 12px; font-size: 13px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #20203c; color: #ffffff;
                selection-background-color: #e94560;
                padding: 6px;
            }
            QSlider::groove:horizontal {
                height: 6px; background: #2b2b48; border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #e94560; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff; width: 18px; margin-top: -6px; margin-bottom: -6px;
                border-radius: 9px;
            }
        """)

        self.selected_style = 0
        self.test_mic = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        # Title
        title = QLabel("🎈 Balloon Desktop Toy")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #ff6088;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Blow into your microphone or Bluetooth headset to inflate!")
        subtitle.setStyleSheet("color: #8c8caa; font-size: 12px;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #2b2b48;")
        layout.addWidget(sep)

        # Header with Refresh and Settings buttons
        mic_row = QHBoxLayout()
        mic_header = QLabel("Microphone / Headset Input")
        mic_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        mic_row.addWidget(mic_header)
        mic_row.addStretch()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setToolTip("Scan again for newly connected Bluetooth headphones")
        btn_refresh.setStyleSheet("""
            QPushButton { background: #262648; color: #ffffff; border-radius: 6px; padding: 4px 10px; font-size: 11px; }
            QPushButton:hover { background: #383868; }
        """)
        btn_refresh.clicked.connect(self._populate_devices)
        mic_row.addWidget(btn_refresh)

        btn_sound = QPushButton("⚙️ Sound Settings")
        btn_sound.setToolTip("Open Windows Sound Settings to verify headset microphone")
        btn_sound.setStyleSheet("""
            QPushButton { background: #262648; color: #ffffff; border-radius: 6px; padding: 4px 10px; font-size: 11px; }
            QPushButton:hover { background: #383868; }
        """)
        btn_sound.clicked.connect(self._open_sound_settings)
        mic_row.addWidget(btn_sound)
        layout.addLayout(mic_row)

        self.device_combo = QComboBox()
        self.device_map = {}
        layout.addWidget(self.device_combo)

        # Bluetooth status indicator
        self.bt_status_label = QLabel()
        self.bt_status_label.setStyleSheet("color: #8c8caa; font-size: 11px;")
        layout.addWidget(self.bt_status_label)

        # Sensitivity slider
        sens_row = QHBoxLayout()
        sens_label = QLabel("Breath Sensitivity:")
        sens_label.setFont(QFont("Segoe UI", 10))
        self.sens_val_label = QLabel("1.4x (Recommended for Bluetooth)")
        self.sens_val_label.setStyleSheet("color: #ff85a1; font-weight: bold; font-size: 11px;")
        sens_row.addWidget(sens_label)
        sens_row.addStretch()
        sens_row.addWidget(self.sens_val_label)
        layout.addLayout(sens_row)

        self.sens_slider = QSlider(Qt.Horizontal)
        self.sens_slider.setRange(5, 25)
        self.sens_slider.setValue(14)
        self.sens_slider.valueChanged.connect(self._on_sens_changed)
        layout.addWidget(self.sens_slider)

        # Populate devices now that slider exists
        self._populate_devices()
        self.device_combo.currentIndexChanged.connect(self._restart_mic_test)

        # Live Test Indicator Box
        test_box = QFrame()
        test_box.setStyleSheet("background: #1c1c32; border-radius: 8px; padding: 6px;")
        tbox_layout = QVBoxLayout(test_box)
        tbox_layout.setContentsMargins(12, 10, 12, 10)
        tbox_layout.setSpacing(6)

        t_header = QHBoxLayout()
        t_label = QLabel("Live Microphone & Breath Test:")
        t_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.blow_badge = QLabel("  💨 BLOW DETECTED  ")
        self.blow_badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.blow_badge.setStyleSheet("""
            background: #2b2b40; color: #666680;
            border-radius: 10px; padding: 2px 8px;
        """)
        t_header.addWidget(t_label)
        t_header.addStretch()
        t_header.addWidget(self.blow_badge)
        tbox_layout.addLayout(t_header)

        # Volume meter bar
        self.meter_bar = QFrame()
        self.meter_bar.setFixedHeight(8)
        self.meter_bar.setStyleSheet("background: #2c2c48; border-radius: 4px;")
        tbox_layout.addWidget(self.meter_bar)
        layout.addWidget(test_box)

        # Color picker
        color_label = QLabel("Select Balloon Color")
        color_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(color_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.style_buttons = []
        for idx, style in enumerate(BALLOON_STYLES):
            btn = QPushButton(style["name"])
            btn.setCheckable(True)
            c = style["color"]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba({c.red()},{c.green()},{c.blue()},180);
                    color: white; border-radius: 12px;
                    padding: 6px 2px; font-size: 11px; font-weight: bold;
                    border: 2px solid transparent;
                }}
                QPushButton:checked {{
                    border: 2px solid white;
                    background: rgba({c.red()},{c.green()},{c.blue()},255);
                }}
                QPushButton:hover {{
                    background: rgba({c.red()},{c.green()},{c.blue()},230);
                }}
            """)
            btn.clicked.connect(lambda _, i=idx: self._select_style(i))
            grid.addWidget(btn, idx // 4, idx % 4)
            self.style_buttons.append(btn)
        self.style_buttons[0].setChecked(True)
        layout.addLayout(grid)

        layout.addStretch()

        # Launch button
        launch = QPushButton("Launch Free-Floating Balloon!")
        launch.setFont(QFont("Segoe UI", 13, QFont.Bold))
        launch.setFixedHeight(48)
        launch.setStyleSheet("""
            QPushButton {
                background: #e94560; color: white;
                border-radius: 24px; border: none;
            }
            QPushButton:hover { background: #ff577d; }
            QPushButton:pressed { padding-top: 3px; }
        """)
        launch.clicked.connect(self._on_launch)
        layout.addWidget(launch)

        # Live poll timer for test meter
        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self._poll_test_meter)
        self.meter_timer.start(40)

    def _open_sound_settings(self):
        QDesktopServices.openUrl(QUrl("ms-settings:sound"))

    def _populate_devices(self):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_map = {}

        # 0. Always add Auto-Detect as top choice
        self.device_combo.addItem("🎙️ Auto-Detect Active Microphone (Recommended)")
        self.device_map[0] = None

        devices = sd.query_devices()
        try:
            default_dev = sd.default.device[0]
        except Exception:
            default_dev = None

        combo_idx = 1
        bt_found = []
        regular_found = []

        for i, dev in enumerate(devices):
            if dev['max_input_channels'] <= 0:
                continue

            try:
                hostapi_info = sd.query_hostapis(dev['hostapi'])
                hostapi_name = hostapi_info.get('name', '')
            except Exception:
                hostapi_name = ''

            # Exclude broken Windows WDM-KS driver endpoints
            if 'WDM-KS' in hostapi_name:
                continue

            name = dev['name'].strip()
            name_lower = name.lower()
            is_bt = any(k in name_lower for k in ['headset', 'airpod', 'bud', 'bluetooth', 'wireless', 'hands-free'])
            is_default = (i == default_dev)

            tags = []
            if is_bt:
                tags.append("🎧 Bluetooth/Headset")
            if is_default:
                tags.append("Default")

            tag_str = f"  [{', '.join(tags)}]" if tags else ""
            label = f"{name} ({hostapi_name}){tag_str}"

            if is_bt:
                bt_found.append((i, label, name))
            else:
                regular_found.append((i, label, name))

        for dev_id, lbl, name in bt_found:
            self.device_combo.addItem(lbl)
            self.device_map[combo_idx] = dev_id
            combo_idx += 1

        for dev_id, lbl, name in regular_found:
            self.device_combo.addItem(lbl)
            self.device_map[combo_idx] = dev_id
            combo_idx += 1

        if bt_found:
            self.device_combo.setCurrentIndex(1)
            self.bt_status_label.setText(f"🎧 Connected: {bt_found[0][2]} (Ready)")
            self.bt_status_label.setStyleSheet("color: #00ffaa; font-size: 11px; font-weight: bold;")
        else:
            self.device_combo.setCurrentIndex(0)
            self.bt_status_label.setText("💡 Tip: Connect headphones & click '🔄 Refresh' or use Auto-Detect")
            self.bt_status_label.setStyleSheet("color: #8c8caa; font-size: 11px;")

        self.device_combo.blockSignals(False)
        self._restart_mic_test()

    def _on_sens_changed(self, val):
        sens = val / 10.0
        self.sens_val_label.setText(f"{sens:.1f}x")
        if self.test_mic:
            self.test_mic.set_sensitivity(sens)

    def _restart_mic_test(self):
        if self.test_mic:
            self.test_mic.close()
            self.test_mic = None

        dev_idx = self.chosen_device()
        sens = (self.sens_slider.value() / 10.0) if hasattr(self, 'sens_slider') else 1.4
        try:
            self.test_mic = MicListener(dev_idx, sensitivity=sens)
        except Exception:
            self.test_mic = None

    def _poll_test_meter(self):
        if not self.test_mic:
            return

        self.test_mic.update()
        lvl = min(self.test_mic.level * 300, 100)
        is_blowing = self.test_mic.is_blowing

        fill_pct = int(lvl)
        if is_blowing:
            col = "#00f090"
            self.blow_badge.setStyleSheet("""
                background: #008850; color: #ffffff;
                border-radius: 10px; padding: 2px 8px; font-weight: bold;
            """)
        else:
            col = "#3878ff"
            self.blow_badge.setStyleSheet("""
                background: #2b2b40; color: #666680;
                border-radius: 10px; padding: 2px 8px;
            """)

        self.meter_bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {col}, stop:{fill_pct/100:.2f} {col},
                stop:{fill_pct/100:.2f} #2c2c48, stop:1 #2c2c48);
            border-radius: 4px;
        """)

    def _select_style(self, idx):
        self.selected_style = idx
        for i, btn in enumerate(self.style_buttons):
            btn.setChecked(i == idx)

    def chosen_device(self):
        ci = self.device_combo.currentIndex()
        return self.device_map.get(ci)

    def chosen_sensitivity(self):
        return self.sens_slider.value() / 10.0

    def chosen_color(self):
        return BALLOON_STYLES[self.selected_style]["color"]

    def _on_launch(self):
        self.meter_timer.stop()
        if self.test_mic:
            self.test_mic.close()
            self.test_mic = None
        self.accept()

    def closeEvent(self, e):
        self.meter_timer.stop()
        if self.test_mic:
            self.test_mic.close()
            self.test_mic = None
        super().closeEvent(e)


# ---- Fullscreen Transparent Overlay with Masking and Free Motion ----
class Overlay(QWidget):
    def __init__(self, device_index, balloon_color, sensitivity=1.4):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

        # Start balloon resting near bottom-right
        start_x = screen.width() - 220
        start_y = screen.height() - 180
        self.balloon = Balloon(start_x, start_y, balloon_color)

        self.mic = MicListener(device_index, sensitivity=sensitivity)
        self.particles = []

        self.dragging = False
        self.drag_offset_x = 0.0
        self.drag_offset_y = 0.0
        self.last_mouse_pos = None
        self.mouse_velocity = (0.0, 0.0)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(25)  # 40 FPS

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        self._update_window_mask()

    def _update_window_mask(self):
        b = self.balloon
        if b.state == 'popped' and not self.particles:
            self.setMask(QRegion())
            return

        if self.dragging:
            self.clearMask()
            return

        eff_r = max(b.r, 26.0)
        pad = 35.0
        top = int(b.y - eff_r - pad)
        left = int(b.x - eff_r - pad)
        width = int((eff_r + pad) * 2)
        height = int(eff_r * 2 + 130)

        if b.r < 15:
            left = min(left, int(b.x - 170))
            width = max(width, 340)
            top = min(top, int(b.y - 65))
            height = max(height, 140)

        left = max(0, left)
        top = max(0, top)
        width = min(self.width() - left, width)
        height = min(self.height() - top, height)

        mask_rect = QRect(left, top, width, height)
        self.setMask(QRegion(mask_rect))

    # ---------- Main Physics & Animation Loop ----------
    def tick(self):
        self.mic.update()
        b = self.balloon
        W, H = self.width(), self.height()
        is_blowing = self.mic.is_blowing
        blow_strength = self.mic.blow_strength

        # Update popping confetti particles
        if self.particles:
            self.particles = [p for p in self.particles if p.update()]

        # 1. State: IDLE
        if b.state == 'idle':
            b.vx *= 0.8
            b.vy *= 0.8

        # 2. State: HELD (Inflation mode)
        elif b.state == 'held':
            if is_blowing and blow_strength > 0:
                puff = blow_strength * 1.6
                b.r = min(b.r + puff, Balloon.MAX_R)
                b.puff_pulse = min(b.puff_pulse + 0.35, 1.0)
                b.silence_timer = 0.0

                b.x += random.uniform(-0.8, 0.8)
                b.y += random.uniform(-0.8, 0.8)
            else:
                b.puff_pulse *= 0.85
                b.silence_timer += 0.025
                if b.silence_timer > 3.5 and b.r > 20 and not self.dragging:
                    b.state = 'deflating'
                    play_hiss()

        # 3. State: DEFLATING
        elif b.state == 'deflating':
            b.r -= 2.5
            b.x += random.uniform(-14, 14)
            b.y += random.uniform(-12, 10)
            if b.r <= Balloon.MIN_R:
                b.r = 0.0
                b.state = 'idle'
                b.vx = 0.0
                b.vy = 0.0

        # 4. State: TIED (Free Floating Anywhere on the Screen!)
        elif b.state == 'tied':
            b.sway_phase += 0.04
            b.puff_pulse *= 0.85

            if not self.dragging:
                lift = -0.075
                b.vy += lift
                b.vx += math.sin(b.sway_phase) * 0.08

                if is_blowing and blow_strength > 0:
                    wind_push = blow_strength * 2.8
                    b.vy -= wind_push * 0.7
                    b.vx += random.uniform(-1.0, 1.0) * wind_push

                b.vx *= 0.985
                b.vy *= 0.985

                b.x += b.vx
                b.y += b.vy

                r = b.r
                margin = 10.0
                if b.x - r < margin:
                    b.x = r + margin
                    b.vx = abs(b.vx) * 0.75 + 1.0
                elif b.x + r > W - margin:
                    b.x = W - margin - r
                    b.vx = -abs(b.vx) * 0.75 - 1.0
                if b.y - r < margin:
                    b.y = r + margin
                    b.vy = abs(b.vy) * 0.65 + 0.5
                elif b.y + r + 50 > H - margin:
                    b.y = H - margin - r - 50
                    b.vy = -abs(b.vy) * 0.75

        # 5. State: POPPED
        elif b.state == 'popped':
            if not self.particles:
                new_color = QColor(
                    random.randint(140, 255),
                    random.randint(50, 210),
                    random.randint(70, 220),
                )
                start_x = random.randint(150, W - 150)
                start_y = H - 160
                b.__init__(start_x, start_y, new_color)

        self._update_window_mask()
        self.update()

    # ---------- Rendering ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        b = self.balloon

        for pt in self.particles:
            c = QColor(pt.color)
            c.setAlphaF(max(0.0, pt.life))
            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(pt.x, pt.y), pt.size, pt.size)

        if b.state == 'popped':
            return

        r = b.r

        if r < 12:
            self._draw_deflated_balloon(p, b)
            return

        eff_r = r + b.puff_pulse * 4.0

        # String
        string_pts = b.update_string()
        p.setPen(QPen(QColor(70, 70, 80, 210), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for i in range(len(string_pts) - 1):
            p.drawLine(string_pts[i], string_pts[i+1])

        # Knot
        knot_col = b.color.darker(145)
        p.setBrush(QBrush(knot_col))
        p.setPen(Qt.NoPen)
        knot_w = max(eff_r * 0.16, 7.0)
        knot_h = max(eff_r * 0.14, 6.0)
        p.drawPolygon([
            QPointF(b.x - knot_w, b.y + eff_r * 0.95),
            QPointF(b.x + knot_w, b.y + eff_r * 0.95),
            QPointF(b.x, b.y + eff_r * 0.95 + knot_h * 1.5)
        ])

        # 3D Body
        grad = QRadialGradient(b.x - eff_r * 0.32, b.y - eff_r * 0.35, eff_r * 1.35)
        grad.setColorAt(0.0, b.color.lighter(170))
        grad.setColorAt(0.55, b.color)
        grad.setColorAt(0.95, b.color.darker(135))
        grad.setColorAt(1.0, b.color.darker(170))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)

        path = QPainterPath()
        oval_h = eff_r * 1.08
        path.addEllipse(QPointF(b.x, b.y), eff_r, oval_h)
        p.drawPath(path)

        # Specular Gloss
        spec = QRadialGradient(b.x - eff_r * 0.35, b.y - eff_r * 0.40, eff_r * 0.45)
        spec.setColorAt(0.0, QColor(255, 255, 255, 200))
        spec.setColorAt(0.7, QColor(255, 255, 255, 40))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(spec))
        p.drawEllipse(QPointF(b.x - eff_r * 0.28, b.y - eff_r * 0.32), eff_r * 0.38, eff_r * 0.28)

        # Rim
        rim = QRadialGradient(b.x + eff_r * 0.5, b.y + eff_r * 0.5, eff_r * 0.5)
        rim.setColorAt(0.0, QColor(255, 255, 255, 55))
        rim.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(rim))
        p.drawEllipse(QPointF(b.x + eff_r * 0.42, b.y + eff_r * 0.38), eff_r * 0.32, eff_r * 0.32)

        if b.state == 'held':
            self._draw_inflation_hud(p, b)

    def _draw_deflated_balloon(self, p, b):
        col = b.color
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(col.darker(120)))
        p.drawEllipse(QPointF(b.x, b.y), 24.0, 10.0)

        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(b.x - 2, b.y - 1), 20.0, 7.0)

        p.setBrush(QBrush(col.darker(140)))
        p.drawRect(QRectF(b.x - 4, b.y + 7, 8, 8))

        bubble_rect = QRectF(b.x - 140, b.y - 58, 280, 48)
        p.setBrush(QBrush(QColor(22, 22, 38, 210)))
        p.setPen(QPen(QColor(233, 69, 96, 180), 1.5))
        p.drawRoundedRect(bubble_rect, 10, 10)

        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor(240, 240, 255))
        p.drawText(bubble_rect, Qt.AlignCenter,
                   "🎈 Click & Hold, then BLOW to inflate!\nPress Enter when full to tie.")

    def _draw_inflation_hud(self, p, b):
        is_blowing = self.mic.is_blowing
        fill_pct = int((b.r / Balloon.MAX_R) * 100)

        hud_w = 160
        hud_rect = QRectF(b.x - hud_w / 2, b.y - b.r - 54, hud_w, 36)

        bg_col = QColor(0, 140, 80, 225) if is_blowing else QColor(30, 30, 50, 210)
        p.setBrush(QBrush(bg_col))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawRoundedRect(hud_rect, 18, 18)

        txt = f"💨 Blowing! {fill_pct}%" if is_blowing else f"Blowing Mic... {fill_pct}%"
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(hud_rect, Qt.AlignCenter, txt)

        hint_rect = QRectF(b.x - 90, b.y + b.r + 32, 180, 22)
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(240, 240, 255, 220))
        p.drawText(hint_rect, Qt.AlignCenter, "Press Enter to Tie Knot")

    # ---------- Mouse & Keyboard Interactions ----------
    def mousePressEvent(self, e):
        b = self.balloon
        if e.button() == Qt.LeftButton:
            if b.contains(e.x(), e.y()):
                self.dragging = True
                self.drag_offset_x = b.x - e.x()
                self.drag_offset_y = b.y - e.y()
                self.last_mouse_pos = (e.x(), e.y())
                self.mouse_velocity = (0.0, 0.0)

                if b.state in ('idle', 'deflating'):
                    b.state = 'held'
                    b.silence_timer = 0.0
                self.setCursor(QCursor(Qt.ClosedHandCursor))
                self.clearMask()
        elif e.button() == Qt.RightButton:
            if b.contains(e.x(), e.y()):
                self._show_context_menu(e.globalPos())

        self.setFocus()

    def mouseMoveEvent(self, e):
        b = self.balloon
        pos = (e.x(), e.y())

        if self.dragging:
            if self.last_mouse_pos:
                dx = e.x() - self.last_mouse_pos[0]
                dy = e.y() - self.last_mouse_pos[1]
                self.mouse_velocity = (
                    0.7 * self.mouse_velocity[0] + 0.3 * dx,
                    0.7 * self.mouse_velocity[1] + 0.3 * dy
                )

                if b.state == 'tied':
                    dist = math.hypot(dx, dy)
                    if dist > 3:
                        b.rub_score += dist
                        if random.random() < 0.35:
                            play_rub()
                        if b.rub_score > Balloon.POP_THRESHOLD:
                            self._trigger_pop()

            b.x = float(e.x() + self.drag_offset_x)
            b.y = float(e.y() + self.drag_offset_y)
            self.last_mouse_pos = pos

        else:
            if b.contains(e.x(), e.y()):
                self.setCursor(QCursor(Qt.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))

        self.last_mouse_pos = pos

    def mouseReleaseEvent(self, e):
        b = self.balloon
        if self.dragging:
            self.dragging = False
            self.setCursor(QCursor(Qt.ArrowCursor))

            if b.state == 'tied':
                b.vx = float(np.clip(self.mouse_velocity[0] * 1.2, -35.0, 35.0))
                b.vy = float(np.clip(self.mouse_velocity[1] * 1.2, -35.0, 35.0))

            elif b.state == 'held':
                if b.r > 15:
                    b.state = 'deflating'
                    play_hiss()
                else:
                    b.state = 'idle'

            self._update_window_mask()

    def keyPressEvent(self, e):
        b = self.balloon
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if b.state == 'held' and b.r > 12:
                b.state = 'tied'
                play_tie_squeak()
                b.vy = -2.0
        elif e.key() == Qt.Key_P:
            if b.r > 15:
                self._trigger_pop()
        elif e.key() == Qt.Key_Escape:
            self.close()

    def _trigger_pop(self):
        b = self.balloon
        b.state = 'popped'
        play_pop()
        self.particles = [Particle(b.x, b.y, b.color) for _ in range(45)]
        self.clearMask()

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1e1e34; color: #f0f0f8;
                border: 1px solid #4a4a70; border-radius: 8px; padding: 4px;
            }
            QMenu::item:selected {
                background: #e94560; border-radius: 4px;
            }
        """)

        pop_action = QAction("💥 Pop Balloon", self)
        pop_action.triggered.connect(self._trigger_pop)
        menu.addAction(pop_action)

        color_menu = menu.addMenu("🎨 Change Color")
        for style in BALLOON_STYLES:
            act = QAction(style["name"], self)
            act.triggered.connect(lambda _, c=style["color"]: self._change_color(c))
            color_menu.addAction(act)

        menu.addSeparator()
        exit_action = QAction("❌ Exit", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)

        menu.exec_(global_pos)

    def _change_color(self, color):
        self.balloon.color = color

    def closeEvent(self, e):
        self.mic.close()
        super().closeEvent(e)


# ---- Entry Point ----
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    dialog = SetupDialog()
    if dialog.exec_() != QDialog.Accepted:
        sys.exit(0)

    device_index   = dialog.chosen_device()
    balloon_color  = dialog.chosen_color()
    sensitivity    = dialog.chosen_sensitivity()

    w = Overlay(device_index, balloon_color, sensitivity=sensitivity)
    w.show()
    sys.exit(app.exec_())
