import os
import sys
import json
from datetime import datetime
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem, 
                             QTextEdit, QGroupBox, QFileDialog) 
from qfluentwidgets import (FluentWindow, FluentIcon, NavigationItemPosition,
                            TextEdit, PlainTextEdit, PrimaryPushButton, PushButton, InfoBar, 
                            SubtitleLabel, ListWidget, LineEdit, SpinBox, 
                            SwitchButton, ComboBox, setTheme, Theme, BodyLabel, 
                            isDarkTheme, IconWidget)

from src.core.bot_thread import PosterThread, LoginThread, LogoutThread, FetchDataThread
from src.core.license_manager import activate_license

DEFAULT_AI_PROMPT = """Bạn là một chuyên gia Copywriter bán hàng lão luyện trên Facebook. 
Nhiệm vụ của bạn là xào (spin) lại đoạn văn bản dưới đây để tạo ra một bài đăng mới mẻ, thu hút, lách thuật toán quét Spam của Facebook.

LUẬT BẮT BUỘC:
1. TUYỆT ĐỐI GIỮ NGUYÊN 100% các dữ liệu cốt lõi: Tên người, SĐT, Giá tiền, Diện tích, Địa chỉ, Hashtag, Link.
2. BẠN CHỈ ĐƯỢC PHÉP làm mới câu từ ở phần Mở bài, thêm thắt Emoji.
3. KHÔNG dùng các câu mào đầu của AI.

Văn bản gốc:
{original_text}"""

def get_config_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.makedirs(os.path.join(base_dir, "user_data"), exist_ok=True)
    return os.path.join(base_dir, "user_data", "config.json")

def get_auth_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_dir, "user_data", "auth.json")

