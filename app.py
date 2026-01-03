"""
API NgânMiu - Tổng hợp API cho Shopee Tools
Author: NgânMiu.Store
Contact: 0819.555.000

Endpoints:
- POST /api/check-cookie - Check cookie Shopee (legacy)
- POST /api/check-cookie-v2 - Check cookie với verify Sheet ID
- POST /api/spx-track - Tracking SPX đơn giản
- POST /api/admin/add-sheet - Admin thêm Sheet ID
"""

from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "nganmiu-api-secret-2026")

# ========== CONFIG ==========
CONTACT_PHONE = os.getenv("CONTACT_PHONE", "0819.555.000")
CACHE_TTL = 86400  # 24 giờ

# Google Sheets
KEYCHECK_SHEET_ID = os.getenv("KEYCHECK_SHEET_ID", "")
GS_CREDS_JSON = os.getenv("GOOGLE_SHEETS_CREDS_JSON", "")
GS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Admin
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

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

# ========== HELPER FUNCTIONS ==========

def verify_sheet_id(sheet_id: str) -> dict:
    """
    Kiểm tra sheet_id trong Sheet KeyCheckMVD
    
    Return:
        {
            "valid": True/False,
            "msg": "...",
            "expire_at": "2026-12-31" (nếu có)
        }
    """
    if not KEYCHECK_SHEET_ID:
        # Nếu chưa config → cho phép tất cả (dev mode)
        return {"valid": True, "msg": "OK (no verification)"}
    
    try:
        gc = _gs_client()
        sh = gc.open_by_key(KEYCHECK_SHEET_ID)
        ws = sh.worksheet("KeyCheckMVD")
        
        rows = ws.get_all_records()
        
        for r in rows:
            if str(r.get("sheet_id", "")).strip() == sheet_id:
                status = str(r.get("status", "")).lower().strip()
                
                # Kiểm tra banned
                if status == "banned":
                    return {
                        "valid": False,
                        "msg": f"❌ Tài khoản đã bị khóa.\n📞 Liên hệ: {CONTACT_PHONE}"
                    }
                
                # Kiểm tra active
                if status != "active":
                    return {
                        "valid": False,
                        "msg": f"⚠️ Tài khoản chưa kích hoạt.\n📞 Liên hệ: {CONTACT_PHONE}"
                    }
                
                # Kiểm tra expire
                exp = r.get("expire_at")
                if exp:
                    try:
                        exp_date = datetime.strptime(str(exp), "%Y-%m-%d")
                        if exp_date < datetime.now():
                            return {
                                "valid": False,
                                "msg": f"⏰ Gói đã hết hạn ({exp}).\n📞 Liên hệ: {CONTACT_PHONE} để gia hạn"
                            }
                    except:
                        pass
                
                # ✅ Hợp lệ
                return {
                    "valid": True,
                    "expire_at": exp,
                    "msg": "OK"
                }
        
        # Không tìm thấy sheet_id
        return {
            "valid": False,
            "msg": f"🔒 Sheet chưa được kích hoạt.\n📞 Liên hệ: {CONTACT_PHONE} để kích hoạt"
        }
        
    except Exception as e:
        # Lỗi kết nối → cho phép (fail-open)
        return {
            "valid": True,
            "msg": f"⚠️ Lỗi verify: {str(e)}"
        }

