import os
import sys
import json
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor
from qfluentwidgets import (LineEdit, PrimaryPushButton, TransparentPushButton, InfoBar, 
                            InfoBarPosition, TitleLabel, BodyLabel, setTheme, Theme, FluentIcon,
                            TransparentToolButton) # Bổ sung TransparentToolButton
from src.core.license_manager import login_user, register_user

def get_auth_path():
    base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.makedirs(os.path.join(base_dir, "user_data"), exist_ok=True)
    return os.path.join(base_dir, "user_data", "auth.json")

def is_dark_mode():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        with open(os.path.join(base_dir, "user_data", "config.json"), 'r') as f:
            return json.load(f).get("theme", "Dark") == "Dark"
    except: return True

class AuthThread(QThread):
    result_signal = pyqtSignal(bool, str, object)
    def __init__(self, mode, user, pwd):
        super().__init__()
        self.mode, self.user, self.pwd = mode, user, pwd
    def run(self):
        if self.mode == "login":
            is_valid, msg, data = login_user(self.user, self.pwd)
            self.result_signal.emit(is_valid, msg, data)
        else:
            is_valid, msg = register_user(self.user, self.pwd)
            self.result_signal.emit(is_valid, msg, None)

class LicenseWindow(QWidget):
    login_success = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(500, 480)
        
        self.container = QWidget(self)
        self.container.setGeometry(15, 15, 470, 450)
        
        # 🔥 FIX: THÊM NÚT TẮT (X) TRÊN CÙNG BÊN PHẢI 🔥
        self.btn_close = TransparentToolButton(FluentIcon.CLOSE, self.container)
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.move(self.container.width() - 36, 10) 
        self.btn_close.clicked.connect(sys.exit) # Bấm vào là thoát sạch ứng dụng
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)
        
        dark = is_dark_mode()
        self.container.setStyleSheet(f"QWidget#login_container {{ background-color: {'#272727' if dark else '#F9F9F9'}; border-radius: 12px; border: 1px solid {'#323232' if dark else '#E5E5E5'}; }}")
        self.container.setObjectName("login_container")
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 35, 40, 35)
        layout.setSpacing(15)
        
        self.title_lbl = TitleLabel("Đăng nhập Hệ thống", self.container)
        layout.addWidget(self.title_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.sub_lbl = BodyLabel("Xác thực người dùng Lynx Bot", self.container)
        self.sub_lbl.setStyleSheet("color: gray;")
        layout.addWidget(self.sub_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        layout.addSpacing(10)
        
        self.username_input = LineEdit(self.container)
        self.username_input.setPlaceholderText("Tên đăng nhập...")
        layout.addWidget(self.username_input)

        self.password_input = LineEdit(self.container)
        self.password_input.setPlaceholderText("Mật khẩu...")
        self.password_input.setEchoMode(LineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)
        
        self.repassword_input = LineEdit(self.container)
        self.repassword_input.setPlaceholderText("Nhập lại Mật khẩu...")
        self.repassword_input.setEchoMode(LineEdit.EchoMode.Password)
        self.repassword_input.hide() 
        layout.addWidget(self.repassword_input)
        
        try:
            if os.path.exists(get_auth_path()):
                with open(get_auth_path(), 'r') as f:
                    self.username_input.setText(json.load(f).get("username", ""))
        except: pass
        
        layout.addStretch(1)
        
        self.btn_switch = TransparentPushButton("Chưa có tài khoản? Đăng ký ngay", self.container)
        self.btn_switch.clicked.connect(self.toggle_mode)
        layout.addWidget(self.btn_switch)
        
        btn_layout = QHBoxLayout()
        self.btn_action = PrimaryPushButton(FluentIcon.PEOPLE, "Đăng nhập", self.container)
        self.btn_action.clicked.connect(self.submit_action)
        btn_layout.addWidget(self.btn_action, stretch=1)
        layout.addLayout(btn_layout)
        
        self.is_login_mode = True

    def toggle_mode(self):
        self.is_login_mode = not self.is_login_mode
        if self.is_login_mode:
            self.title_lbl.setText("Đăng nhập Hệ thống")
            self.repassword_input.hide()
            self.btn_action.setText("Đăng nhập")
            self.btn_switch.setText("Chưa có tài khoản? Đăng ký ngay")
        else:
            self.title_lbl.setText("Đăng ký Tài khoản")
            self.repassword_input.show()
            self.btn_action.setText("Tạo tài khoản")
            self.btn_switch.setText("Đã có tài khoản? Quay lại Đăng nhập")

    def submit_action(self):
        u, p = self.username_input.text().strip(), self.password_input.text().strip()
        
        if not u or not p:
            InfoBar.warning("Cảnh báo", "Vui lòng nhập đủ thông tin!", parent=self, position=InfoBarPosition.TOP)
            return
            
        if len(u) < 4:
            InfoBar.warning("Cảnh báo", "Tên đăng nhập phải từ 4 ký tự trở lên!", parent=self, position=InfoBarPosition.TOP)
            return
            
        if len(p) < 6:
            InfoBar.warning("Cảnh báo", "Mật khẩu phải từ 6 ký tự trở lên!", parent=self, position=InfoBarPosition.TOP)
            return
            
        if not self.is_login_mode and p != self.repassword_input.text().strip():
            InfoBar.warning("Lỗi", "Mật khẩu nhập lại không khớp!", parent=self, position=InfoBarPosition.TOP)
            return
            
        self.btn_action.setEnabled(False)
        self.thread = AuthThread("login" if self.is_login_mode else "register", u, p)
        self.thread.result_signal.connect(self.on_result)
        self.thread.start()

    def on_result(self, is_valid, msg, data):
        self.btn_action.setEnabled(True)
        if is_valid:
            if self.is_login_mode:
                try:
                    with open(get_auth_path(), 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
                except: pass
                self.login_success.emit()
                self.close()
            else:
                InfoBar.success("Thành công", msg, parent=self, position=InfoBarPosition.TOP)
                self.toggle_mode() 
        else:
            InfoBar.error("Thất bại", msg, parent=self, position=InfoBarPosition.TOP)