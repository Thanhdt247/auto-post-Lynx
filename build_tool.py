import os
import sys
import json
import shutil
import subprocess

print("="*50)
print("🚀 LYNX BOT - HỆ THỐNG ĐÓNG GÓI BẢO MẬT (NUITKA C++) 🚀")
print("="*50)

# 1. Nhập thông tin bản mới
new_version = input("👉 Nhập phiên bản mới (vd: 1.0.1): ").strip()
changelog = input("👉 Nhập nội dung cập nhật (Dùng \\n để xuống dòng): ").strip()

print(f"\n[1/4] Đang cập nhật hệ thống lên phiên bản v{new_version}...")
with open("version.py", "w", encoding="utf-8") as f:
    f.write(f'APP_VERSION = "{new_version}"\n')

github_json = {
    "version": new_version,
    "changelog": changelog,
    "download_url": f"https://github.com/Thanhdt247/auto-post-Lynx/releases/download/v{new_version}/update_package.zip"
}
with open("version.json", "w", encoding="utf-8") as f:
    json.dump(github_json, f, indent=4, ensure_ascii=False)

print("\n[2/4] Đang gọi NUITKA để biên dịch mã nguồn sang C++ (Sẽ mất vài phút)...")
print("      (Nuitka sẽ bảo vệ 100% source code của sếp khỏi việc bị dịch ngược!)")

# Tự động tìm thư viện Playwright để đóng gói kèm
playwright_include = ""
try:
    import playwright
    pw_path = os.path.dirname(playwright.__file__)
    # FIX LỖI DẤU CÁCH: Bọc toàn bộ tham số vào trong ngoặc kép ""
    playwright_include = f'--include-data-dir="{pw_path}=playwright"'
    print("      - Đã tìm thấy thư viện Playwright, đưa vào luồng đóng gói...")
except ImportError:
    pass

# Lệnh Nuitka siêu bảo mật có gắn Icon
nuitka_cmd = f'python -m nuitka --standalone --windows-disable-console --windows-icon-from-ico=logo.ico --enable-plugin=pyqt6 {playwright_include} --output-dir=dist main.py'

# Chạy lệnh biên dịch và kiểm tra lỗi
result = subprocess.run(nuitka_cmd, shell=True)

# Nếu Nuitka build xịt, tự động dừng chương trình, không chạy phần nén ZIP
if result.returncode != 0:
    print("\n❌ LỖI: Quá trình Build Nuitka thất bại! Vui lòng kiểm tra log lỗi màu đỏ phía trên.")
    sys.exit(1)

print("\n[3/4] Build thành công! Đang xử lý file và nén thành update_package.zip...")

dist_dir = os.path.join("dist", "main.dist")
target_dir = os.path.join("dist", "Lynx-bot")

if os.path.exists(target_dir):
    shutil.rmtree(target_dir)
    
if os.path.exists(dist_dir):
    exe_path = os.path.join(dist_dir, "main.exe")
    new_exe_path = os.path.join(dist_dir, "Lynx-bot.exe")
    if os.path.exists(exe_path):
        os.rename(exe_path, new_exe_path)
    os.rename(dist_dir, target_dir)

zip_name = "update_package"
if os.path.exists(f"{zip_name}.zip"):
    os.remove(f"{zip_name}.zip")
    
shutil.make_archive(zip_name, 'zip', target_dir)

print("\n[4/4] 🎉 HOÀN TẤT QUY TRÌNH!")
print(f"✅ Đã tạo xong file: update_package.zip (Mã hóa C++ 100%)")
print(f"✅ Đã tạo xong file: version.json")
print("="*50)
print("BƯỚC TIẾP THEO BẠN CẦN LÀM:")
print(f"1. Up toàn bộ code (gồm version.json) lên nhánh main của GitHub.")
print(f"2. Tạo Release mới tên v{new_version} trên GitHub.")
print(f"3. Kéo thả file update_package.zip vào Release đó và Publish!")