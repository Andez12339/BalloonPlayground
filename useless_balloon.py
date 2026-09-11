import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys, math, random, time, threading
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
BALLOON_STYLES = [
    {"name": "Ruby",      "color": QColor(245,  50,  85)},
    {"name": "Sky",       "color": QColor( 40, 150, 245)},
    {"name": "Emerald",   "color": QColor( 45, 210, 110)},
    {"name": "Gold",      "color": QColor(255, 195,  30)},
    {"name": "Violet",    "color": QColor(165,  65, 240)},
    {"name": "Tangerine", "color": QColor(255, 115,  50)},
    {"name": "Mint",      "color": QColor( 40, 230, 190)},
    {"name": "Hot Pink",  "color": QColor(255,  80, 175)},
    {"name": "Azure",     "color": QColor( 30, 190, 255)},
    {"name": "Lavender",  "color": QColor(185, 130, 255)},
]
def play_tone(freq=440, duration=0.15, volume=0.3, kind='sine'):
    def _run():
        try:
            t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
            if kind == 'sine':
                wave = np.sin(freq * t * 2 * np.pi)
            else:
                wave = np.random.uniform(-1, 1, t.shape)
            envelope = np.linspace(1, 0, wave.shape[0])
            audio = (wave * envelope * volume).astype(np.float32)
            sd.play(audio, SAMPLE_RATE)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
def play_pop():
    play_tone(freq=180, duration=0.14, volume=0.8, kind='noise')
def play_hiss(duration=0.5):
    play_tone(duration=duration, volume=0.22, kind='noise')
def play_tie_squeak():
    play_tone(freq=950, duration=0.09, volume=0.35, kind='sine')
def play_rub():
    play_tone(freq=random.randint(280, 520), duration=0.04, volume=0.15, kind='noise')
def check_and_unmute_windows_mic():
    """Checks if default recording device in Windows is muted, and unmutes it with volume boost."""
    try:
        import ctypes
        from ctypes import wintypes
        ole32 = ctypes.oledll.ole32
        ole32.CoInitialize(None)
        CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
        IID_IMMDeviceEnumerator  = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
        IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"
        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8)
            ]
            @classmethod
            def from_str(cls, s):
                g = cls()
                ole32.CLSIDFromString(s, ctypes.byref(g))
                return g

        class IAudioEndpointVolumeVtbl(ctypes.Structure):
            _fields_ = [
                ("QueryInterface", ctypes.c_void_p),
                ("AddRef", ctypes.c_void_p),
                ("Release", ctypes.c_void_p),
                ("RegisterControlChangeNotify", ctypes.c_void_p),
                ("UnregisterControlChangeNotify", ctypes.c_void_p),
                ("GetChannelCount", ctypes.c_void_p),
                ("SetMasterVolumeLevel", ctypes.c_void_p),
                ("SetMasterVolumeLevelScalar", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_float, ctypes.c_void_p)),
                ("GetMasterVolumeLevel", ctypes.c_void_p),
                ("GetMasterVolumeLevelScalar", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float))),
                ("SetChannelVolumeLevel", ctypes.c_void_p),
                ("SetChannelVolumeLevelScalar", ctypes.c_void_p),
                ("GetChannelVolumeLevel", ctypes.c_void_p),
                ("GetChannelVolumeLevelScalar", ctypes.c_void_p),
                ("SetMute", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, wintypes.BOOL, ctypes.c_void_p)),
                ("GetMute", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL))),
            ]
        class IAudioEndpointVolume(ctypes.Structure):
            _fields_ = [("lpVtbl", ctypes.POINTER(IAudioEndpointVolumeVtbl))]
        class IMMDeviceVtbl(ctypes.Structure):
            _fields_ = [
                ("QueryInterface", ctypes.c_void_p),
                ("AddRef", ctypes.c_void_p),
                ("Release", ctypes.c_void_p),
                ("Activate", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(IAudioEndpointVolume)))),
            ]
        class IMMDevice(ctypes.Structure):
            _fields_ = [("lpVtbl", ctypes.POINTER(IMMDeviceVtbl))]
        class IMMDeviceEnumeratorVtbl(ctypes.Structure):
            _fields_ = [
                ("QueryInterface", ctypes.c_void_p),
                ("AddRef", ctypes.c_void_p),
                ("Release", ctypes.c_void_p),
                ("EnumAudioEndpoints", ctypes.c_void_p),
                ("GetDefaultAudioEndpoint", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(IMMDevice)))),
            ]
        class IMMDeviceEnumerator(ctypes.Structure):
            _fields_ = [("lpVtbl", ctypes.POINTER(IMMDeviceEnumeratorVtbl))]
        clsid_enum = GUID.from_str(CLSID_MMDeviceEnumerator)
        iid_enum = GUID.from_str(IID_IMMDeviceEnumerator)
        p_enum = ctypes.POINTER(IMMDeviceEnumerator)()
        if ole32.CoCreateInstance(ctypes.byref(clsid_enum), None, 1, ctypes.byref(iid_enum), ctypes.byref(p_enum)) == 0:
            p_dev = ctypes.POINTER(IMMDevice)()
            if p_enum.contents.lpVtbl.contents.GetDefaultAudioEndpoint(p_enum, 1, 1, ctypes.byref(p_dev)) == 0:
                iid_epv = GUID.from_str(IID_IAudioEndpointVolume)
                p_epv = ctypes.POINTER(IAudioEndpointVolume)()
                if p_dev.contents.lpVtbl.contents.Activate(p_dev, ctypes.byref(iid_epv), 1, None, ctypes.byref(p_epv)) == 0:
                    mute = wintypes.BOOL()
                    p_epv.contents.lpVtbl.contents.GetMute(p_epv, ctypes.byref(mute))
                    if mute.value:
                        p_epv.contents.lpVtbl.contents.SetMute(p_epv, False, None)
                    vol = ctypes.c_float()
                    p_epv.contents.lpVtbl.contents.GetMasterVolumeLevelScalar(p_epv, ctypes.byref(vol))
                    if vol.value < 0.65:
                        p_epv.contents.lpVtbl.contents.SetMasterVolumeLevelScalar(p_epv, 0.90, None)
    except Exception:
        pass