def fetch_shopee_order_detail(cookie: str, order_id: str) -> dict:
    """
    Lấy chi tiết 1 đơn từ Shopee
    
    Return:
        {
            "tracking_no": "SPXVN...",
            "status": "...",
            "shipping_name": "...",
            "shipping_phone": "...",
            "shipping_address": "...",
            "product_name": "...",
            "cod": 80000,
            "shipper_name": "",
            "shipper_phone": "",
            "username": ""
        }
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
    Lấy tất cả đơn hàng từ cookie
    
    Return: List[dict] - danh sách đơn
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
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()
        
        if data.get("error") != 0:
            return []
        
        details = data.get("data", {}).get("details", [])
        if not details:
            return []
        
        orders = []
        for detail in details:
            order_id = detail.get("info", {}).get("order_id")
            if not order_id:
                continue
            
            order_detail = fetch_shopee_order_detail(cookie, order_id)
            if order_detail:
                orders.append(order_detail)
        
        return orders
        
    except Exception as e:
        return []

# ========== API ENDPOINTS ==========

@app.route("/", methods=["GET"])
def home():
    """API info"""
    return jsonify({
        "name": "API NgânMiu",
        "version": "2.0.0",
        "contact": CONTACT_PHONE,
        "endpoints": {
            "check_cookie_legacy": "POST /api/check-cookie",
            "check_cookie_v2": "POST /api/check-cookie-v2",
            "spx_tracking": "GET /api/spx-track?mvd=SPXVN...",
            "admin_add_sheet": "POST /api/admin/add-sheet"
        }
    })

@app.route("/api/check-cookie", methods=["POST"])
def check_cookie_legacy():
    """
    API legacy - Check cookie (không verify Sheet ID)
    
    Request:
        {
            "cookie": "SPC_ST=..."
        }
    
    Response:
        {
            "data": {
                "tracking_no": "...",
                "status": "...",
                ...
            }
        }
    """
    data = request.get_json() or {}
    cookie = data.get("cookie", "").strip()
    
    if not cookie:
        return jsonify({"error": 1, "msg": "Thiếu cookie"}), 400
    
    # Cache
    cache_key = f"legacy:{cookie[:50]}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)
    
    # Fetch
    orders = fetch_all_orders_from_cookie(cookie, limit=1)
    
    if not orders:
        result = {"error": 1, "msg": "Cookie không hợp lệ hoặc không có đơn"}
    else:
        result = {"data": orders[0]}
    
    # Cache
    set_cache(cache_key, result, 3600)  # 1 giờ
    
    return jsonify(result)

@app.route("/api/check-cookie-v2", methods=["POST"])
def check_cookie_v2():
    """
    API v2 - Check cookie với verify Sheet ID
    
    Request:
        {
            "cookie": "SPC_ST=...",
            "sheet_id": "1ABC...XYZ"
        }
    
    Response (thành công):
        {
            "error": 0,
            "orders": [...],
            "total": 2,
            "cached": false,
            "expire_at": "2026-12-31"
        }
    
    Response (lỗi):
        {
            "error": 1,
            "msg": "Sheet chưa được kích hoạt..."
        }
    """
    data = request.get_json() or {}
    
    cookie = data.get("cookie", "").strip()
    sheet_id = data.get("sheet_id", "").strip()
    
    # Validate
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
    cache_key = f"v2:{sheet_id}:{cookie[:50]}"
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
        return jsonify({
            "error": 1,
            "msg": "Cookie không hợp lệ hoặc không có đơn hàng"
        }), 400
    
    # ===== SAVE CACHE =====
    set_cache(cache_key, orders, CACHE_TTL)
    
    # ===== RETURN =====
    return jsonify({
        "error": 0,
        "orders": orders,
        "total": len(orders),
        "cached": False,
        "expire_at": verify_result.get("expire_at")
    })

@app.route("/api/spx-track", methods=["GET"])
def spx_track():
    """
    Tracking SPX đơn giản
    
    Query:
        ?mvd=SPXVN066194857771&language_code=vi
    
    Response:
        {
            "error": 0,
            "timeline": [
                "2024-12-15 10:30 — Giao hàng thành công",
                "2024-12-14 08:00 — Đang giao hàng"
            ],
            "status": "Giao hàng thành công"
        }
    """
    mvd = request.args.get("mvd", "").strip()
    language_code = request.args.get("language_code", "vi")
    
    if not mvd:
        return jsonify({"error": 1, "msg": "Thiếu mã vận đơn"}), 400
    
    # Cache
    cache_key = f"spx:{mvd}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)
    
    # Call SPX API
    url = "https://spx.vn/shipment/order/open/order/get_order_info"
    params = {
        "spx_tn": mvd,
        "language_code": language_code
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get("code") != 0:
            result = {"error": 1, "msg": "Không tìm thấy MVĐ"}
        else:
            records = data.get("data", {}).get("sls_tracking_info", {}).get("records", [])
            
            timeline = []
            status = "Đang vận chuyển"
            
            for r in records:
                desc = r.get("description") or r.get("buyer_description") or ""
                time_str = r.get("actual_time", "")
                
                if desc:
                    if time_str:
                        try:
                            from datetime import datetime
                            ts = int(time_str) / 1000
                            dt = datetime.fromtimestamp(ts)
                            time_fmt = dt.strftime("%Y-%m-%d %H:%M")
                            timeline.append(f"{time_fmt} — {desc}")
                        except:
                            timeline.append(desc)
                    else:
                        timeline.append(desc)
                    
                    if "giao hàng thành công" in desc.lower():
                        status = "Giao hàng thành công"
            
            result = {
                "error": 0,
                "timeline": timeline,
                "status": status
            }
        
        # Cache 1 giờ
        set_cache(cache_key, result, 3600)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": 1,
            "msg": f"Lỗi kết nối SPX: {str(e)}"
        }), 500

@app.route("/api/admin/add-sheet", methods=["POST"])
def admin_add_sheet():
    """
    Admin API - Thêm Sheet ID vào KeyCheckMVD
    
    Request:
        {
            "admin_key": "SECRET_KEY",
            "sheet_id": "1ABC...XYZ",
            "expire_at": "2026-12-31",
            "note": "Khách VIP"
        }
    
    Response:
        {
            "error": 0,
            "msg": "Đã thêm Sheet ID thành công"
        }
    """
    if not ADMIN_API_KEY:
        return jsonify({"error": 1, "msg": "Admin API chưa được cấu hình"}), 500
    
    data = request.get_json() or {}
    
    # Auth
    if data.get("admin_key") != ADMIN_API_KEY:
        return jsonify({"error": 1, "msg": "Unauthorized"}), 403
    
    sheet_id = data.get("sheet_id", "").strip()
    expire_at = data.get("expire_at", "")
    note = data.get("note", "")
    
    if not sheet_id:
        return jsonify({"error": 1, "msg": "Thiếu sheet_id"}), 400
    
    if not KEYCHECK_SHEET_ID:
        return jsonify({"error": 1, "msg": "KEYCHECK_SHEET_ID chưa được cấu hình"}), 500
    
    try:
        gc = _gs_client()
        sh = gc.open_by_key(KEYCHECK_SHEET_ID)
        ws = sh.worksheet("KeyCheckMVD")
        
        # Thêm hàng mới
        ws.append_row([
            sheet_id,
            "active",
            expire_at,
            note
        ])
        
        return jsonify({
            "error": 0,
            "msg": "Đã thêm Sheet ID thành công"
        })
        
    except Exception as e:
        return jsonify({
            "error": 1,
            "msg": f"Lỗi: {str(e)}"
        }), 500

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