def load_auth_info():
    try:
        if os.path.exists(get_auth_path()):
            with open(get_auth_path(), 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return {}

def load_settings():
    settings = {"api_key": "", "use_ai_spin": False, "ai_spin_prompt": DEFAULT_AI_PROMPT, "delay_min": 10, "delay_max": 30, "headless": False, "theme": "Dark"}
    try:
        if os.path.exists(get_config_path()):
            with open(get_config_path(), 'r', encoding='utf-8') as f: settings.update(json.load(f))
    except: pass
    return settings

def save_settings_to_file(data):
    try:
        with open(get_config_path(), 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=4)
    except: pass

def load_api_key():
    return load_settings().get('api_key', '')

# --- FIX MÀU: Đã thêm kiểm tra chế độ Sáng/Tối trực tiếp ---
def apply_gb_style(groupboxes, is_dark=None):
    if is_dark is None:
        is_dark = load_settings().get("theme", "Dark") == "Dark"
        
    text_color = 'white' if is_dark else 'black'
    border_color = '#30363d' if is_dark else '#dcdcdc'
    
    style = f"""
        QGroupBox {{ border: 1px solid {border_color}; border-radius: 8px; margin-top: 15px; padding-top: 15px; font-weight: bold; color: {text_color}; }}
        QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; color: {text_color}; }}
    """
    for gb in groupboxes: gb.setStyleSheet(style)


class ActivateKeyThread(QThread):
    result = pyqtSignal(bool, str, object)
    def __init__(self, user, key):
        super().__init__()
        self.user, self.key = user, key
    def run(self):
        success, msg, data = activate_license(self.user, self.key)
        self.result.emit(success, msg, data)


# ==========================================
# CÁC COMPONENT GIAO DIỆN CHÍNH
# ==========================================
class TerminalInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("TerminalInterface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(SubtitleLabel("System Terminal", self))
        self.console = QTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setStyleSheet("QTextEdit { background-color: #0d1117; color: #10b981; font-family: 'Consolas', monospace; font-size: 14px; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }")
        layout.addWidget(self.console)
        self.log_message("Hệ thống Lynx Bot đã khởi động.")
    def log_message(self, message):
        self.console.append(f"> {message}")
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

class FeaturesInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("FeaturesInterface")
        self.parent_window = parent
        self.image_paths, self.groupboxes = [], []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        control_layout = QHBoxLayout()
        self.btn_login = PushButton(FluentIcon.PEOPLE, "Đăng nhập FB", self)
        self.btn_login.clicked.connect(self.login_fb)
        self.btn_fetch = PushButton(FluentIcon.SYNC, "Tải danh sách", self)
        self.btn_fetch.clicked.connect(self.fetch_data)
        self.btn_logout = PushButton(FluentIcon.CLOSE, "Đăng xuất FB", self)
        self.btn_logout.clicked.connect(self.logout_fb)
        control_layout.addWidget(self.btn_login); control_layout.addWidget(self.btn_fetch); control_layout.addWidget(self.btn_logout); control_layout.addStretch(1)
        layout.addLayout(control_layout)

        list_layout = QHBoxLayout()
        self.group_box = QGroupBox("Danh sách Nhóm")
        group_layout = QVBoxLayout()
        group_top_layout = QHBoxLayout()
        self.search_group_input = LineEdit(self)
        self.search_group_input.setPlaceholderText("Tìm kiếm nhóm...")
        self.search_group_input.textChanged.connect(self.filter_groups)
        self.btn_select_all = PushButton(FluentIcon.ACCEPT, "Chọn tất cả", self)
        self.btn_select_all.clicked.connect(self.select_all_groups)
        self.btn_deselect_all = PushButton(FluentIcon.CLOSE, "Bỏ chọn", self)
        self.btn_deselect_all.clicked.connect(self.deselect_all_groups)
        group_top_layout.addWidget(self.search_group_input, stretch=2); group_top_layout.addWidget(self.btn_select_all); group_top_layout.addWidget(self.btn_deselect_all)
        group_layout.addLayout(group_top_layout)
        self.list_groups = ListWidget(self)
        group_layout.addWidget(self.list_groups)
        self.group_box.setLayout(group_layout)
        
        self.page_box = QGroupBox("Danh sách Page")
        page_layout = QVBoxLayout()
        self.list_pages = ListWidget(self)
        page_layout.addWidget(self.list_pages)
        self.page_box.setLayout(page_layout)

        self.groupboxes.extend([self.group_box, self.page_box])
        list_layout.addWidget(self.group_box); list_layout.addWidget(self.page_box)
        layout.addLayout(list_layout, stretch=2)

        img_layout = QHBoxLayout()
        self.btn_select_image = PushButton(FluentIcon.PHOTO, "Chọn Ảnh/Video", self)
        self.btn_select_image.clicked.connect(self.select_images)
        self.lbl_images = BodyLabel("Chưa chọn file nào", self)
        img_layout.addWidget(self.btn_select_image); img_layout.addWidget(self.lbl_images, stretch=1)
        layout.addLayout(img_layout)

        self.content_input = PlainTextEdit(self)
        self.content_input.setPlaceholderText("Nhập nội dung bài viết...")
        layout.addWidget(self.content_input, stretch=1)

        self.btn_run = PrimaryPushButton(FluentIcon.SEND, "Khởi động AutoPost", self)
        self.btn_run.clicked.connect(self.start_posting)
        layout.addWidget(self.btn_run)
        
        self.update_styles()
        self.check_license_lock()

    def check_license_lock(self):
        auth = load_auth_info()
        status = auth.get("status", "").lower()
        is_valid = False
        try:
            expiry = datetime.strptime(auth.get("expiry_date", "2000-01-01"), "%Y-%m-%d")
            if status == "active" and datetime.now() <= expiry:
                is_valid = True
        except: pass

        self.btn_login.setEnabled(is_valid)
        self.btn_fetch.setEnabled(is_valid)
        self.btn_logout.setEnabled(is_valid)
        self.search_group_input.setEnabled(is_valid)
        self.btn_select_all.setEnabled(is_valid)
        self.btn_deselect_all.setEnabled(is_valid)
        self.list_groups.setEnabled(is_valid)
        self.list_pages.setEnabled(is_valid)
        self.btn_select_image.setEnabled(is_valid)
        self.content_input.setEnabled(is_valid)
        
        if not is_valid:
            self.btn_run.setEnabled(False)
            self.btn_run.setText("⛔ TÀI KHOẢN CHƯA KÍCH HOẠT HOẶC HẾT HẠN")
            self.content_input.setPlaceholderText("Tính năng đã bị khóa. Vui lòng sang tab Cài đặt để nạp Key!")
        else:
            self.btn_run.setEnabled(True)
            self.btn_run.setText("Khởi động AutoPost")
            self.content_input.setPlaceholderText("Nhập nội dung bài viết. Tool sẽ giữ nguyên 100% văn bản của bạn và gõ phím như người thật...")

    def update_styles(self, is_dark=None): apply_gb_style(self.groupboxes, is_dark)
    def log_to_terminal(self, msg): self.parent_window.terminal_interface.log_message(msg)

    def filter_groups(self, text):
        for i in range(self.list_groups.count()):
            item = self.list_groups.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def select_all_groups(self):
        for i in range(self.list_groups.count()):
            if not self.list_groups.item(i).isHidden(): self.list_groups.item(i).setCheckState(Qt.CheckState.Checked)

    def deselect_all_groups(self):
        for i in range(self.list_groups.count()):
            if not self.list_groups.item(i).isHidden(): self.list_groups.item(i).setCheckState(Qt.CheckState.Unchecked)

    def select_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn Ảnh/Video", "", "Image/Video Files (*.png *.jpg *.jpeg *.mp4 *.avi)")
        if files:
            self.image_paths = files
            self.lbl_images.setText(f"Đã chọn {len(files)} file đính kèm.")
            self.lbl_images.setStyleSheet("color: #10b981; font-weight: bold;") 
        else:
            self.image_paths = []
            self.lbl_images.setText("Chưa chọn file nào")
            self.lbl_images.setStyleSheet("")

    def login_fb(self):
        self.btn_login.setEnabled(False)
        self.login_thread = LoginThread()
        self.login_thread.finished_signal.connect(lambda m: self._on_done(self.btn_login, m))
        self.login_thread.error_signal.connect(self.on_error)
        self.login_thread.start()

    def logout_fb(self):
        self.btn_logout.setEnabled(False)
        self.logout_thread = LogoutThread()
        self.logout_thread.finished_signal.connect(lambda m: self._on_done(self.btn_logout, m))
        self.logout_thread.error_signal.connect(self.on_error)
        self.logout_thread.start()

    def fetch_data(self):
        self.btn_fetch.setEnabled(False)
        self.list_groups.clear(); self.list_pages.clear()
        self.fetch_thread = FetchDataThread(load_api_key())
        self.fetch_thread.log_signal.connect(self.log_to_terminal) 
        self.fetch_thread.finished_signal.connect(self.on_fetch_success)
        self.fetch_thread.error_signal.connect(self.on_error)
        self.fetch_thread.start()

    def on_fetch_success(self, data):
        self.btn_fetch.setEnabled(True)
        for group in data["groups"]:
            item = QListWidgetItem(group['name'])
            item.setData(Qt.ItemDataRole.UserRole, group['url'])
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_groups.addItem(item)
        for page in data["pages"]:
            item = QListWidgetItem(page['name'])
            item.setData(Qt.ItemDataRole.UserRole, page['url'])
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_pages.addItem(item)
        self.log_to_terminal(f"Quét xong: {len(data['groups'])} Nhóm, {len(data['pages'])} Page.")

    def start_posting(self):
        urls = [self.list_groups.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_groups.count()) if self.list_groups.item(i).checkState() == Qt.CheckState.Checked]
        urls += [self.list_pages.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_pages.count()) if self.list_pages.item(i).checkState() == Qt.CheckState.Checked]

        content = self.content_input.toPlainText().strip()
        if not urls or not content:
            InfoBar.warning('Cảnh báo', 'Cần chọn ít nhất 1 nơi đăng và nhập nội dung!', parent=self)
            return

        self.btn_run.setEnabled(False)
        self.post_thread = PosterThread(urls, content, self.image_paths)
        self.post_thread.log_signal.connect(self.log_to_terminal)
        self.post_thread.finished_signal.connect(lambda m: self._on_done(self.btn_run, m))
        self.post_thread.error_signal.connect(self.on_error)
        self.post_thread.start()

    def _on_done(self, btn, msg):
        btn.setEnabled(True)
        self.log_to_terminal(msg)
        InfoBar.success('Hoàn tất', msg, parent=self)

    def on_error(self, error_message):
        self.btn_fetch.setEnabled(True); self.btn_login.setEnabled(True); self.btn_run.setEnabled(True)
        self.log_to_terminal(f"LỖI: {error_message}")
        InfoBar.error('Lỗi', error_message, parent=self)


class SettingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent_window = parent
        self.groupboxes = []
        self.setObjectName("SettingInterface")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.current_settings = load_settings()
        layout.addWidget(SubtitleLabel("Cài đặt & Quản lý Hệ thống", self), alignment=Qt.AlignmentFlag.AlignTop)

        # ===============================================
        # 1. BẢNG QUẢN LÝ BẢN QUYỀN
        # ===============================================
        self.license_box = QGroupBox("1. Quản lý Tài khoản & Bản quyền")
        license_layout = QVBoxLayout()
        license_layout.setSpacing(15)
        license_layout.setContentsMargins(20, 25, 20, 20)
        
        info_layout = QHBoxLayout()
        self.icon_user = IconWidget(FluentIcon.PEOPLE, self)
        self.icon_user.setFixedSize(18, 18)
        self.lbl_user = BodyLabel(self)
        self.lbl_user.setTextFormat(Qt.TextFormat.RichText)
        
        self.icon_status = IconWidget(FluentIcon.CERTIFICATE, self) 
        self.icon_status.setFixedSize(18, 18)
        self.lbl_status = BodyLabel(self)
        self.lbl_status.setTextFormat(Qt.TextFormat.RichText)
        
        info_layout.addWidget(self.icon_user)
        info_layout.addWidget(self.lbl_user)
        info_layout.addSpacing(30)
        info_layout.addWidget(self.icon_status)
        info_layout.addWidget(self.lbl_status)
        info_layout.addStretch(1)
        
        license_layout.addLayout(info_layout)
        self.refresh_auth_ui()
        
        key_input_layout = QHBoxLayout()
        self.key_input = LineEdit(self)
        self.key_input.setPlaceholderText("Nhập mã Key mua từ Admin để gia hạn hoặc kích hoạt...")
        self.key_input.setClearButtonEnabled(True)
        
        self.btn_activate = PrimaryPushButton(FluentIcon.TAG, "Kích hoạt Key", self)
        self.btn_activate.clicked.connect(self.activate_key)
        
        key_input_layout.addWidget(self.key_input, stretch=1)
        key_input_layout.addWidget(self.btn_activate)
        license_layout.addLayout(key_input_layout)
        
        self.license_box.setLayout(license_layout)
        layout.addWidget(self.license_box)

        # ===============================================
        # 2. CẤU HÌNH TRÍ TUỆ NHÂN TẠO
        # ===============================================
        self.api_box = QGroupBox("2. Trí tuệ nhân tạo (AI Gemini)")
        api_layout = QVBoxLayout()
        api_layout.setSpacing(10)
        api_layout.setContentsMargins(20, 25, 20, 20)
        
        api_inner = QHBoxLayout()
        api_inner.addWidget(BodyLabel("Mã API Key:", self))
        self.api_input = LineEdit(self)
        self.api_input.setEchoMode(LineEdit.EchoMode.Password)
        self.api_input.setText(self.current_settings.get("api_key", "")) 
        api_inner.addWidget(self.api_input, stretch=1)
        api_layout.addLayout(api_inner)
        
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(BodyLabel("Bật AI Spin nội dung:", self))
        self.switch_ai_spin = SwitchButton(self)
        self.switch_ai_spin.setChecked(self.current_settings.get("use_ai_spin", False))
        spin_layout.addWidget(self.switch_ai_spin); spin_layout.addStretch(1)
        api_layout.addLayout(spin_layout)

        self.prompt_input = TextEdit(self)
        self.prompt_input.setText(self.current_settings.get("ai_spin_prompt", DEFAULT_AI_PROMPT))
        self.prompt_input.setMinimumHeight(100) 
        api_layout.addWidget(self.prompt_input)
        self.api_box.setLayout(api_layout)
        layout.addWidget(self.api_box)

        # ===============================================
        # 3. CẤU HÌNH HỆ THỐNG
        # ===============================================
        self.sys_box = QGroupBox("3. Cấu hình Hệ thống")
        sys_layout = QHBoxLayout()
        sys_layout.setContentsMargins(20, 25, 20, 20)
        
        sys_layout.addWidget(BodyLabel("Delay (Giây):", self))
        self.spin_delay_min = SpinBox(self); self.spin_delay_min.setValue(self.current_settings.get("delay_min", 10))
        self.spin_delay_max = SpinBox(self); self.spin_delay_max.setValue(self.current_settings.get("delay_max", 30))
        sys_layout.addWidget(self.spin_delay_min); sys_layout.addWidget(BodyLabel("-", self)); sys_layout.addWidget(self.spin_delay_max)
        
        sys_layout.addSpacing(20)
        sys_layout.addWidget(BodyLabel("Chạy ngầm:", self))
        self.switch_headless = SwitchButton(self)
        self.switch_headless.setChecked(self.current_settings.get("headless", False))
        sys_layout.addWidget(self.switch_headless)

        sys_layout.addSpacing(20)
        sys_layout.addWidget(BodyLabel("Giao diện:", self))
        self.combo_theme = ComboBox(self)
        self.combo_theme.addItems(["Tối (Dark)", "Sáng (Light)"])
        self.combo_theme.setCurrentIndex(0 if self.current_settings.get("theme", "Dark") == "Dark" else 1)
        
        # --- FIX MÀU: Ép thay đổi màu ngay khi gạt công tắc ---
        self.combo_theme.currentIndexChanged.connect(self.change_theme_and_style)
        
        sys_layout.addWidget(self.combo_theme)
        
        sys_layout.addStretch(1)
        self.sys_box.setLayout(sys_layout)
        layout.addWidget(self.sys_box)

        self.groupboxes.extend([self.license_box, self.api_box, self.sys_box])
        self.update_styles()

        layout.addStretch(1)
        self.btn_save = PrimaryPushButton(FluentIcon.SAVE, "Lưu toàn bộ cài đặt", self)
        self.btn_save.clicked.connect(self.save_all_settings)
        layout.addWidget(self.btn_save, alignment=Qt.AlignmentFlag.AlignRight)

    # --- HÀM MỚI: Xử lý thay đổi giao diện động ---
    def change_theme_and_style(self, index):
        is_dark = (index == 0)
        setTheme(Theme.DARK if is_dark else Theme.LIGHT)
        
        # Cập nhật màu chữ cho Setting Tab
        self.update_styles(is_dark)
        
        # Gọi sang Features Tab để cập nhật nốt mấy cái GroupBox bên đó
        if hasattr(self, 'parent_window') and self.parent_window:
            self.parent_window.features_interface.update_styles(is_dark)

    def refresh_auth_ui(self):
        auth = load_auth_info()
        user = auth.get("username", "N/A")
        db_status = auth.get("status", "Inactive")
        expiry = auth.get("expiry_date", "N/A")
        
        display_status = db_status
        color = "#ef4444" # Mặc định là Đỏ
        
        if expiry == "2000-01-01" or expiry == "N/A":
            expiry_display = "Chưa có Key"
            display_status = "Chưa kích hoạt"
        else:
            expiry_display = expiry
            try:
                # Tự động tính toán ngày hết hạn thực tế
                exp_date = datetime.strptime(expiry, "%Y-%m-%d")
                if datetime.now() > exp_date:
                    display_status = "Đã hết hạn"
                    color = "#ef4444" # Ép sang màu Đỏ
                elif db_status.lower() == "active":
                    display_status = "Đang hoạt động"
                    color = "#10b981" # Màu Xanh nếu còn hạn
            except:
                pass
            
        self.lbl_user.setText(f"<span style='font-size:14px'><b>Tài khoản:</b> {user}</span>")
        self.lbl_status.setText(f"<span style='font-size:14px'><b>Trạng thái:</b> <span style='color:{color}'><b>{display_status} (Hạn: {expiry_display})</b></span></span>")

    def activate_key(self):
        key = self.key_input.text().strip()
        auth = load_auth_info()
        user = auth.get("username")
        
        if not key or not user:
            InfoBar.warning("Lỗi", "Vui lòng nhập mã Key!", parent=self)
            return
            
        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("Đang kết nối...")
        
        self.act_thread = ActivateKeyThread(user, key)
        self.act_thread.result.connect(self.on_activate_done)
        self.act_thread.start()

    def on_activate_done(self, success, msg, new_data):
        self.btn_activate.setEnabled(True)
        self.btn_activate.setText("Kích hoạt Key")
        self.btn_activate.setIcon(FluentIcon.TAG)
        
        if success and new_data:
            try:
                with open(get_auth_path(), 'w', encoding='utf-8') as f: json.dump(new_data, f, indent=4)
            except: pass
            self.refresh_auth_ui()
            InfoBar.success("Thành công", msg, parent=self)
            self.key_input.clear()
            
            if hasattr(self, 'parent_window') and self.parent_window:
                self.parent_window.features_interface.check_license_lock()
        else:
            InfoBar.error("Thất bại", msg, parent=self)

    def update_styles(self, is_dark=None): apply_gb_style(self.groupboxes, is_dark)

    def save_all_settings(self):
        new_settings = {
            "api_key": self.api_input.text().strip(),
            "use_ai_spin": self.switch_ai_spin.isChecked(),
            "ai_spin_prompt": self.prompt_input.toPlainText().strip(),
            "delay_min": self.spin_delay_min.value(),
            "delay_max": self.spin_delay_max.value(),
            "headless": self.switch_headless.isChecked(),
            "theme": "Dark" if self.combo_theme.currentIndex() == 0 else "Light"
        }
        save_settings_to_file(new_settings)
        InfoBar.success('Thành công', 'Đã lưu thiết lập!', parent=self)


class AutoPostApp(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lynx Bot - AutoPost System")
        self.resize(1000, 750) 
        
        setTheme(Theme.DARK if load_settings().get("theme", "Dark") == "Dark" else Theme.LIGHT)
        
        self.terminal_interface = TerminalInterface(self)
        self.features_interface = FeaturesInterface(self)
        self.setting_interface = SettingInterface(self)
        
        self.addSubInterface(self.terminal_interface, FluentIcon.COMMAND_PROMPT, 'Terminal')
        self.addSubInterface(self.features_interface, FluentIcon.APPLICATION, 'Features')
        self.addSubInterface(self.setting_interface, FluentIcon.SETTING, 'Setting', NavigationItemPosition.BOTTOM)