import sys
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme
from src.gui.updater import LauncherWindow, is_dark_mode

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 🌟 CỰC KỲ QUAN TRỌNG: Ngăn chặn App bị tắt ngầm khi chuyển từ bảng Update sang bảng License
    app.setQuitOnLastWindowClosed(False)
    
    # Thiết lập màu nền toàn hệ thống trước khi vẽ giao diện
    if is_dark_mode():
        setTheme(Theme.DARK)
    else:
        setTheme(Theme.LIGHT)
        
    # GỌI LAUNCHER UPDATE RA TRƯỚC
    launcher = LauncherWindow()
    launcher.show()
    
    sys.exit(app.exec())