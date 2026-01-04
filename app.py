"""
API NgânMiu v3 - Complete Edition
- ✅ V3: Check kích hoạt trực tiếp trong tab "Kích hoạt GGS" (KHÔNG CẦN KeyCheckMVD riêng)
- ✅ Giữ nguyên tất cả tính năng v2
- ✅ Thêm: GHN tracking, SPX tracking qua tramavandan.com

Author: NgânMiu.Store
Contact: 0819.555.000
"""

from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "nganmiu-api-secret-2026")

# ========== CONFIG ==========
CONTACT_PHONE = os.getenv("CONTACT_PHONE", "0819.555.000")
CACHE_TTL = 86400  # 24 giờ

# Google Sheets
GS_CREDS_JSON = os.getenv("GOOGLE_SHEETS_CREDS_JSON", "")
GS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Shopee API
UA = "Android app Shopee appver=28320 app_type=1"
BASE = "https://shopee.vn/api/v4"

# ========== GOOGLE SHEETS CLIENT ==========
_gspread = None
_Credentials = None

def _gs_client():
    """Khởi tạo gspread client"""
    global _gspread, _Credentials
    if _gspread is None or _Credentials is None:
        import gspread
        from google.oauth2.service_account import Credentials
        _gspread = gspread
        _Credentials = Credentials
    
    data = json.loads(GS_CREDS_JSON)
    creds = _Credentials.from_service_account_info(data, scopes=GS_SCOPES)
    return _gspread.authorize(creds)

# ========== CACHE ==========
_cache = {}  # {key: (data, expire_timestamp)}

def get_cache(key: str):
    """Lấy cache, tự động xóa nếu hết hạn"""
    import time
    if key in _cache:
        data, expire_at = _cache[key]
        if time.time() < expire_at:
            return data
        else:
            del _cache[key]
    return None

def set_cache(key: str, value: dict, ttl: int = CACHE_TTL):
    """Lưu cache với TTL"""
    import time
    _cache[key] = (value, time.time() + ttl)

# ========== ✅ V3: VERIFY SHEET ID - CHECK TRỰC TIẾP TRONG SHEET USER ==========

def verify_sheet_id(sheet_id: str) -> dict:
    """
    ✅ V3: Kiểm tra kích hoạt TRỰC TIẾP trong tab "Kích hoạt GGS" của user
    KHÔNG CẦN KeyCheckMVD riêng nữa
    
    QUAN TRỌNG: KHÔNG cache - phải check realtime để admin kích hoạt tức thì có hiệu lực
    
    Return:
        {
            "valid": True/False,
            "msg": "...",
            "expire_at": "2026-12-31" (nếu có)
        }
    """
    try:
        gc = _gs_client()
        
        # Mở chính sheet của user
        try:
            spreadsheet = gc.open_by_key(sheet_id)
        except Exception as e:
            # Không mở được sheet → cho phép (fail-open)
            print(f"⚠️ Cannot open sheet {sheet_id}: {e}")
            return {"valid": True, "msg": "OK (cannot open sheet)"}
        
        # Tìm tab "Kích hoạt GGS"
        try:
            activation_sheet = spreadsheet.worksheet("Kích hoạt GGS")
        except Exception:
            # Không có tab "Kích hoạt GGS" → chưa kích hoạt
            return {
                "valid": False,
                "msg": f"🔒 Chưa gửi yêu cầu kích hoạt.\nVui lòng click menu 'Gửi yêu cầu kích hoạt'.\n📞 Liên hệ: {CONTACT_PHONE}"
            }
        
        # Đọc data từ tab "Kích hoạt GGS"
        try:
            all_values = activation_sheet.get_all_values()
            if len(all_values) < 2:
                # Tab có nhưng chưa có data → chưa kích hoạt
                return {
                    "valid": False,
                    "msg": f"🔒 Sheet chưa được kích hoạt.\n📞 Liên hệ: {CONTACT_PHONE}"
                }
            
            # Tìm hàng có sheet_id này (cột B - index 1)
            # Header: Thời gian | Sheet ID | Tên Sheet | Email | Trạng thái
            for row in all_values[1:]:  # Bỏ header
                if len(row) < 5:
                    continue
                
                row_sheet_id = str(row[1]).strip()
                if row_sheet_id == sheet_id:
                    # Tìm thấy!
                    status = str(row[4]).strip() if len(row) > 4 else ""
                    
                    # Check status
                    if status == "Đã kích hoạt":
                        # ✅ ĐƯỢC KÍCH HOẠT
                        return {
                            "valid": True,
                            "expire_at": None,
                            "msg": "OK"
                        }
                    elif status == "Từ chối":
                        # ❌ BỊ TỪ CHỐI
                        return {
                            "valid": False,
                            "msg": f"🔒 Yêu cầu kích hoạt bị từ chối.\n📞 Liên hệ: {CONTACT_PHONE}"
                        }
                    elif status == "Hết hạn":
                        # ❌ HẾT HẠN
                        return {
                            "valid": False,
                            "msg": f"🔒 Sheet đã hết hạn sử dụng.\n📞 Liên hệ: {CONTACT_PHONE}"
                        }
                    else:
                        # ⏳ CHỜ KÍCH HOẠT
                        return {
                            "valid": False,
                            "msg": f"🔒 Sheet đang chờ kích hoạt.\n📞 Liên hệ: {CONTACT_PHONE}"
                        }
            
            # Không tìm thấy sheet_id trong tab → chưa gửi yêu cầu
            return {
                "valid": False,
                "msg": f"🔒 Chưa gửi yêu cầu kích hoạt.\nVui lòng click menu 'Gửi yêu cầu kích hoạt'.\n📞 Liên hệ: {CONTACT_PHONE}"
            }
            
        except Exception as e:
            # Lỗi đọc data → cho phép (fail-open)
            print(f"⚠️ Error reading activation data: {e}")
            return {"valid": True, "msg": "OK (read error)"}
            
    except Exception as e:
        # Lỗi chung → cho phép (fail-open)
        print(f"⚠️ Error in verify_sheet_id: {e}")
        return {"valid": True, "msg": "OK (general error)"}

