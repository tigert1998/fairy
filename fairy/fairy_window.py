import queue
import threading

import soundfile as sf
import sounddevice as sd
from PyQt6.QtWidgets import QMainWindow, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QMovie, QImage, QKeyEvent


class FairyWindow(QMainWindow):
    def __init__(self, ratio, device, quit_callback):
        super().__init__()

        # UI
        fairy_gif = "./resources/fairy.gif"
        self.movie = QMovie(fairy_gif)
        size = QImage(fairy_gif).size()
        width, height = int(size.width() * ratio), int(size.height() * ratio)
        self.movie.setScaledSize(QSize(width, height))
        self.label = QLabel()
        self.label.setMovie(self.movie)
        self.setGeometry(
            100, 100, self.movie.scaledSize().width(), self.movie.scaledSize().height()
        )
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setCentralWidget(self.label)
        self.movie.start()

        # Quit
        self.quit_callback = quit_callback
        self.is_quitted = False

        # Recording
        self.start_record_condition = threading.Condition()
        self.stop_record_lock = threading.Lock()
        self.device = device
        device_info = sd.query_devices(self.device, "input")
        self.samplerate = int(device_info["default_samplerate"])
        self.channels = 1
        self.q = queue.Queue()

    def keyReleaseEvent(self, event):
        if isinstance(event, QKeyEvent):
            if event.isAutoRepeat():
                return
            if event.key() == Qt.Key.Key_Space:
                with self.stop_record_lock:
                    self.stop_record = True

    def keyPressEvent(self, event):
        if isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Space:
                with self.start_record_condition:
                    self.start_record = True
                    self.start_record_condition.notify()
            elif event.key() == Qt.Key.Key_Q:
                self.is_quitted = True
                with self.stop_record_lock:
                    self.stop_record = True
                with self.start_record_condition:
                    self.start_record = True
                    self.start_record_condition.notify()
                self.quit_callback()

    def _callback(self, indata, frames, time, status):
        self.q.put(indata.copy())

    def record(self, record_output_path):
        # This function must be called in non-UI thread
        self.start_record = False
        self.stop_record = False

        with self.start_record_condition:
            while not self.start_record:
                self.start_record_condition.wait()

        if self.is_quitted:
            return

        with sf.SoundFile(
            record_output_path,
            mode="w",
            samplerate=self.samplerate,
            channels=self.channels,
            subtype="PCM_24",
        ) as file:
            with sd.InputStream(
                samplerate=self.samplerate,
                device=self.device,
                channels=self.channels,
                callback=self._callback,
            ):
                while True:
                    with self.stop_record_lock:
                        if self.stop_record:
                            break
                    file.write(self.q.get())
