import os
import sys
import time
import json
import random
import re
from PyQt6.QtCore import QThread, pyqtSignal
from playwright.sync_api import sync_playwright
import google.generativeai as genai

def get_profile_dir():
    # Kiểm tra xem đang chạy file .exe hay đang chạy code .py
    if getattr(sys, 'frozen', False):
        # Nếu là file .exe: lấy đường dẫn thư mục chứa file .exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Nếu là code .py: lấy đường dẫn thư mục gốc của dự án
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
    profile_dir = os.path.join(base_dir, "user_data", "chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)
    return profile_dir

def get_active_page(browser):
    pages = browser.pages
    if len(pages) > 0: page = pages[0]
    else: page = browser.new_page()
    for i in range(1, len(pages)):
        try: pages[i].close()
        except: pass
    return page

def handle_browser_launch_error(e, error_signal):
    if "existing browser session" in str(e).lower():
        error_signal.emit("LỖI: Trình duyệt đang được mở! Vui lòng tắt cửa sổ Chrome hiện tại.")
    else:
        error_signal.emit(f"Lỗi khởi chạy: {str(e)}")

def get_best_ai_model():
    try:
        model_name = 'gemini-1.0-pro' 
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name
                if 'flash' in model_name or 'pro' in model_name: break
        return model_name
    except: return 'gemini-1.0-pro'


class LoginThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            with sync_playwright() as p:
                try: browser = p.chromium.launch_persistent_context(user_data_dir=get_profile_dir(), headless=False, args=['--disable-blink-features=AutomationControlled'])
                except Exception as e: handle_browser_launch_error(e, self.error_signal); return
                page = get_active_page(browser)
                page.goto("https://www.facebook.com/")
                self.finished_signal.emit("Cửa sổ Chrome đã mở. Hãy đăng nhập Facebook...")
                for _ in range(120): 
                    try:
                        if page.is_closed(): break
                        if page.locator("input[aria-label='Tìm kiếm trên Facebook']").count() > 0:
                            time.sleep(1.5); break
                        time.sleep(0.5)
                    except: break 
                try: browser.close()
                except: pass
                self.finished_signal.emit("Đã lưu phiên đăng nhập thành công!")
        except Exception as e:
            self.error_signal.emit(f"Lỗi hệ thống: {str(e)}")


class FetchDataThread(QThread):
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str) 
    
    def __init__(self, api_key):
        super().__init__(); self.api_key = api_key

    def run(self):
        try:
            if self.api_key: genai.configure(api_key=self.api_key)
            with sync_playwright() as p:
                try: browser = p.chromium.launch_persistent_context(user_data_dir=get_profile_dir(), headless=False, args=['--disable-blink-features=AutomationControlled'])
                except Exception as e: handle_browser_launch_error(e, self.error_signal); return
                page = get_active_page(browser)
                scraped_data = {"groups": [], "pages": []}

                # --- 1. QUÉT NHÓM (CẬP NHẬT THUẬT TOÁN CUỘN ĐỘNG VÔ HẠN) ---
                self.log_signal.emit("Đang quét danh sách Hội nhóm...")
                page.goto("https://www.facebook.com/groups/feed/")
                time.sleep(3)
                
                try:
                    # Di chuột vào vùng menu bên trái chứa danh sách nhóm để chuẩn bị cuộn
                    sidebar = page.locator("div[aria-label='Danh sách nhóm']").first
                    sidebar.hover(timeout=3000)
                    
                    last_group_count = 0
                    no_new_groups_turns = 0
                    
                    # Vòng lặp cuộn động: Sẽ dừng lại khi cuộn 4 lần liên tiếp mà không thấy nhóm mới xuất hiện
                    while no_new_groups_turns < 4:
                        page.mouse.wheel(0, 2000)
                        time.sleep(1.5) # Chờ 1.5s để Facebook tải thêm dữ liệu nhóm mới
                        
                        # Đếm số lượng liên kết hiện tại đang hiển thị trong DOM
                        current_group_count = page.locator("div[aria-label='Danh sách nhóm'][role='navigation'] a").count()
                        if current_group_count == 0:
                            current_group_count = page.locator("a[href*='/groups/']").count()
                            
                        if current_group_count > last_group_count:
                            self.log_signal.emit(f"Đang tải dữ liệu... Đã nhận diện sơ bộ {current_group_count} liên kết nhóm.")
                            last_group_count = current_group_count
                            no_new_groups_turns = 0 # Reset bộ đếm nếu vẫn thấy có nhóm mới xuất hiện
                        else:
                            no_new_groups_turns += 1 # Tăng bộ đếm nếu Facebook không tải thêm nhóm nào nữa
                            
                    self.log_signal.emit(" Đã cuộn hết danh sách Hội nhóm. Bắt đầu lọc dữ liệu...")
                except Exception as e:
                    self.log_signal.emit(f"Lưu ý khi cuộn danh sách nhóm: {str(e)}")

                # Tiến hành nhặt link sau khi đã cuộn hết sạch danh sách
                group_elements = page.locator("div[aria-label='Danh sách nhóm'][role='navigation'] a").all()
                if not group_elements: group_elements = page.locator("a[href*='/groups/']").all()
                for el in group_elements:
                    try:
                        url = el.get_attribute("href") or ""; name = el.inner_text().split('\n')[0].strip()
                        if name and "/groups/" in url:
                            url = url.split('?')[0] if url.startswith("http") else f"https://www.facebook.com{url.split('?')[0]}"
                            blacklist = ["khám phá", "tạo nhóm", "bảng feed", "nhóm của bạn", "xem tất cả", "đã tham gia", "chưa đọc", "bài viết mới"]
                            if not any(b in name.lower() for b in blacklist) and 3 < len(name) < 60:
                                if not any(g['url'] == url for g in scraped_data["groups"]): scraped_data["groups"].append({"name": name, "url": url})
                    except: continue

                # --- 2. QUÉT PAGE (CŨNG ÁP DỤNG CUỘN ĐỘNG ĐỂ ĐỒNG BỘ) ---
                self.log_signal.emit("Đang quét danh sách Fanpage...")
                page.goto("https://www.facebook.com/pages/?category=your_pages")
                time.sleep(4) 
                
                try:
                    last_page_links = 0
                    no_new_pages_turns = 0
                    while no_new_pages_turns < 4:
                        page.mouse.wheel(0, 2500)
                        time.sleep(1.5)
                        
                        current_page_links = page.locator("a").count()
                        if current_page_links > last_page_links:
                            last_page_links = current_page_links
                            no_new_pages_turns = 0
                        else:
                            no_new_pages_turns += 1
                except: pass

                raw_links = []
                main_area = page.locator("div[role='main']")
                if main_area.count() > 0:
                    all_links = main_area.locator("a").all()
                else:
                    all_links = page.locator("a").all()

                for link in all_links:
                    try:
                        url = link.get_attribute("href") or ""
                        raw_text = link.inner_text().strip()
                        if not raw_text or not url: continue
                        
                        name = raw_text.split('\n')[0].strip() 
                        url_lower = url.lower()
                        name_lower = name.lower()

                        if url.startswith("/"): url = f"https://www.facebook.com{url}"
                        
                        bad_urls = ["business.facebook.com", "category=", "discovery", "groups", "watch", "help", "messages", "notifications", "bookmarks", "notif_id"]
                        if any(bad in url_lower for bad in bad_urls): continue

                        bad_names = ["meta business", "khám phá", "followed pages", "lời mời", "tạo trang", "trang bạn quản lý", "tin nhắn", "quảng cáo", "cài đặt", "chỉnh sửa", "thông báo", "chưa đọc", "đăng nhập", "vừa xong", "phút trước"]
                        if any(bad in name_lower for bad in bad_names): continue

                        if 2 < len(name) < 60 and "facebook.com" in url_lower:
                            raw_links.append({"name": name, "url": url})
                    except: continue

                unique_links = []
                seen_urls = set()
                for item in raw_links:
                    if item['url'] not in seen_urls:
                        unique_links.append(item)
                        seen_urls.add(item['url'])

                if self.api_key:
                    best_model = get_best_ai_model()
                    self.log_signal.emit(f"🤖 Đang nhờ AI ({best_model}) kiểm tra lại Fanpage...")
                    model = genai.GenerativeModel(best_model)
                    prompt = f"Lọc danh sách Fanpage. Xóa BỎ HOÀN TOÀN các menu như 'Meta Business', 'Khám phá', 'Followed Pages', 'Lời mời' hoặc các dòng chữ thông báo bảo mật dài dòng. Dữ liệu: {json.dumps(unique_links, ensure_ascii=False)}. Trả về ĐÚNG 1 mảng JSON format: [{{\"name\": \"...\", \"url\": \"...\"}}]"
                    try:
                        response_text = model.generate_content(prompt).text
                        cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
                        match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
                        if match:
                            scraped_data["pages"] = json.loads(match.group(0))
                            self.log_signal.emit("🤖 Lọc Page hoàn tất!")
                        else:
                            scraped_data["pages"] = unique_links
                    except:
                        scraped_data["pages"] = unique_links
                else: 
                    scraped_data["pages"] = unique_links

                browser.close()
                self.finished_signal.emit(scraped_data)
        except Exception as e: self.error_signal.emit(f"Lỗi quét dữ liệu: {str(e)}")


class PosterThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, urls, content, image_paths):
        super().__init__()
        self.urls = urls
        self.content = content
        self.image_paths = image_paths 

    def run(self):
        try:
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch_persistent_context(
                        user_data_dir=get_profile_dir(), headless=False, 
                        args=['--disable-blink-features=AutomationControlled']
                    )
                except Exception as e:
                    handle_browser_launch_error(e, self.error_signal); return

                page = get_active_page(browser)
                
                # ====================================================
                # HỌC TÊN PROFILE GỐC ĐỂ ĐỔI LẠI SAU KHI ĐĂNG PAGE
                # ====================================================
                page.goto("https://www.facebook.com/")
                page.wait_for_load_state('domcontentloaded')
                time.sleep(3)
                main_profile_name = ""
                try:
                    nav_links = page.locator("div[role='navigation'] ul li a")
                    if nav_links.count() > 0:
                        raw_name = nav_links.first.inner_text()
                        main_profile_name = raw_name.split('\n')[0].strip()
                        if main_profile_name:
                            self.log_signal.emit(f"👤 Tự động nhận diện Profile gốc: {main_profile_name}")
                except: pass

                success_count = 0
                
                for url in self.urls:
                    switched_profile = False 
                    
                    self.log_signal.emit(f"\n>> Đang xử lý: {url}")
                    page.goto(url)
                    page.wait_for_load_state('domcontentloaded')
                    time.sleep(3) 

                    # BƯỚC 0: ĐỔI SANG FANPAGE (NẾU YÊU CẦU)
                    switch_selectors = ["div[role='button']:has-text('Chuyển ngay')", "span:has-text('Chuyển ngay')"]
                    for sel in switch_selectors:
                        try:
                            if page.locator(sel).count() > 0:
                                self.log_signal.emit("Yêu cầu đổi Profile! Đang tự động bấm 'Chuyển ngay'...")
                                page.locator(sel).first.click(timeout=3000)
                                switched_profile = True 
                                time.sleep(5) 
                                break
                        except: pass

                    # ---------------------------------------------------------
                    # BƯỚC 0.5: VƯỢT TƯỜNG LỬA CỦA CÁC NHÓM MUA BÁN/BẤT ĐỘNG SẢN
                    # ---------------------------------------------------------
                    if "/groups/" in url:
                        self.log_signal.emit("Đang đưa nhóm về chế độ Đăng bài tiêu chuẩn...")
                        try:
                            tab_thao_luan = page.locator("a[role='tab']:has-text('Thảo luận'), div[role='tablist'] a:has-text('Thảo luận')")
                            if tab_thao_luan.count() > 0:
                                tab_thao_luan.first.click(timeout=3000)
                                time.sleep(3)
                        except: pass

                    # BƯỚC 1: TÌM BẢNG POPUP ĐĂNG BÀI
                    post_box_selectors = [
                        "div[role='button']:has-text('Bạn đang nghĩ gì')",
                        "div[role='button']:has-text('Viết gì đó')",
                        "div[role='button']:has-text('Bạn viết gì đi')", 
                        "div[role='button']:has-text('Tạo bài viết')", 
                        "span:has-text('Tạo bài viết')",               
                        "xpath=//span[contains(text(), 'Bạn đang nghĩ gì')]",
                        "xpath=//div[contains(text(), 'Tạo bài viết')]" 
                    ]

                    clicked = False
                    for selector in post_box_selectors:
                        try:
                            if page.locator(selector).count() > 0:
                                page.locator(selector).first.click(timeout=3000)
                                clicked = True
                                break
                        except: continue

                    if not clicked:
                        self.log_signal.emit(f"-> BỎ QUA: Không tìm thấy nút mở bảng đăng bài.")
                        continue

                    # ---------------------------------------------------------
                    # BƯỚC 2: GÕ VĂN BẢN (ĐÃ KHẮC PHỤC LỖI NHIỀU Ô NHẬP CHỮ)
                    # ---------------------------------------------------------
                    self.log_signal.emit("Đang tìm ô nhập văn bản...")
                    try:
                        modal_textbox = page.locator("div[role='dialog'] div[role='textbox']")
                        if modal_textbox.count() > 0:
                            # LUÔN CHỌN Ô CUỐI CÙNG (.last) ĐỂ TRÁNH Ô TIÊU ĐỀ
                            modal_textbox.last.click(timeout=3000)
                        else:
                            page.locator("xpath=//div[@role='textbox']").last.click(timeout=3000)
                    except Exception as e:
                        self.log_signal.emit(f"Cảnh báo click ô nhập: {str(e)}")

                    self.log_signal.emit("Đang gõ phím siêu tốc...")
                    for char in self.content:
                        # Giảm thời gian chờ xuống chỉ còn 2 đến 10 mili-giây
                        page.keyboard.type(char, delay=random.uniform(2, 10)) 
                    time.sleep(1)

                    # BƯỚC 3: UPLOAD ẢNH
                    if self.image_paths:
                        self.log_signal.emit(f"Đang tải lên {len(self.image_paths)} file đính kèm...")
                        try:
                            photo_icons = ["div[role='dialog'] div[aria-label='Ảnh/video']", "div[role='dialog'] div[aria-label='Thêm ảnh/video']"]
                            icon_clicked = False
                            for icon in photo_icons:
                                if page.locator(icon).count() > 0:
                                    with page.expect_file_chooser(timeout=5000) as fc_info:
                                        page.locator(icon).first.click(timeout=2000)
                                    fc_info.value.set_files(self.image_paths)
                                    icon_clicked = True
                                    break

                            if not icon_clicked:
                                multiple_input = page.locator("div[role='dialog'] input[type='file'][multiple]")
                                if multiple_input.count() > 0:
                                    multiple_input.first.set_input_files(self.image_paths)
                                else:
                                    page.locator("input[type='file']").last.set_input_files(self.image_paths)
                            
                            wait_time = max(5, len(self.image_paths) * 3)
                            self.log_signal.emit(f"Chờ {wait_time} giây để FB xử lý dữ liệu ảnh...")
                            time.sleep(wait_time) 
                        except Exception as e:
                            self.log_signal.emit(f"Lỗi tải ảnh: {str(e)}")
                    time.sleep(1)
                    
                    # BƯỚC 4: BẤM XUẤT BẢN ĐA BƯỚC
                    self.log_signal.emit("Đang xử lý quy trình xuất bản...")
                    try:
                        btn_tiep_selectors = ["div[role='dialog'] div[aria-label='Tiếp']", "div[aria-label='Tiếp']"]
                        for sel in btn_tiep_selectors:
                            if page.locator(sel).count() > 0:
                                page.locator(sel).first.click()
                                time.sleep(3) 
                                break
                        
                        btn_post_selectors = ["div[role='dialog'] div[aria-label='Đăng']", "div[aria-label='Đăng']", "div[role='dialog'] div[aria-label='Xuất bản']"]
                        for sel in btn_post_selectors:
                            if page.locator(sel).count() > 0:
                                page.locator(sel).first.click()
                                time.sleep(4) 
                                break
                    except Exception as e:
                        self.log_signal.emit("Lưu ý: Không tự bấm được nút Đăng.")

                    # BƯỚC 5: DỌN DẸP POPUP (WHATSAPP...)
                    try:
                        close_popups = ["div[role='dialog'] div[aria-label='Lúc khác']", "div[aria-label='Lúc khác']"]
                        for sel in close_popups:
                            if page.locator(sel).count() > 0:
                                page.locator(sel).first.click(timeout=2000)
                                time.sleep(2)
                                break
                    except: pass
                    
                    self.log_signal.emit(f"-> THÀNH CÔNG!")
                    success_count += 1
                    
                    # BƯỚC 6: HOÀN TRẢ PROFILE CÁ NHÂN
                    if switched_profile:
                        self.log_signal.emit("Đang hoàn trả lại Profile cá nhân gốc...")
                        try:
                            page.goto("https://www.facebook.com/")
                            time.sleep(3)
                            account_btns = ["div[role='banner'] div[aria-label='Tài khoản']", "svg[aria-label='Tài khoản']"]
                            for btn in account_btns:
                                if page.locator(btn).count() > 0:
                                    page.locator(btn).first.click(timeout=3000)
                                    time.sleep(2)
                                    break
                            
                            switch_btns = ["div[aria-label*='Chuyển sang']", "div[aria-label*='Switch to']"]
                            if main_profile_name:
                                switch_btns.append(f"div[role='button']:has-text('{main_profile_name}')")
                            
                            switched_back = False
                            for btn in switch_btns:
                                if page.locator(btn).count() > 0:
                                    page.locator(btn).first.click(timeout=3000)
                                    switched_back = True
                                    time.sleep(4) 
                                    break
                            
                            if not switched_back:
                                btn_xem_tat_ca = ["div[role='button']:has-text('Xem tất cả')"]
                                for x_btn in btn_xem_tat_ca:
                                    if page.locator(x_btn).count() > 0:
                                        page.locator(x_btn).first.click()
                                        time.sleep(2)
                                        if main_profile_name:
                                            target = page.locator(f"div[role='dialog'] div[role='button']:has-text('{main_profile_name}')")
                                            if target.count() > 0:
                                                target.first.click()
                                                time.sleep(4)
                                        break
                        except Exception as e:
                            self.log_signal.emit("Cảnh báo: Không tự chuyển về Profile gốc được.")

                    rest_time = random.randint(5, 10) 
                    self.log_signal.emit(f"Nghỉ {rest_time}s trước khi sang mục tiêu tiếp theo...")
                    time.sleep(rest_time) 

                browser.close()
                self.finished_signal.emit(f"Hoàn tất! Đã đăng xong {success_count}/{len(self.urls)} mục tiêu.")

        except Exception as e:
            self.error_signal.emit(f"Lỗi hệ thống: {str(e)}")

class LogoutThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str) # <--- BẠN BỔ SUNG DÒNG NÀY VÀO ĐÂY NHÉ

    def run(self):
        try:
            with sync_playwright() as p:
                try:
                    # Mở lại Profile hiện tại
                    browser = p.chromium.launch_persistent_context(
                        user_data_dir=get_profile_dir(), headless=False, 
                        args=['--disable-blink-features=AutomationControlled']
                    )
                except Exception as e:
                    handle_browser_launch_error(e, self.error_signal); return
                
                page = get_active_page(browser)
                
                self.log_signal.emit("Đang truy cập trang chủ Facebook để đăng xuất...")
                page.goto("https://www.facebook.com/")
                page.wait_for_load_state('domcontentloaded')
                time.sleep(3)
                
                # 1. TÌM VÀ BẤM VÀO AVATAR Ở GÓC TRÊN BÊN PHẢI
                self.log_signal.emit("Đang tìm menu Tài khoản...")
                account_btns = [
                    "div[role='banner'] div[aria-label='Tài khoản']", 
                    "svg[aria-label='Tài khoản']",
                    "div[role='banner'] div[aria-label='Trang cá nhân của bạn']",
                    "svg[aria-label='Trang cá nhân của bạn']",
                    "div[role='banner'] div[role='button'] img", 
                    "div[role='banner'] svg image",              
                    "xpath=(//div[@role='banner']//div[@role='button'])[last()]" 
                ]
                
                clicked_avatar = False
                for btn in account_btns:
                    if page.locator(btn).count() > 0:
                        page.locator(btn).first.click(timeout=3000)
                        clicked_avatar = True
                        time.sleep(2) 
                        break
                
                if not clicked_avatar:
                    self.log_signal.emit("Cảnh báo: Không tìm thấy Avatar để mở menu Đăng xuất.")
                
                # 2. BẤM NÚT ĐĂNG XUẤT
                self.log_signal.emit("Đang tiến hành Đăng xuất...")
                logout_btns = [
                    "div[role='button']:has-text('Đăng xuất')", 
                    "span:has-text('Đăng xuất')", 
                    "div[role='button']:has-text('Log out')",
                    "xpath=//span[contains(text(), 'Đăng xuất')]",
                    "xpath=//div[contains(text(), 'Đăng xuất')]"
                ]
                for btn in logout_btns:
                    if page.locator(btn).count() > 0:
                        page.locator(btn).first.click(timeout=3000)
                        time.sleep(4) 
                        break
                
                browser.close()
                self.finished_signal.emit("Đã đăng xuất thành công! Trình duyệt đã sẵn sàng cho tài khoản mới.")
        except Exception as e:
            self.error_signal.emit(f"Lỗi đăng xuất: {str(e)}")