# ========== SHOPEE API FUNCTIONS ==========

def fetch_shopee_order_detail(cookie: str, order_id: str) -> dict:
    """
    Lấy chi tiết 1 đơn từ Shopee
    """
    url = f"{BASE}/order/get_order_detail"
    headers = {
        "cookie": cookie,
        "user-agent": UA,
        "referer": "https://shopee.vn/"
    }
    params = {"order_id": order_id}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()
        
        if data.get("error") != 0:
            return None
        
        d = data.get("data", {})
        
        # Parse product name
        product_name = ""
        try:
            items = d.get("info_card", {}).get("parcel_cards", [{}])[0] \
                     .get("product_info", {}).get("item_groups", [{}])[0] \
                     .get("items", [])
            product_name = ", ".join([i.get("name", "") for i in items if i.get("name")])
        except:
            product_name = "—"
        
        # Parse COD (fix bug dư 5 số 0)
        cod = 0
        try:
            final_total = d.get("info_card", {}).get("final_total", 0)
            if final_total > 0:
                cod = int(final_total / 100000)
        except:
            cod = 0
        
        # Username
        username = str(d.get("username", "") or d.get("account", {}).get("username", ""))
        
        return {
            "tracking_no": d.get("tracking_no", ""),
            "status": d.get("status", {}).get("list_view_text", {}).get("text", ""),
            "shipping_name": d.get("address", {}).get("shipping_name", ""),
            "shipping_phone": d.get("address", {}).get("shipping_phone", ""),
            "shipping_address": d.get("address", {}).get("shipping_address", ""),
            "product_name": product_name,
            "cod": cod,
            "shipper_name": d.get("shipping", {}).get("shipper_name", ""),
            "shipper_phone": d.get("shipping", {}).get("shipper_phone", ""),
            "username": username
        }
        
    except Exception as e:
        return None