class BreathDetector:
    """Detects pure air blowing into the microphone.

    Strictly discriminates aerodynamic wind turbulence from human speech,
    talking, singing, humming, whistling, and room noises.
    """
    def __init__(self, sample_rate=44100, sensitivity=1.4):
        self.sample_rate = sample_rate
        self.sensitivity = max(float(sensitivity), 0.2)
        self.ambient_rms = 0.003
        self.is_blowing = False
        self.strength = 0.0
        self.raw_level = 0.0
        self.hold_counter = 0

    def process(self, block):
        if block is None or len(block) == 0:
            return False, 0.0, 0.0

        data = block.flatten().astype(np.float32)
        data = data - np.mean(data)
        rms = float(np.sqrt(np.mean(data ** 2)))
        self.raw_level = rms

        # Track ambient noise floor smoothly
        if rms < self.ambient_rms * 1.3:
            self.ambient_rms = 0.95 * self.ambient_rms + 0.05 * max(rms, 0.0003)

        # Dynamic sensitivity threshold above room ambient (slightly more sensitive, ~20% lower threshold)
        thresh = max(0.0017 / self.sensitivity, self.ambient_rms * 1.25)
        if rms < thresh:
            self.hold_counter = 0
            self.is_blowing = False
            self.strength = 0.0
            return False, 0.0, rms

        # 1. Pitch Autocorrelation (Strict Speech / Voice / Hum Rejection)
        # Check lags corresponding to human voice pitch 55 Hz to 450 Hz
        min_lag = max(int(self.sample_rate * 0.0022), 2)   # ~450 Hz
        max_lag = min(int(self.sample_rate * 0.0180), len(data) - 1)  # ~55 Hz
        max_pitch_corr = 0.0
        if max_lag > min_lag:
            r = np.correlate(data, data, mode='full')
            r = r[len(data) - 1:]
            r_norm = r / (r[0] + 1e-9)
            max_pitch_corr = float(np.max(r_norm[min_lag:max_lag]))

        # 2. Spectral Analysis (FFT)
        fft = np.abs(np.fft.rfft(data))
        freqs = np.fft.rfftfreq(len(data), 1.0 / self.sample_rate)
        tot_energy = float(np.sum(fft ** 2)) + 1e-9

        # Aerodynamic breath turbulence band (40 Hz to 1400 Hz)
        turb_band = (freqs >= 40) & (freqs <= 1400)
        turb_ratio = float(np.sum(fft[turb_band] ** 2)) / tot_energy

        # High-frequency band (Sibilance, hiss, sharp transients, key clicks: > 3600 Hz)
        hi_band = (freqs >= 3600)
        hi_ratio = float(np.sum(fft[hi_band] ** 2)) / tot_energy

        # Spectral crest factor (Peak / Mean: rejects whistles, tones, sharp formant resonances)
        peak_val = float(np.max(fft))
        mean_val = float(np.mean(fft)) + 1e-9
        crest = peak_val / mean_val

        # STRICT CRITERIA: ONLY PURE AIR BLOWING PASSES
        # - Voice pitch autocorrelation must be low (< 0.46) (speech is typically > 0.60 - 0.90)
        # - Aerodynamic turbulence energy must dominate (> 0.24)
        # - High frequency sibilance/clicks must be minimal (< 0.34)
        # - Spectral peakiness must be low (< 25.0) (whistles and single tones are > 40 - 200)
        is_unvoiced = (max_pitch_corr < 0.46)
        is_turbulent = (turb_ratio > 0.24)
        is_not_sibilant = (hi_ratio < 0.34)
        is_not_tonal = (crest < 25.0)

        detected = is_unvoiced and is_turbulent and is_not_sibilant and is_not_tonal

        if detected:
            self.hold_counter = 3
            self.is_blowing = True
            norm_rms = ((rms - thresh) / (thresh * 2.5)) * self.sensitivity
            self.strength = float(np.clip(norm_rms + 0.25, 0.25, 1.0))
        else:
            if self.hold_counter > 0:
                self.hold_counter -= 1
                self.strength *= 0.75
            else:
                self.is_blowing = False
                self.strength = 0.0

        return self.is_blowing, self.strength, rms


