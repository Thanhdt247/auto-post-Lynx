import os
import json
import shutil
import subprocess

print("="*50)
print("🚀 LYNX BOT - HỆ THỐNG TỰ ĐỘNG ĐÓNG GÓI CẬP NHẬT 🚀")
print("="*50)

# 1. Nhập thông tin bản mới từ Terminal
new_version = input("👉 Nhập phiên bản mới (vd: 1.0.1): ").strip()
changelog = input("👉 Nhập nội dung cập nhật (Dùng \\n để xuống dòng): ").strip()

print(f"\n[1/4] Đang cập nhật hệ thống lên phiên bản v{new_version}...")
# 2. Ghi đè file version.py
with open("version.py", "w", encoding="utf-8") as f:
    f.write(f'APP_VERSION = "{new_version}"\n')

# 3. Ghi đè file version.json (Sẵn sàng up lên GitHub)
github_json = {
    "version": new_version,
    "changelog": changelog,
    "download_url": f"https://github.com/Thanhdt247/auto-post-Lynx/releases/download/v{new_version}/update_package.zip"
}
with open("version.json", "w", encoding="utf-8") as f:
    json.dump(github_json, f, indent=4, ensure_ascii=False)

print("[2/4] Đang gọi PyInstaller để đóng gói phần mềm (Sẽ mất vài phút)...")
# 4. Tự động chạy lệnh Build Pyinstaller
subprocess.run(["pyinstaller", "--clean", "Lynx-bot.spec"], shell=True)

print("\n[3/4] Build thành công! Đang nén thư mục thành file update_package.zip...")
# 5. Tự động nén thư mục dist/Lynx-bot thành file Zip
dist_dir = os.path.join("dist", "Lynx-bot")
zip_name = "update_package"
if os.path.exists(f"{zip_name}.zip"):
    os.remove(f"{zip_name}.zip") # Xóa file zip cũ nếu có
shutil.make_archive(zip_name, 'zip', dist_dir)

print("\n[4/4] 🎉 HOÀN TẤT QUY TRÌNH!")
print(f"✅ Đã tạo xong file: update_package.zip")
print(f"✅ Đã tạo xong file: version.json")
print("="*50)
print("BƯỚC TIẾP THEO BẠN CẦN LÀM:")
print(f"1. Up toàn bộ code (gồm version.json) lên nhánh main của GitHub.")
print(f"2. Tạo Release mới tên v{new_version} trên GitHub.")
print(f"3. Kéo thả file update_package.zip vào Release đó và Publish!")