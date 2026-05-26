import os
import sys
import json
import requests
import subprocess
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem, 
                             QTextEdit, QGroupBox, QFileDialog, QLabel) 
from qfluentwidgets import (FluentWindow, FluentIcon, NavigationItemPosition,
                            TextEdit, PrimaryPushButton, PushButton, InfoBar, 
                            InfoBarPosition, SubtitleLabel, ListWidget, LineEdit,
                            SpinBox, SwitchButton, ComboBox, setTheme, Theme,
                            BodyLabel, isDarkTheme, IconWidget)

from src.core.bot_thread import PosterThread, LoginThread, LogoutThread, FetchDataThread

# ==========================================
# CẤU HÌNH PROMPT MẶC ĐỊNH & LƯU CONFIG
# ==========================================
DEFAULT_AI_PROMPT = """Bạn là một chuyên gia Copywriter bán hàng lão luyện trên Facebook. 
Nhiệm vụ của bạn là xào (spin) lại đoạn văn bản dưới đây để tạo ra một bài đăng mới mẻ, thu hút, lách thuật toán quét Spam của Facebook.

LUẬT BẮT BUỘC:
1. TUYỆT ĐỐI GIỮ NGUYÊN 100% các dữ liệu cốt lõi: Tên người, SĐT, Giá tiền, Diện tích, Địa chỉ, và toàn bộ Hashtag, Link (URL).
2. BẠN CHỈ ĐƯỢC PHÉP làm mới câu từ ở phần Mở bài và các câu miêu tả cảm quan, thêm thắt hoặc đổi Emoji cho sinh động.
3. KHÔNG dùng các câu mào đầu của AI. Trả về trực tiếp nội dung để đăng lên Facebook.

Văn bản gốc:
{original_text}"""

def get_config_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    user_data_dir = os.path.join(base_dir, "user_data")
    os.makedirs(user_data_dir, exist_ok=True)
    return os.path.join(user_data_dir, "config.json")