class MicListener:
    def __init__(self, device_index=None, sensitivity=1.4):
        check_and_unmute_windows_mic()
        self.detector = BreathDetector(sample_rate=44100, sensitivity=sensitivity)
        self.stream = None
        self.active_device = device_index
        self.sample_rate = 44100
        self.running = True
        self.latest_block = None
        self.is_blowing = False
        self.blow_strength = 0.0
        self.level = 0.0
        self.stream = self._open_stream(device_index)
        if self.stream is None and device_index is not None:
            self.stream = self._open_stream(None)

    def _open_stream(self, dev_idx):
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

        for sr in rates:
            try:
                s = sd.InputStream(
                    device=dev_idx,
                    callback=self._cb,
                    channels=1,
                    samplerate=sr,
                    blocksize=1024,
                )
                s.start()
                self.sample_rate = sr
                self.detector.sample_rate = sr
                return s
            except Exception:
                pass
        return None

    def _cb(self, indata, frames, time_info, status):
        if self.running:
            self.latest_block = indata[:, 0].copy()

    def update(self):
        block = self.latest_block
        self.latest_block = None
        if block is not None:
            blowing, strength, raw_lvl = self.detector.process(block)
            self.is_blowing = blowing
            self.blow_strength = strength
            self.level = raw_lvl

    def set_sensitivity(self, val):
        self.detector.sensitivity = max(float(val), 0.2)

    def close(self):
        self.running = False
        if self.stream is not None:
            s = self.stream
            self.stream = None
            try:
                s.abort()
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass


# ---- Balloon Model ----
class Balloon:
    MIN_R = 12.0
    MAX_R = 95.0
    POP_THRESHOLD = 350.0

    _id_counter = 0

    def __init__(self, x, y, color, name="Balloon"):
        Balloon._id_counter += 1
        self.id = Balloon._id_counter
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.r = 0.0            # starts deflated (0.0)
        self.color = color
        self.name = name
        self.state = 'idle'     # 'idle', 'held', 'tied', 'deflating', 'popped'
        self.silence_timer = 0.0
        self.sway_phase = random.uniform(0, math.tau)
        self.rub_score = 0.0
        self.puff_pulse = 0.0
        self.target_slot_x = float(x)
        self.target_slot_y = float(y)

    def contains(self, px, py):
        eff_r = max(self.r, 22.0)
        dx = px - self.x
        dy = py - self.y
        if (dx * dx + dy * dy) <= (eff_r * 1.12) ** 2:
            return True
        if self.r < 15:
            return abs(dx) <= 120 and abs(dy) <= 25
        return False

    def update_string(self):
        knot_x = self.x
        knot_y = self.y + self.r * 0.95
        pts = [QPointF(knot_x, knot_y)]
        cur_x, cur_y = knot_x, knot_y
        seg_len = 15.0
        for i in range(4):
            lag_vx = -self.vx * 1.6
            sway = math.sin(self.sway_phase + i * 0.7) * (3.0 + i * 1.2)
            cur_x += (lag_vx + sway) * 0.3
            cur_y += seg_len
            pts.append(QPointF(cur_x, cur_y))
        return pts


# ---- Confetti Particle Effect ----
class Particle:
    def __init__(self, x, y, color):
        self.x = float(x)
        self.y = float(y)
        angle = random.uniform(0, math.tau)
        speed = random.uniform(4.0, 16.0)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 3.5
        self.color = color
        self.life = 1.0
        self.size = random.uniform(4.0, 9.0)
        self.decay = random.uniform(0.016, 0.032)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.35
        self.vx *= 0.98
        self.life -= self.decay
        return self.life > 0