def fetch_all_orders_from_cookie(cookie: str, limit: int = 50) -> list:
    """
    Lấy tất cả đơn hàng từ cookie (NGƯỜI MUA)
    Logic từ API nganmiu.store (đang chạy tốt)
    """
    url = f"{BASE}/order/get_all_order_and_checkout_list"
    headers = {
        "cookie": cookie,
        "user-agent": UA,
        "referer": "https://shopee.vn/"
    }
    params = {
        "limit": limit,
        "offset": 0
    }
    
    try:
        # Bước 1: Lấy list order_id
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()
        
        if data.get("error") != 0:
            return []
        
        # Lấy tất cả order_id từ response (BFS search)
        order_ids = []
        def extract_order_ids(obj):
            if isinstance(obj, dict):
                if "order_id" in obj and obj["order_id"]:
                    order_ids.append(obj["order_id"])
                for v in obj.values():
                    extract_order_ids(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_order_ids(item)
        
        extract_order_ids(data)
        
        # Loại bỏ trùng lặp
        seen = set()
        unique_ids = []
        for oid in order_ids:
            if oid not in seen:
                seen.add(oid)
                unique_ids.append(oid)
        
        if not unique_ids:
            return []
        
        # Bước 2: Lấy chi tiết từng đơn
        orders = []
        for order_id in unique_ids[:limit]:
            order_detail = fetch_shopee_order_detail(cookie, order_id)
            if order_detail:
                orders.append(order_detail)
        
        return orders
        
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return []

# ========== ✅ SPX TRACKING (tramavandan.com) ==========

def check_spx_tramavandan(tracking_no: str) -> dict:
    """
    Tracking SPX qua tramavandan.com
    
    Return:
        {
            "error": 0/1,
            "timeline": [...],
            "status": "...",
            "phone": "...",
            "eta": "..."
        }
    """
    SPX_API = "https://tramavandon.com/api/spx.php"
    
    payload = {"tracking_id": tracking_no.strip().upper()}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Connection": "close"
    }
    
    try:
        import re
        r = requests.post(SPX_API, json=payload, headers=headers, timeout=10)
        data = r.json()
        
        if data.get("retcode") != 0:
            return {
                "error": 1,
                "msg": "Không tìm thấy thông tin MVĐ"
            }
        
        info = data["data"]["sls_tracking_info"]
        records = info.get("records", [])
        
        timeline = []
        phone = ""
        last_ts = None
        
        for rec in records:
            ts = rec.get("actual_time")
            if not ts:
                continue
            
            last_ts = ts
            dt = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
            
            status_text = rec.get("buyer_description", "").strip()
            location = rec.get("current_location", {}).get("location_name", "").strip()
            
            # Tìm SĐT shipper
            if not phone:
                found = re.findall(r"\b0\d{9,10}\b", status_text)
                if found:
                    phone = found[0]
            
            line = f"{dt} — {status_text}"
            if location:
                line += f" — {location}"
            
            timeline.append(line)
        
        # Dự kiến giao (ước tính)
        eta = "-"
        if last_ts:
            eta_dt = datetime.fromtimestamp(last_ts) + timedelta(days=1)
            eta = eta_dt.strftime("%d/%m/%Y")
        
        return {
            "error": 0,
            "timeline": timeline[-5:] if timeline else [],
            "status": timeline[0] if timeline else "Đang vận chuyển",
            "phone": phone,
            "eta": eta
        }
        
    except Exception as e:
        return {
            "error": 1,
            "msg": f"Lỗi kết nối: {str(e)}"
        }

# ========== ✅ GHN TRACKING ==========

GHN_STATUS_EMOJI = {
    "Chờ lấy hàng": "🕓",
    "Nhận hàng tại bưu cục": "📦",
    "Sẵn sàng xuất đến Kho trung chuyển": "🚚",
    "Xuất hàng đi khỏi kho": "🚛",
    "Đang trung chuyển hàng": "🚚",
    "Nhập hàng vào kho trung chuyển": "🏬",
    "Đang giao hàng": "🚴",
    "Giao hàng thành công": "✅",
    "Giao hàng không thành công": "❌",
    "Hoàn hàng": "↩️"
}

def clean_ghn_status(text: str) -> str:
    """Cắt bỏ nhãn trạng thái chung, giữ mô tả chi tiết"""
    if not text:
        return ""
    
    text = text.strip()
    
    if " – " in text:
        return text.split(" – ", 1)[1].strip()
    
    if " - " in text:
        return text.split(" - ", 1)[1].strip()
    
    return text

def check_ghn(order_code: str, max_steps: int = 4) -> dict:
    """
    Tracking GHN
    
    Return:
        {
            "error": 0/1,
            "status_name": "...",
            "emoji": "...",
            "eta": "...",
            "timeline": [...]
        }
    """
    url = "https://fe-online-gateway.ghn.vn/order-tracking/public-api/client/tracking-logs"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://donhang.ghn.vn",
        "Referer": "https://donhang.ghn.vn/",
        "User-Agent": "Mozilla/5.0"
    }
    
    payload = {"order_code": order_code.strip()}
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        res = r.json()
    except Exception as e:
        return {
            "error": 1,
            "msg": f"Không kết nối được GHN: {str(e)}"
        }
    
    if res.get("code") != 200:
        return {
            "error": 1,
            "msg": "Không tìm thấy đơn GHN"
        }
    
    data = res.get("data", {})
    info = data.get("order_info", {})
    logs = data.get("tracking_logs", [])
    
    # Header
    status_name = info.get("status_name", "-")
    emoji = GHN_STATUS_EMOJI.get(status_name, "🚚")
    
    # ETA
    eta = "-"
    leadtime = info.get("leadtime")
    if leadtime:
        try:
            eta = datetime.fromisoformat(leadtime.replace("Z", "")).strftime("%d/%m/%Y")
        except:
            eta = leadtime[:10]
    
    # Timeline
    timeline = []
    last_key = None
    
    for lg in reversed(logs):
        status = clean_ghn_status(lg.get("status_name", "").strip())
        addr = lg.get("location", {}).get("address", "").strip()
        
        if not status:
            continue
        
        # Chống trùng
        key = f"{status}|{addr}"
        if key == last_key:
            continue
        
        t = lg.get("action_at", "")
        if t:
            try:
                t = datetime.fromisoformat(t.replace("Z", "")).strftime("%d/%m %H:%M")
            except:
                t = t.replace("T", " ")[:16]
        
        content = status
        if addr and addr not in status:
            content = f"{status} — {addr}"
        
        timeline.append(f"{t} — {content}")
        last_key = key
        
        if len(timeline) >= max_steps:
            break
    
    if not timeline:
        timeline.append("Chưa có lịch trình")
    
    return {
        "error": 0,
        "status_name": status_name,
        "emoji": emoji,
        "eta": eta,
        "timeline": timeline
    }

