import subprocess
import requests
from datetime import datetime, timedelta
import uuid
from src.core.constants import SHEETDB_URL_USERS 
from src.core.constants import SHEETDB_URL_LICENSES

def get_hwid():
    """Lấy mã định danh phần cứng độc nhất của máy tính"""
    try:
        hwid = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].strip()
        return hwid
    except:
        return str(uuid.getnode())

def login_user(username, password):
    """Xử lý Đăng nhập và khóa máy"""
    if not username or not password: return False, "Vui lòng nhập đủ thông tin!", None
    my_hwid = get_hwid()
    try:
        res = requests.get(f"{SHEETDB_URL_USERS}/search?username={username}", timeout=10)
        data = res.json()
        
        # Bắt lỗi chuẩn: Nếu SheetDB trả về mảng rỗng [] nghĩa là không có user này
        if res.status_code != 200 or not isinstance(data, list) or len(data) == 0: 
            return False, "Tài khoản không tồn tại!", None
        
        user = data[0]
        if str(user.get("password", "")) != str(password): return False, "Sai mật khẩu!", None
        
        if user.get("status", "").lower() == "banned":
            return False, "Tài khoản này đã bị admin khóa vĩnh viễn!", None
        
        saved_hwid = user.get("hwid", "")
        if not saved_hwid:
            requests.patch(f"{SHEETDB_URL_USERS}/username/{username}", json={"data": {"hwid": my_hwid}}, timeout=10)
            user["hwid"] = my_hwid
        elif saved_hwid != my_hwid:
            return False, "Tài khoản đang được dùng trên máy khác!", None
            
        return True, "Đăng nhập thành công!", user
    except Exception as e: return False, "Lỗi kết nối máy chủ!", None

def register_user(username, password):
    """Xử lý Tạo tài khoản mới lên SheetDB"""
    if not username or not password: return False, "Vui lòng nhập đủ thông tin!"
    if len(username) < 4: return False, "Tên đăng nhập phải có ít nhất 4 ký tự!"
    if len(password) < 6: return False, "Mật khẩu phải có ít nhất 6 ký tự!"
    
    try:
        # BẮT BUỘC CHECK TRÙNG LẶP: Quét xem tên đăng nhập đã ai xài chưa
        res = requests.get(f"{SHEETDB_URL_USERS}/search?username={username}", timeout=10)
        data = res.json()
        if res.status_code == 200 and isinstance(data, list) and len(data) > 0: 
            return False, "Tên đăng nhập đã tồn tại! Vui lòng chọn tên khác."
        
        new_user = {
            "username": username,
            "password": password,
            "license_key": "",
            "hwid": "",
            "status": "Inactive",
            "expiry_date": "2000-01-01" 
        }
        requests.post(SHEETDB_URL_USERS, json={"data": new_user}, timeout=10)
        return True, "Đăng ký thành công! Vui lòng đăng nhập."
    except Exception as e: return False, "Lỗi kết nối máy chủ!"

def activate_license(username, key):
    """Kích hoạt Key: Chặn nạp chồng nếu còn hạn, lưu lịch sử, gia hạn 30 ngày"""
    try:
        # 1. Tìm Key mới trong bảng Licenses
        res_key = requests.get(f"{SHEETDB_URL_LICENSES}/search?license_key={key}", timeout=10)
        keys = res_key.json()
        
        if not keys or not isinstance(keys, list) or len(keys) == 0 or keys[0].get("status") != "Available":
            return False, "Mã Key không tồn tại hoặc đã được sử dụng!", None
        
        # 2. Tìm thông tin User
        res_user = requests.get(f"{SHEETDB_URL_USERS}/search?username={username}", timeout=10)
        users = res_user.json()
        if not users or not isinstance(users, list) or len(users) == 0: 
            return False, "Không tìm thấy tài khoản người dùng!", None
        
        user_data = users[0] 
        
        # 3. 🔥 TÍNH NĂNG MỚI: CHẶN NẾU TÀI KHOẢN VẪN CÒN HẠN SỬ DỤNG 🔥
        try:
            current_expiry = datetime.strptime(user_data.get("expiry_date", "2000-01-01"), "%Y-%m-%d")
            # Nếu hạn sử dụng vẫn lớn hơn thời điểm hiện tại -> Chặn!
            if current_expiry > datetime.now() and user_data.get("status", "").lower() == "active":
                return False, f"Tài khoản của bạn vẫn còn hạn đến {user_data.get('expiry_date')}. Vui lòng chờ hết hạn mới nạp tiếp!", None
        except:
            pass # Bỏ qua nếu lỗi format ngày tháng, mặc định cho phép nạp
        
        # 4. Tính toán hạn sử dụng mới (Tính từ ngày hôm nay + 30 ngày)
        new_expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # 5. Cập nhật bảng Licenses: Đổi Key mới thành 'Used', lưu người nạp & thời gian nạp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        requests.patch(f"{SHEETDB_URL_LICENSES}/license_key/{key}", 
                       json={"data": {"status": "Used", "activated_by": username, "activated_date": current_time}}, timeout=10)
        
        # 6. Cập nhật bảng Users: Ghi nhận hạn dùng và Gắn Key mới vào (Key cũ bên bảng Licenses vẫn được bảo tồn)
        update_payload = {
            "status": "Active", 
            "expiry_date": new_expiry, 
            "license_key_used": key 
        }
        requests.patch(f"{SHEETDB_URL_USERS}/username/{username}", json={"data": update_payload}, timeout=10)
        
        # 7. Gộp dữ liệu mới vào user_data để trả về giao diện
        user_data.update(update_payload)
        user_data["key"] = key 
        
        return True, "Kích hoạt thành công!", user_data
        
    except Exception as e:
        return False, f"Lỗi hệ thống: {str(e)}", None