# ---- Setup Dialog ----
class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Balloon Setup — Microphone & Headset Input")
        self.setFixedSize(500, 425)
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

        self.test_mic = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        title = QLabel("🎈 Multi-Balloon Desktop Toy")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #ff6088;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Blow into your microphone to inflate balloons one after another!")
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

        btn_unmute = QPushButton("🔊 Unmute & Boost")
        btn_unmute.setToolTip("Unmute Windows microphone and boost volume to 90%")
        btn_unmute.setStyleSheet("""
            QPushButton { background: #1a3d2e; color: #00ffbb; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #24553f; }
        """)
        btn_unmute.clicked.connect(self._unmute_and_boost)
        mic_row.addWidget(btn_unmute)

        btn_sound = QPushButton("⚙️ Settings")
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

        # Detection Mode row
        mode_row = QHBoxLayout()
        mode_label = QLabel("Detection Mode:")
        mode_label.setFont(QFont("Segoe UI", 10))
        mode_row.addWidget(mode_label)
        mode_row.addStretch()

        mode_badge = QLabel("🌬️ Pure Air Blowing Only (Speech & Noise Rejected)")
        mode_badge.setStyleSheet("""
            background: #1e2840; color: #64b5f6;
            border: 1px solid #1976d2; border-radius: 6px;
            font-size: 11px; font-weight: bold; padding: 4px 10px;
        """)
        mode_row.addWidget(mode_badge)
        layout.addLayout(mode_row)

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

        # Populate devices
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
        self.blow_badge = QLabel("  🎙️ LISTENING...  ")
        self.blow_badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.blow_badge.setStyleSheet("""
            background: #2b2b40; color: #8c8caa;
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

        layout.addStretch()

        # Launch button
        launch = QPushButton("Launch Balloon Playground!")
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

        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self._poll_test_meter)
        self.meter_timer.start(40)

    def _unmute_and_boost(self):
        check_and_unmute_windows_mic()
        self._populate_devices()
        self._restart_mic_test()

    def _open_sound_settings(self):
        QDesktopServices.openUrl(QUrl("ms-settings:sound"))

    def _populate_devices(self):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_map = {}

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
        lvl = min(self.test_mic.level * 450, 100)
        is_blowing = self.test_mic.is_blowing

        fill_pct = int(lvl)
        if is_blowing:
            col = "#00f090"
            self.blow_badge.setText("  💨 AIR BLOW DETECTED!  ")
            self.blow_badge.setStyleSheet("""
                background: #008850; color: #ffffff;
                border-radius: 10px; padding: 2px 8px; font-weight: bold;
            """)
        else:
            col = "#3878ff"
            self.blow_badge.setText("  🎙️ LISTENING (Blow air into mic)  ")
            self.blow_badge.setStyleSheet("""
                background: #2b2b40; color: #8c8caa;
                border-radius: 10px; padding: 2px 8px;
            """)

        self.meter_bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {col}, stop:{fill_pct/100:.2f} {col},
                stop:{fill_pct/100:.2f} #2c2c48, stop:1 #2c2c48);
            border-radius: 4px;
        """)

    def chosen_device(self):
        ci = self.device_combo.currentIndex()
        return self.device_map.get(ci)

    def chosen_sensitivity(self):
        return self.sens_slider.value() / 10.0

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