# ========== API ENDPOINTS ==========

@app.route("/", methods=["GET"])
def home():
    """API info"""
    return jsonify({
        "name": "API NgânMiu v3",
        "version": "3.0.0",
        "description": "Auto-activation via 'Kích hoạt GGS' tab",
        "contact": CONTACT_PHONE,
        "endpoints": {
            "check_cookie_v2": "POST /api/check-cookie-v2 (with auto-activation)",
            "spx_tracking": "GET /api/spx-track?mvd=SPXVN...",
            "ghn_tracking": "GET /api/ghn-track?code=GHN...",
            "spx_tramavandan": "GET /api/spx-tramavandan?mvd=SPXVN..."
        }
    })

@app.route("/api/check-cookie-v2", methods=["POST"])
def check_cookie_v2():
    """
    API v2 - Check cookie với auto-activation
    """
    data = request.get_json() or {}
    
    cookie = data.get("cookie", "").strip()
    sheet_id = data.get("sheet_id", "").strip()
    
    if not cookie:
        return jsonify({"error": 1, "msg": "Thiếu cookie"}), 400
    
    if not sheet_id:
        return jsonify({"error": 1, "msg": "Thiếu sheet_id"}), 400
    
    # ===== VERIFY SHEET ID =====
    verify_result = verify_sheet_id(sheet_id)
    
    if not verify_result["valid"]:
        return jsonify({
            "error": 1,
            "msg": verify_result["msg"]
        }), 403
    
    # ===== CHECK CACHE =====
    cache_key = f"v3:{sheet_id}:{cookie[:50]}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        return jsonify({
            "error": 0,
            "orders": cached_data,
            "total": len(cached_data),
            "cached": True,
            "expire_at": verify_result.get("expire_at")
        })
    
    # ===== FETCH SHOPEE =====
    orders = fetch_all_orders_from_cookie(cookie, limit=50)
    
    if not orders:
        # Cookie LIVE nhưng chưa có đơn → error=0 (không phải lỗi)
        result = {
            "error": 0,
            "orders": [],
            "total": 0,
            "cached": False,
            "msg": "Cookie hợp lệ nhưng chưa có đơn hàng"
        }
        set_cache(cache_key, result, 3600)  # Cache 1h cho trường hợp này
        return jsonify(result)
    
    # ===== SAVE CACHE =====
    set_cache(cache_key, orders, CACHE_TTL)
    
    return jsonify({
        "error": 0,
        "orders": orders,
        "total": len(orders),
        "cached": False,
        "expire_at": verify_result.get("expire_at")
    })

@app.route("/api/spx-track", methods=["GET"])
def spx_track_simple():
    """
    SPX tracking đơn giản (legacy - giữ tương thích)
    """
    mvd = request.args.get("mvd", "").strip()
    
    if not mvd:
        return jsonify({"error": 1, "msg": "Thiếu MVĐ"}), 400
    
    result = check_spx_tramavandan(mvd)
    return jsonify(result)

@app.route("/api/spx-tramavandan", methods=["GET"])
def spx_track_tramavandan():
    """
    SPX tracking qua tramavandan.com (chi tiết hơn)
    """
    mvd = request.args.get("mvd", "").strip()
    
    if not mvd:
        return jsonify({"error": 1, "msg": "Thiếu MVĐ"}), 400
    
    result = check_spx_tramavandan(mvd)
    return jsonify(result)

@app.route("/api/ghn-track", methods=["GET"])
def ghn_track():
    """
    GHN tracking
    """
    code = request.args.get("code", "").strip()
    
    if not code:
        return jsonify({"error": 1, "msg": "Thiếu mã GHN"}), 400
    
    result = check_ghn(code)
    return jsonify(result)

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "error": 1,
        "msg": "Endpoint không tồn tại",
        "contact": CONTACT_PHONE
    }), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "error": 1,
        "msg": "Lỗi server nội bộ",
        "contact": CONTACT_PHONE
    }), 500

# ========== MAIN ==========

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
