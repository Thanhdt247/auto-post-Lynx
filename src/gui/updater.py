import os
import sys
import json
import zipfile
import shutil
import requests
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QApplication, QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor
from qfluentwidgets import (FluentIcon, SubtitleLabel, BodyLabel, TitleLabel,
                            ProgressBar, PushButton, PrimaryPushButton)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from version import APP_VERSION as CURRENT_VERSION
UPDATE_URL = "https://raw.githubusercontent.com/Thanhdt247/auto-post-Lynx/main/version.json"

def is_dark_mode():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        config_path = os.path.join(base_dir, "user_data", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f).get("theme", "Dark") == "Dark"
    except: return True

# =======================================================
# DOWNLOAD & CHECK THREADS
# =======================================================
class DownloadUpdateThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str) 
    error_signal = pyqtSignal(str)

    def __init__(self, download_url):
        super().__init__()
        self.download_url = download_url

    def run(self):
        try:
            response = requests.get(self.download_url, stream=True, timeout=15)
            total_size = int(response.headers.get('content-length', 0))
            zip_name = "update_package.zip"
            downloaded = 0
            
            with open(zip_name, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            self.progress_signal.emit(int((downloaded / total_size) * 100))
                            
            temp_dir = "temp_update_extract"
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_name, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            os.remove(zip_name)
            
            self.finished_signal.emit(temp_dir)
        except Exception as e:
            self.error_signal.emit(str(e))

class CheckUpdateThread(QThread):
    check_finished_signal = pyqtSignal(dict)
    
    def run(self):
        result = {
            "has_update": False,
            "version": CURRENT_VERSION,
            "changelog": "✅ You are running the latest version.\nSystem is ready to launch.",
            "download_url": ""
        }
        try:
            response = requests.get(UPDATE_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("version") and data.get("version") != CURRENT_VERSION:
                    result.update({"has_update": True, "version": data.get("version"), 
                                   "changelog": data.get("changelog"), "download_url": data.get("download_url")})
        except: 
            result["changelog"] = "⚠️ Could not connect to update server.\nPlease check your Internet connection!"
        self.check_finished_signal.emit(result)

# =======================================================
# MODERN ENGLISH LAUNCHER UI
# =======================================================
class LauncherWindow(QWidget):
    def __init__(self):
        super().__init__()
        # Khử viền và làm nền trong suốt để tạo hiệu ứng đổ bóng
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 380)

        # Khung Container chính
        self.container = QWidget(self)
        self.container.setGeometry(15, 15, 570, 350)
        
        # Thêm hiệu ứng Shadow đổ bóng 3D cực ngầu
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        self.container.setGraphicsEffect(shadow)
        
        dark = is_dark_mode()
        bg_color = "#1e1e1e" if dark else "#ffffff"
        text_color = "white" if dark else "black"
        border_color = "#333333" if dark else "#e5e5e5"
        
        self.container.setStyleSheet(f"""
            QWidget#launcher_container {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 1px solid {border_color};
                color: {text_color};
            }}
        """)
        self.container.setObjectName("launcher_container")

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.setSpacing(15)

        self.titleLabel = TitleLabel("Starting Lynx Bot...", self.container)
        layout.addWidget(self.titleLabel)

        self.versionLabel = BodyLabel("Connecting to servers...", self.container)
        layout.addWidget(self.versionLabel)

        self.changelogLabel = BodyLabel("", self.container)
        self.changelogLabel.setStyleSheet("color: gray;")
        self.changelogLabel.setWordWrap(True)
        layout.addWidget(self.changelogLabel)
        
        self.progressBar = ProgressBar(self.container)
        self.progressBar.setRange(0, 100)
        self.progressBar.hide()
        layout.addWidget(self.progressBar)

        self.statusLabel = BodyLabel("", self.container)
        self.statusLabel.hide()
        layout.addWidget(self.statusLabel)

        layout.addStretch(1)

        # Nhóm Nút Bấm (Buttons)
        self.btnLayout = QHBoxLayout()
        self.btnLayout.setSpacing(12)
        
        self.btn_run = PushButton(FluentIcon.PLAY, "Launch", self.container)
        self.btn_run.clicked.connect(self.launch_main_app)
        self.btn_run.hide()
        
        self.btn_update = PrimaryPushButton(FluentIcon.DOWNLOAD, "Update", self.container)
        self.btn_update.clicked.connect(self.start_download)
        self.btn_update.hide()
        
        self.btn_cancel = PushButton(FluentIcon.CLOSE, "Cancel", self.container)
        self.btn_cancel.clicked.connect(self.launch_main_app)
        self.btn_cancel.hide()
        
        self.btn_exit = PushButton(FluentIcon.POWER_BUTTON, "Exit", self.container)
        self.btn_exit.clicked.connect(sys.exit)
        
        self.btnLayout.addStretch(1)
        self.btnLayout.addWidget(self.btn_run)
        self.btnLayout.addWidget(self.btn_update)
        self.btnLayout.addWidget(self.btn_cancel)
        self.btnLayout.addWidget(self.btn_exit)

        layout.addLayout(self.btnLayout)
        self.center_window()

        self.check_thread = CheckUpdateThread()
        self.check_thread.check_finished_signal.connect(self.on_check_finished)
        self.check_thread.start()

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def on_check_finished(self, data):
        self.download_url = data.get('download_url', '')
        has_update = data.get('has_update', False)
        new_version = data.get('version', CURRENT_VERSION)
        
        if has_update:
            self.titleLabel.setText("🚀 New Update Available!")
            self.versionLabel.setText(f"Current: v{CURRENT_VERSION}  ➡️  New: v{new_version}")
            self.versionLabel.setStyleSheet("color: #10b981; font-weight: bold; font-size: 15px;")
            self.btn_update.show()
            self.btn_cancel.show()
        else:
            self.titleLabel.setText("Lynx Bot System Launcher")
            self.versionLabel.setText(f"Current Version: v{CURRENT_VERSION}")
            self.versionLabel.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 15px;")
            self.btn_run.show()
            
        self.changelogLabel.setText(f"Changelog:\n{data.get('changelog', '')}")

    def start_download(self):
        self.btn_update.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progressBar.show()
        self.statusLabel.show()
        self.statusLabel.setText("Downloading update data... Please do not close!")
        
        self.downloader = DownloadUpdateThread(self.download_url)
        self.downloader.progress_signal.connect(self.progressBar.setValue)
        self.downloader.finished_signal.connect(self.on_download_finished)
        self.downloader.error_signal.connect(self.on_download_error)
        self.downloader.start()
        
    def on_download_finished(self, temp_dir):
        self.statusLabel.setText("Download completed! Restarting application...")
        self.statusLabel.setStyleSheet("color: #10b981; font-weight: bold;")
        
        if getattr(sys, 'frozen', False):
            current_exe = os.path.basename(sys.executable)
            bat_content = f"""@echo off
timeout /t 2 /nobreak > NUL
:loop
taskkill /f /im "{current_exe}" >nul 2>&1
xcopy /s /e /y "{temp_dir}\\*" "." >nul 2>&1
if errorlevel 1 goto loop

rd /s /q "{temp_dir}"
start "" "{current_exe}" 
del "%~f0"
"""
            with open("update.bat", "w", encoding="utf-8") as f:
                f.write(bat_content)
            subprocess.Popen(["update.bat"], shell=True)
            sys.exit() 
        else:
            self.statusLabel.setText("Extraction successful (Developer Mode).")
            self.btn_run.show()
            self.btn_run.setEnabled(True)
            self.btn_update.hide()
            self.btn_cancel.hide()
            
    def on_download_error(self, err):
        self.statusLabel.setText(f"Download failed: {err}")
        self.statusLabel.setStyleSheet("color: #ef4444;")
        self.btn_update.setEnabled(True)
        self.btn_cancel.setEnabled(True)

    def launch_main_app(self):
        # 🌟 CỰC KỲ QUAN TRỌNG: Chỉ khi bấm Launch thì Main Window mới được gọi ra!
        self.close() 
        from src.gui.main_window import AutoPostApp
        self.main_app = AutoPostApp()
        self.main_app.show()