def load_settings():
    default_settings = {
        "api_key": "",
        "use_ai_spin": False,
        "ai_spin_prompt": DEFAULT_AI_PROMPT, # Thêm trường lưu Prompt
        "delay_min": 10,
        "delay_max": 30,
        "headless": False,
        "theme": "Dark"
    }
    try:
        if os.path.exists(get_config_path()):
            with open(get_config_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                default_settings.update(data)
    except: pass
    return default_settings

def save_settings_to_file(data):
    try:
        with open(get_config_path(), 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=4)
    except: pass

def load_api_key():
    return load_settings().get('api_key', '')

def save_api_key(key):
    settings = load_settings()
    settings['api_key'] = key
    save_settings_to_file(settings)

def apply_gb_style(groupboxes):
    dark = isDarkTheme()
    text_color = "white" if dark else "black"
    border_color = "#30363d" if dark else "#dcdcdc"
    
    style = f"""
        QGroupBox {{
            border: 1px solid {border_color};
            border-radius: 8px;
            margin-top: 15px;
            padding-top: 15px;
            font-size: 14px;
            font-weight: bold;
            color: {text_color};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            left: 10px;
            color: {text_color};
        }}
    """
    for gb in groupboxes:
        gb.setStyleSheet(style)


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
        self.console.setStyleSheet("""
            QTextEdit { background-color: #0d1117; color: #10b981; font-family: 'Consolas', monospace; font-size: 14px; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
            QScrollBar:vertical { background: #0d1117; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #30363d; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #10b981; }
        """)
        layout.addWidget(self.console)
        self.log_message("Hệ thống Lynx Bot đã khởi động.")

    def log_message(self, message):
        self.console.append(f"> {message}")
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class FeaturesInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("FeaturesInterface")
        self.parent_window = parent
        self.image_paths = [] 
        self.groupboxes = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        control_layout = QHBoxLayout()
        self.btn_login = PushButton(FluentIcon.PEOPLE, "Đăng nhập FB", self)
        self.btn_login.clicked.connect(self.login_fb)
        self.btn_fetch = PushButton(FluentIcon.SYNC, "Tải danh sách Nhóm & Page", self)
        self.btn_fetch.clicked.connect(self.fetch_data)
        self.btn_logout = PushButton(FluentIcon.CLOSE, "Đăng xuất FB", self)
        self.btn_logout.clicked.connect(self.logout_fb)
        
        control_layout.addWidget(self.btn_login)
        control_layout.addWidget(self.btn_fetch)
        control_layout.addWidget(self.btn_logout)
        control_layout.addStretch(1) 
        layout.addLayout(control_layout)

        list_layout = QHBoxLayout()
        
        self.group_box = QGroupBox("Danh sách Nhóm đã tham gia")
        group_layout = QVBoxLayout()
        
        group_top_layout = QHBoxLayout()
        self.search_group_input = LineEdit(self)
        self.search_group_input.setPlaceholderText("Tìm kiếm nhóm (VD: Bất động sản)...")
        self.search_group_input.setClearButtonEnabled(True)
        self.search_group_input.textChanged.connect(self.filter_groups)
        
        self.btn_select_all = PushButton(FluentIcon.ACCEPT, "Chọn tất cả", self)
        self.btn_select_all.clicked.connect(self.select_all_groups)
        
        self.btn_deselect_all = PushButton(FluentIcon.CLOSE, "Bỏ chọn", self)
        self.btn_deselect_all.clicked.connect(self.deselect_all_groups)
        
        group_top_layout.addWidget(self.search_group_input, stretch=2)
        group_top_layout.addWidget(self.btn_select_all)
        group_top_layout.addWidget(self.btn_deselect_all)
        
        group_layout.addLayout(group_top_layout)
        
        self.list_groups = ListWidget(self)
        group_layout.addWidget(self.list_groups)
        self.group_box.setLayout(group_layout)
        
        self.page_box = QGroupBox("Danh sách Page / Trang cá nhân")
        page_layout = QVBoxLayout()
        self.list_pages = ListWidget(self)
        page_layout.addWidget(self.list_pages)
        self.page_box.setLayout(page_layout)

        self.groupboxes.extend([self.group_box, self.page_box])

        list_layout.addWidget(self.group_box)
        list_layout.addWidget(self.page_box)
        layout.addLayout(list_layout, stretch=2)

        img_layout = QHBoxLayout()
        self.btn_select_image = PushButton(FluentIcon.PHOTO, "Chọn Ảnh/Video đính kèm", self)
        self.btn_select_image.clicked.connect(self.select_images)
        self.lbl_images = BodyLabel("Chưa chọn file nào", self)
        
        img_layout.addWidget(self.btn_select_image)
        img_layout.addWidget(self.lbl_images, stretch=1)
        layout.addLayout(img_layout)

        self.content_input = TextEdit(self)
        self.content_input.setPlaceholderText("Nhập nội dung bài viết. Tool sẽ giữ nguyên 100% văn bản của bạn và gõ phím như người thật...")
        layout.addWidget(self.content_input, stretch=1)

        self.btn_run = PrimaryPushButton(FluentIcon.SEND, "Khởi động AutoPost", self)
        self.btn_run.clicked.connect(self.start_posting)
        layout.addWidget(self.btn_run)

        self.update_styles()

    def update_styles(self):
        apply_gb_style(self.groupboxes)

    def select_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn Ảnh/Video", "", "Image/Video Files (*.png *.jpg *.jpeg *.mp4 *.avi)")
        if files:
            self.image_paths = files
            num_files = len(files)
            base_names = [os.path.basename(f) for f in files]
            if num_files == 1:
                display_text = f"Đã chọn 1 file: {base_names[0]}"
            elif num_files == 2:
                display_text = f"Đã chọn 2 file: {base_names[0]}, {base_names[1]}"
            else:
                display_text = f"Đã chọn {num_files} file: {base_names[0]}, {base_names[1]} ... và {num_files - 2} file khác"
            self.lbl_images.setText(display_text)
            self.lbl_images.setStyleSheet("color: #10b981; font-weight: bold;") 
        else:
            self.image_paths = []
            self.lbl_images.setText("Chưa chọn file nào")
            self.lbl_images.setStyleSheet("")

    def filter_groups(self, text):
        search_text = text.lower() 
        for i in range(self.list_groups.count()):
            item = self.list_groups.item(i)
            if search_text in item.text().lower():
                item.setHidden(False) 
            else:
                item.setHidden(True)  

    def select_all_groups(self):
        for i in range(self.list_groups.count()):
            item = self.list_groups.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)

    def deselect_all_groups(self):
        for i in range(self.list_groups.count()):
            item = self.list_groups.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Unchecked)

    def log_to_terminal(self, msg):
        if hasattr(self.parent_window, 'terminal_interface'):
            self.parent_window.terminal_interface.log_message(msg)

    def login_fb(self):
        self.btn_login.setEnabled(False)
        self.log_to_terminal("Đang mở trình duyệt để đăng nhập...")
        self.login_thread = LoginThread()
        self.login_thread.finished_signal.connect(lambda m: self._on_done(self.btn_login, m))
        self.login_thread.error_signal.connect(self.on_error)
        self.login_thread.start()

    def logout_fb(self):
        self.btn_logout.setEnabled(False)
        self.log_to_terminal("Đang mở trình duyệt để đăng xuất tài khoản hiện tại...")
        self.logout_thread = LogoutThread()
        self.logout_thread.log_signal.connect(self.log_to_terminal)
        self.logout_thread.finished_signal.connect(lambda m: self._on_done(self.btn_logout, m))
        self.logout_thread.error_signal.connect(self.on_error)
        self.logout_thread.start()

    def fetch_data(self):
        self.btn_fetch.setEnabled(False)
        self.list_groups.clear()
        self.list_pages.clear()
        self.search_group_input.clear()
        self.log_to_terminal("Bắt đầu lấy dữ liệu...")
        
        api_key = load_api_key()
        
        self.fetch_thread = FetchDataThread(api_key)
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
        selected_urls = []
        for i in range(self.list_groups.count()):
            item = self.list_groups.item(i)
            if item.checkState() == Qt.CheckState.Checked: selected_urls.append(item.data(Qt.ItemDataRole.UserRole))
                
        for i in range(self.list_pages.count()):
            item = self.list_pages.item(i)
            if item.checkState() == Qt.CheckState.Checked: selected_urls.append(item.data(Qt.ItemDataRole.UserRole))

        content = self.content_input.toPlainText().strip()

        if not selected_urls or not content:
            InfoBar.warning('Cảnh báo', 'Cần chọn ít nhất 1 nơi đăng và nhập nội dung!', parent=self)
            return

        self.btn_run.setEnabled(False)
        self.log_to_terminal(f"Chuẩn bị đăng bài lên {len(selected_urls)} địa chỉ...")

        self.post_thread = PosterThread(selected_urls, content, self.image_paths)
        self.post_thread.log_signal.connect(self.log_to_terminal)
        self.post_thread.finished_signal.connect(lambda m: self._on_done(self.btn_run, m))
        self.post_thread.error_signal.connect(self.on_error)
        self.post_thread.start()

    def _on_done(self, btn, msg):
        btn.setEnabled(True)
        self.log_to_terminal(msg)
        InfoBar.success('Hoàn tất', msg, parent=self)

    def on_error(self, error_message):
        self.btn_fetch.setEnabled(True)
        self.btn_login.setEnabled(True)
        self.btn_run.setEnabled(True)
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
        layout.setSpacing(20)

        self.current_settings = load_settings()

        title = SubtitleLabel("Cài đặt hệ thống Lynx Bot", self)
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignTop)

        self.api_box = QGroupBox("1. Trí tuệ nhân tạo (AI Gemini)")
        api_layout = QVBoxLayout()
        api_layout.setSpacing(10)
        api_layout.setContentsMargins(20, 25, 20, 20)
        
        api_inner = QHBoxLayout()
        api_inner.addWidget(BodyLabel("Mã API Key (Bảo mật):", self))
        
        self.api_input = LineEdit(self)
        self.api_input.setPlaceholderText("Nhập Gemini API Key để kích hoạt AI...")
        self.api_input.setEchoMode(LineEdit.EchoMode.Password)
        self.api_input.setClearButtonEnabled(True)
        self.api_input.setText(self.current_settings.get("api_key", "")) 
        
        api_inner.addWidget(self.api_input, stretch=1)
        api_layout.addLayout(api_inner)
        
        # --- BẬT TẮT AI ---
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(BodyLabel("Bật AI Spin (Trộn) nội dung tự động chống Checkpoint:", self))
        
        self.switch_ai_spin = SwitchButton(self)
        self.switch_ai_spin.setOnText("Bật")
        self.switch_ai_spin.setOffText("Tắt")
        self.switch_ai_spin.setChecked(self.current_settings.get("use_ai_spin", False))
        
        spin_layout.addWidget(self.switch_ai_spin)
        spin_layout.addStretch(1)
        api_layout.addLayout(spin_layout)

        # --- Ô NHẬP LỆNH PROMPT CHO AI ---
        self.prompt_label = BodyLabel("Câu lệnh cấu hình AI (Giữ nguyên cụm {original_text} ở cuối để truyền bài viết vào):", self)
        self.prompt_label.setStyleSheet("margin-top: 10px;")
        api_layout.addWidget(self.prompt_label)
        
        self.prompt_input = TextEdit(self)
        self.prompt_input.setPlaceholderText("Nhập câu lệnh Prompt để điều khiển văn phong AI...")
        self.prompt_input.setText(self.current_settings.get("ai_spin_prompt", DEFAULT_AI_PROMPT))
        self.prompt_input.setMinimumHeight(120) 
        api_layout.addWidget(self.prompt_input)

        self.api_box.setLayout(api_layout)
        layout.addWidget(self.api_box)

        self.auto_box = QGroupBox("2. Cấu hình An toàn & Trình duyệt")
        auto_layout = QVBoxLayout()
        auto_layout.setSpacing(15)
        auto_layout.setContentsMargins(20, 25, 20, 20)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(BodyLabel("Thời gian nghỉ ngẫu nhiên giữa các bài đăng (Giây):", self))
        
        self.spin_delay_min = SpinBox(self)
        self.spin_delay_min.setRange(1, 300)
        self.spin_delay_min.setValue(self.current_settings.get("delay_min", 10))
        
        self.spin_delay_max = SpinBox(self)
        self.spin_delay_max.setRange(1, 600)
        self.spin_delay_max.setValue(self.current_settings.get("delay_max", 30))
        
        delay_layout.addWidget(self.spin_delay_min)
        delay_layout.addWidget(BodyLabel("đến", self))
        delay_layout.addWidget(self.spin_delay_max)
        delay_layout.addStretch(1)
        auto_layout.addLayout(delay_layout)

        headless_layout = QHBoxLayout()
        headless_layout.addWidget(BodyLabel("Chế độ chạy ngầm (Ẩn hoàn toàn cửa sổ Chrome giúp nhẹ máy):", self))
        
        self.switch_headless = SwitchButton(self)
        self.switch_headless.setOnText("Bật")
        self.switch_headless.setOffText("Tắt")
        self.switch_headless.setChecked(self.current_settings.get("headless", False))
        
        headless_layout.addWidget(self.switch_headless)
        headless_layout.addStretch(1)
        auto_layout.addLayout(headless_layout)

        self.auto_box.setLayout(auto_layout)
        layout.addWidget(self.auto_box)

        self.ui_box = QGroupBox("3. Tùy biến màu sắc giao diện")
        ui_layout = QHBoxLayout()
        ui_layout.setContentsMargins(20, 25, 20, 20)
        
        ui_layout.addWidget(BodyLabel("Chủ đề hiển thị ứng dụng:", self))
        
        self.combo_theme = ComboBox(self)
        self.combo_theme.addItems(["Tối (Dark Mode)", "Sáng (Light Mode)"])
        
        if self.current_settings.get("theme", "Dark") == "Dark":
            self.combo_theme.setCurrentIndex(0)
            setTheme(Theme.DARK)
        else:
            self.combo_theme.setCurrentIndex(1)
            setTheme(Theme.LIGHT)
            
        self.combo_theme.currentIndexChanged.connect(self.change_theme)
        
        ui_layout.addWidget(self.combo_theme)
        ui_layout.addStretch(1)
        self.ui_box.setLayout(ui_layout)
        layout.addWidget(self.ui_box)

        self.groupboxes.extend([self.api_box, self.auto_box, self.ui_box])
        self.update_styles()

        layout.addStretch(1)

        self.btn_save = PrimaryPushButton(FluentIcon.SAVE, "Lưu toàn bộ cấu hình", self)
        self.btn_save.clicked.connect(self.save_all_settings)
        layout.addWidget(self.btn_save, alignment=Qt.AlignmentFlag.AlignRight)

    def update_styles(self):
        apply_gb_style(self.groupboxes)

    def change_theme(self, index):
        if index == 0:
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)
            
        self.update_styles()
        if hasattr(self, 'parent_window') and self.parent_window:
            if hasattr(self.parent_window, 'features_interface'):
                self.parent_window.features_interface.update_styles()

    def save_all_settings(self):
        min_val = self.spin_delay_min.value()
        max_val = self.spin_delay_max.value()
        
        if min_val > max_val:
            InfoBar.warning('Cảnh báo', 'Thời gian Min không được lớn hơn Max!', parent=self)
            return
            
        new_settings = {
            "api_key": self.api_input.text().strip(),
            "use_ai_spin": self.switch_ai_spin.isChecked(),
            "ai_spin_prompt": self.prompt_input.toPlainText().strip(), # LƯU PROMPT
            "delay_min": min_val,
            "delay_max": max_val,
            "headless": self.switch_headless.isChecked(),
            "theme": "Dark" if self.combo_theme.currentIndex() == 0 else "Light"
        }
        
        save_settings_to_file(new_settings)
        InfoBar.success('Thành công', 'Đã cập nhật toàn bộ cấu hình hệ thống!', parent=self)


class AutoPostApp(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lynx Bot - AutoPost System")
        self.resize(1000, 750) 
        
        settings = load_settings()
        if settings.get("theme", "Dark") == "Dark":
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)
        
        self.terminal_interface = TerminalInterface(self)
        self.features_interface = FeaturesInterface(self)
        self.setting_interface = SettingInterface(self)
        
        self.addSubInterface(self.terminal_interface, FluentIcon.COMMAND_PROMPT, 'Terminal')
        self.addSubInterface(self.features_interface, FluentIcon.APPLICATION, 'Features')
        self.addSubInterface(self.setting_interface, FluentIcon.SETTING, 'Setting', NavigationItemPosition.BOTTOM)