# ---- Fullscreen Transparent Overlay with Continuous Random Balloons ----
class Overlay(QWidget):
    def __init__(self, device_index=None, sensitivity=1.4):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

        self.mic = MicListener(device_index, sensitivity=sensitivity)
        self.particles = []

        # All tied, free-floating balloons
        self.floating_balloons = []

        # Single active balloon dock in lower center of screen
        self.blow_pos_x = float(screen.width() // 2)
        self.blow_pos_y = float(screen.height() - 130)
        self.active_balloon = None
        self._last_style_name = None
        self._spawn_next_balloon()

        # Mouse interaction tracking
        self.dragged_balloon = None
        self.drag_offset_x = 0.0
        self.drag_offset_y = 0.0
        self.last_mouse_pos = None
        self.mouse_velocity = (0.0, 0.0)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)  # 60 FPS silky smooth animation

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        self._update_window_mask()

    def _spawn_next_balloon(self):
        """Spawns ONE single deflated balloon with a random vibrant color at the blowing dock."""
        pool = [s for s in BALLOON_STYLES if s["name"] != self._last_style_name]
        if not pool:
            pool = BALLOON_STYLES
        style = random.choice(pool)
        self._last_style_name = style["name"]

        b = Balloon(self.blow_pos_x, self.blow_pos_y, style["color"], style["name"])
        b.r = 0.0
        b.state = 'idle'
        self.active_balloon = b

    def _advance_to_next_balloon(self):
        """Called as soon as active balloon is tied: it floats away, and a new random balloon is given!"""
        if self.active_balloon:
            b = self.active_balloon
            b.state = 'tied'
            # Launch into room with upward momentum & room breeze
            b.vy = random.uniform(-5.5, -8.0)
            b.vx = random.uniform(-3.0, 3.0)
            self.floating_balloons.append(b)

        # Immediately give another random balloon to blow!
        self._spawn_next_balloon()

    def _update_window_mask(self):
        """Combines regions of all balloons so clicks outside pass to desktop."""
        if self.dragged_balloon is not None:
            self.clearMask()
            return

        full_region = QRegion()

        # 1. Active balloon area (dock pill if deflated, or balloon if inflating)
        ab = self.active_balloon
        if ab:
            if ab.r > 12:
                eff_r = ab.r + 30
                rect = QRect(int(ab.x - eff_r), int(ab.y - eff_r - 55), int(eff_r * 2), int(eff_r * 2 + 130))
                full_region = full_region.united(QRegion(rect))
            else:
                rect = QRect(int(ab.x - 120), int(ab.y - 28), 240, 56)
                full_region = full_region.united(QRegion(rect))

        # 2. All floating balloons
        for b in self.floating_balloons:
            if b.state == 'popped':
                continue
            eff_r = b.r + 20
            rect = QRect(int(b.x - eff_r), int(b.y - eff_r), int(eff_r * 2), int(eff_r * 2 + 95))
            full_region = full_region.united(QRegion(rect))

        # 3. Particles
        for p in self.particles:
            rect = QRect(int(p.x - 10), int(p.y - 10), 20, 20)
            full_region = full_region.united(QRegion(rect))

        self.setMask(full_region)

    # ---------- Main Physics & Multi-Balloon Animation Loop (60 FPS) ----------
    def tick(self):
        self.mic.update()
        W, H = self.width(), self.height()
        is_blowing = self.mic.is_blowing
        blow_strength = self.mic.blow_strength

        # 1. Update Confetti Particles
        if self.particles:
            self.particles = [p for p in self.particles if p.update()]

        # 2. Active Balloon Inflation & Rest Position (Smooth 60 FPS interpolation)
        ab = self.active_balloon
        if ab and ab != self.dragged_balloon and ab.state == 'idle':
            ab.x += (self.blow_pos_x - ab.x) * 0.16
            ab.y += (self.blow_pos_y - ab.y) * 0.16

        if ab and ab.state in ('idle', 'held'):
            if is_blowing and blow_strength > 0:
                ab.state = 'held'
                # Smooth inflation with incoming breath
                puff = blow_strength * 1.25
                ab.r += puff
                ab.puff_pulse = min(ab.puff_pulse + 0.25, 1.0)
                ab.silence_timer = 0.0

                # Micro breath turbulence vibration
                ab.x += random.uniform(-0.5, 0.5)
                ab.y += random.uniform(-0.5, 0.5)

                # Auto-Tie and Launch when full!
                if ab.r >= Balloon.MAX_R:
                    play_tie_squeak()
                    self._advance_to_next_balloon()

            else:
                ab.puff_pulse *= 0.90
                ab.silence_timer += 0.016
                # If released without tying and idle for too long, hiss and deflate
                if ab.silence_timer > 3.8 and ab.r > 20 and ab != self.dragged_balloon:
                    ab.state = 'deflating'
                    play_hiss()

        elif ab and ab.state == 'deflating':
            ab.r -= 1.8
            ab.x += random.uniform(-5, 5)
            ab.y += random.uniform(-5, 4)
            if ab.r <= 0:
                ab.r = 0.0
                ab.state = 'idle'
                ab.x = self.blow_pos_x
                ab.y = self.blow_pos_y

        # 3. Floating Balloons Physics (Multiple Balloons Bouncing Across Screen at 60 FPS)
        margin = 12.0
        for b in self.floating_balloons:
            if b == self.dragged_balloon or b.state != 'tied':
                continue

            b.sway_phase += 0.026
            b.puff_pulse *= 0.90

            # Helium lift + gentle room breeze
            lift = -0.05
            b.vy += lift
            b.vx += math.sin(b.sway_phase) * 0.055

            # Wind effect: Blowing also gently guides floating balloons!
            if is_blowing and blow_strength > 0:
                wind = blow_strength * 1.4
                b.vy -= wind * 0.4
                b.vx += random.uniform(-0.5, 0.5) * wind

            # Air drag (calibrated for 60 FPS)
            b.vx *= 0.991
            b.vy *= 0.991

            b.x += b.vx
            b.y += b.vy

            # Screen Boundaries Bounce
            r = b.r
            # Left wall
            if b.x - r < margin:
                b.x = r + margin
                b.vx = abs(b.vx) * 0.75 + 0.5
            # Right wall
            elif b.x + r > W - margin:
                b.x = W - margin - r
                b.vx = -abs(b.vx) * 0.75 - 0.5
            # Ceiling
            if b.y - r < margin:
                b.y = r + margin
                b.vy = abs(b.vy) * 0.65 + 0.35
            # Floor
            elif b.y + r + 50 > H - margin:
                b.y = H - margin - r - 50
                b.vy = -abs(b.vy) * 0.75

        # 4. Soft Balloon-to-Balloon Collisions (Smooth damping)
        fb_len = len(self.floating_balloons)
        for i in range(fb_len):
            for j in range(i + 1, fb_len):
                b1 = self.floating_balloons[i]
                b2 = self.floating_balloons[j]
                if b1.state != 'tied' or b2.state != 'tied':
                    continue

                dx = b2.x - b1.x
                dy = b2.y - b1.y
                dist = math.hypot(dx, dy)
                min_dist = b1.r + b2.r

                if dist < min_dist and dist > 0.01:
                    overlap = min_dist - dist
                    nx = dx / dist
                    ny = dy / dist

                    # Push apart softly
                    b1.x -= nx * overlap * 0.5
                    b1.y -= ny * overlap * 0.5
                    b2.x += nx * overlap * 0.5
                    b2.y += ny * overlap * 0.5

                    # Gentle momentum impulse
                    k = 0.22
                    b1.vx -= nx * k
                    b1.vy -= ny * k
                    b2.vx += nx * k
                    b2.vy += ny * k

        # Remove popped balloons from floating list
        self.floating_balloons = [b for b in self.floating_balloons if b.state != 'popped']

        self._update_window_mask()
        self.update()

    # ---------- Rendering ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 1. Confetti Particles
        for pt in self.particles:
            c = QColor(pt.color)
            c.setAlphaF(max(0.0, pt.life))
            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(pt.x, pt.y), pt.size, pt.size)

        # 2. Single Active Balloon (Deflated Dock or 3D Inflating Balloon)
        ab = self.active_balloon
        if ab:
            if ab.r > 12:
                self._draw_balloon_3d(p, ab)
                self._draw_inflation_hud(p, ab)
            else:
                self._draw_deflated_balloon_dock(p, ab)

        # 3. All Floating Tied Balloons
        for b in self.floating_balloons:
            if b.state == 'tied':
                self._draw_balloon_3d(p, b)

    def _draw_deflated_balloon_dock(self, p, ab):
        """Draws the single deflated balloon waiting in the dock ready to be blown."""
        dock_w = 230
        dock_h = 46
        dock_rect = QRectF(ab.x - dock_w / 2, ab.y - 23, dock_w, dock_h)

        is_blowing = self.mic.is_blowing

        bg_col = QColor(0, 140, 75, 215) if is_blowing else QColor(20, 20, 36, 210)
        border_col = QColor(ab.color.red(), ab.color.green(), ab.color.blue(), 180)

        p.setBrush(QBrush(bg_col))
        p.setPen(QPen(border_col, 1.6))
        p.drawRoundedRect(dock_rect, 23, 23)

        # Deflated Balloon Pouch icon
        bx = ab.x - 72
        by = ab.y
        col = ab.color

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(col.darker(120)))
        p.drawEllipse(QPointF(bx, by), 16.0, 9.0)

        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(bx - 2, by - 1), 12.0, 6.0)

        p.setBrush(QBrush(col.darker(145)))
        p.drawRect(QRectF(bx - 3, by + 6, 6, 6))

        # Prompt text
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor(255, 255, 255))
        txt_rect = QRectF(ab.x - 45, ab.y - 18, 150, 36)
        txt = "💨 Inflating..." if is_blowing else "🎈 Blow into mic to inflate!"
        p.drawText(txt_rect, Qt.AlignVCenter | Qt.AlignLeft, txt)

    def _draw_balloon_3d(self, p, b):
        r = b.r
        eff_r = r + b.puff_pulse * 3.5

        # Dynamic dangling string
        string_pts = b.update_string()
        p.setPen(QPen(QColor(70, 70, 85, 200), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for i in range(len(string_pts) - 1):
            p.drawLine(string_pts[i], string_pts[i+1])

        # Balloon Knot
        knot_col = b.color.darker(145)
        p.setBrush(QBrush(knot_col))
        p.setPen(Qt.NoPen)
        knot_w = max(eff_r * 0.15, 6.0)
        knot_h = max(eff_r * 0.13, 5.0)
        p.drawPolygon([
            QPointF(b.x - knot_w, b.y + eff_r * 0.95),
            QPointF(b.x + knot_w, b.y + eff_r * 0.95),
            QPointF(b.x, b.y + eff_r * 0.95 + knot_h * 1.5)
        ])

        # 3D Shaded Oval Body
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

        # Specular Gloss Reflection
        spec = QRadialGradient(b.x - eff_r * 0.35, b.y - eff_r * 0.40, eff_r * 0.45)
        spec.setColorAt(0.0, QColor(255, 255, 255, 210))
        spec.setColorAt(0.7, QColor(255, 255, 255, 45))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(spec))
        p.drawEllipse(QPointF(b.x - eff_r * 0.28, b.y - eff_r * 0.32), eff_r * 0.38, eff_r * 0.28)

        # Rim Light
        rim = QRadialGradient(b.x + eff_r * 0.5, b.y + eff_r * 0.5, eff_r * 0.5)
        rim.setColorAt(0.0, QColor(255, 255, 255, 55))
        rim.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(rim))
        p.drawEllipse(QPointF(b.x + eff_r * 0.42, b.y + eff_r * 0.38), eff_r * 0.32, eff_r * 0.32)

    def _draw_inflation_hud(self, p, b):
        is_blowing = self.mic.is_blowing
        fill_pct = int((b.r / Balloon.MAX_R) * 100)

        hud_w = 170
        hud_rect = QRectF(b.x - hud_w / 2, b.y - b.r - 50, hud_w, 34)

        bg_col = QColor(0, 145, 80, 225) if is_blowing else QColor(30, 30, 50, 210)
        p.setBrush(QBrush(bg_col))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawRoundedRect(hud_rect, 17, 17)

        txt = f"💨 Inflating: {fill_pct}%" if is_blowing else f"🎈 {fill_pct}% (Blow air into mic)"
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(hud_rect, Qt.AlignCenter, txt)

        hint_rect = QRectF(b.x - 90, b.y + b.r + 30, 180, 20)
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(240, 240, 255, 220))
        p.drawText(hint_rect, Qt.AlignCenter, "Enter / Space to Tie")

    # ---------- Mouse & Keyboard Interactions ----------
    def _find_balloon_at(self, px, py):
        if self.active_balloon and self.active_balloon.contains(px, py):
            return self.active_balloon

        for b in reversed(self.floating_balloons):
            if b.contains(px, py):
                return b

        return None

    def mousePressEvent(self, e):
        b = self._find_balloon_at(e.x(), e.y())
        if e.button() == Qt.LeftButton:
            if b:
                self.dragged_balloon = b
                self.drag_offset_x = b.x - e.x()
                self.drag_offset_y = b.y - e.y()
                self.last_mouse_pos = (e.x(), e.y())
                self.mouse_velocity = (0.0, 0.0)

                self.setCursor(QCursor(Qt.ClosedHandCursor))
                self.clearMask()

        elif e.button() == Qt.RightButton:
            self._show_context_menu(b, e.globalPos())

        self.setFocus()

    def mouseMoveEvent(self, e):
        pos = (e.x(), e.y())

        if self.dragged_balloon:
            b = self.dragged_balloon
            if self.last_mouse_pos:
                dx = e.x() - self.last_mouse_pos[0]
                dy = e.y() - self.last_mouse_pos[1]
                self.mouse_velocity = (
                    0.7 * self.mouse_velocity[0] + 0.3 * dx,
                    0.7 * self.mouse_velocity[1] + 0.3 * dy
                )

                # Friction rub when tied -> pop!
                if b.state == 'tied':
                    dist = math.hypot(dx, dy)
                    if dist > 3:
                        b.rub_score += dist
                        if random.random() < 0.35:
                            play_rub()
                        if b.rub_score > Balloon.POP_THRESHOLD:
                            self._trigger_pop(b)
                            self.dragged_balloon = None

            if b and b.state != 'popped':
                b.x = float(e.x() + self.drag_offset_x)
                b.y = float(e.y() + self.drag_offset_y)

        else:
            hover_b = self._find_balloon_at(e.x(), e.y())
            if hover_b:
                self.setCursor(QCursor(Qt.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))

        self.last_mouse_pos = pos

    def mouseReleaseEvent(self, e):
        if self.dragged_balloon:
            b = self.dragged_balloon
            self.dragged_balloon = None
            self.setCursor(QCursor(Qt.ArrowCursor))

            # Fling physics when released!
            if b.state == 'tied':
                b.vx = float(np.clip(self.mouse_velocity[0] * 1.25, -35.0, 35.0))
                b.vy = float(np.clip(self.mouse_velocity[1] * 1.25, -35.0, 35.0))

            elif b.state == 'held':
                if b.r > 15:
                    b.state = 'deflating'
                    play_hiss()
                else:
                    b.state = 'idle'

            self._update_window_mask()

    def keyPressEvent(self, e):
        # Tie current active balloon on Enter or Space
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self.active_balloon and self.active_balloon.r > 12:
                play_tie_squeak()
                self._advance_to_next_balloon()

        # Pop all balloons shortcut
        elif e.key() == Qt.Key_P:
            self._pop_all_floating()

        # Escape closes app
        elif e.key() == Qt.Key_Escape:
            self.close()

    def _trigger_pop(self, b):
        b.state = 'popped'
        play_pop()
        self.particles.extend([Particle(b.x, b.y, b.color) for _ in range(40)])

    def _pop_all_floating(self):
        for b in list(self.floating_balloons):
            self._trigger_pop(b)

    def _show_context_menu(self, b, global_pos):
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

        if b and b.state == 'tied':
            pop_act = QAction(f"💥 Pop This {b.name} Balloon", self)
            pop_act.triggered.connect(lambda: self._trigger_pop(b))
            menu.addAction(pop_act)

            color_menu = menu.addMenu("🎨 Change Balloon Color")
            for style in BALLOON_STYLES:
                act = QAction(style["name"], self)
                act.triggered.connect(lambda _, c=style["color"], n=style["name"]: self._change_color(b, c, n))
                color_menu.addAction(act)

            menu.addSeparator()

        if self.floating_balloons:
            pop_all_act = QAction("💥 Pop All Floating Balloons (P)", self)
            pop_all_act.triggered.connect(self._pop_all_floating)
            menu.addAction(pop_all_act)

        new_b_act = QAction("🎈 Give New Random Balloon", self)
        new_b_act.triggered.connect(self._spawn_next_balloon)
        menu.addAction(new_b_act)

        menu.addSeparator()

        settings_act = QAction("⚙️ Microphone & Sound Settings", self)
        settings_act.triggered.connect(self._open_settings_dialog)
        menu.addAction(settings_act)

        exit_act = QAction("❌ Exit (Esc)", self)
        exit_act.triggered.connect(self.close)
        menu.addAction(exit_act)

        menu.exec_(global_pos)

    def _open_settings_dialog(self):
        dlg = SetupDialog()
        if dlg.exec_() == QDialog.Accepted:
            dev = dlg.chosen_device()
            sens = dlg.chosen_sensitivity()
            self.mic.close()
            self.mic = MicListener(dev, sensitivity=sens)

    def _change_color(self, b, color, name):
        b.color = color
        b.name = name

    def closeEvent(self, e):
        self.timer.stop()
        self.mic.close()
        super().closeEvent(e)


# ---- Helper to Auto-Detect Best Microphone / Headset ----
def get_best_input_device():
    try:
        devices = sd.query_devices()
        try:
            default_dev = sd.default.device[0]
        except Exception:
            default_dev = None
    except Exception:
        return None

    # Check for Bluetooth headphones or wireless headsets first (AirPods, etc.)
    for i, dev in enumerate(devices):
        if dev.get('max_input_channels', 0) <= 0:
            continue
        try:
            hostapi = sd.query_hostapis(dev['hostapi'])
            if 'WDM-KS' in hostapi.get('name', ''):
                continue
        except Exception:
            pass
        name = dev.get('name', '').lower()
        if any(k in name for k in ['headset', 'airpod', 'bud', 'bluetooth', 'wireless', 'hands-free']):
            return i

    return default_dev


# ---- Entry Point ----
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 1. Microphone & Headset selection dialog
    dialog = SetupDialog()
    if dialog.exec_() != QDialog.Accepted:
        sys.exit(0)

    device_index = dialog.chosen_device()
    sensitivity  = dialog.chosen_sensitivity()

    # 2. Launch overlay with random balloons ready to blow one after another
    w = Overlay(device_index=device_index, sensitivity=sensitivity)
    w.show()
    sys.exit(app.exec_())

