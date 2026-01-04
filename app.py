"""
API NgânMiu FINAL - Người mua + Kích hoạt
- Logic từ API 1867 dòng (đang chạy tốt)
- Hệ thống kích hoạt qua Sheet ID
- Endpoint: /api/check-cookie-v2
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime, timedelta
from functools import lru_cache
import time

app = Flask(__name__)
CORS(app)

# ========== CONFIG ==========
BASE = "https://shopee.vn/api/v4"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ========== ERROR CLASSIFY (for Apps Script) ==========
# Đồng bộ với logic classifyCookieJson_ ở ShopeeAutoV2.gs
TEMP_ERROR_CODES = {408, 409, 425, 429, 500, 501, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526}
INVALID_HINTS = [
    "unauthorized", "forbidden", "invalid", "expire", "expired",
    "token", "cookie", "not logged", "please login", "auth", "ban", "banned",
    "login", "account", "session"
]
RATE_LIMIT_HINTS = ["too many", "rate limit", "request limit", "captcha", "throttle", "429"]

def _has_hint(s: str, hints) -> bool:
    t = (s or "").lower()
    return any(h in t for h in hints)

def _classify_shopee_failure(status_code: int, data_obj, raw_text: str):
    """Return (kind, msg, http_status): kind in {'auth_fail','temp_error','unknown'}"""
    raw_text = raw_text or ""
    msg = ""
    if isinstance(data_obj, dict):
        msg = str(data_obj.get("error_msg") or data_obj.get("msg") or data_obj.get("message") or "")
    joined = (msg + " " + raw_text)[:2000].lower()

    if status_code in TEMP_ERROR_CODES:
        return ("temp_error", f"HTTP {status_code}", status_code)
    if status_code in (401, 403):
        return ("auth_fail", msg or "Unauthorized/Forbidden", 401)

    # Shopee thường trả 200 nhưng error != 0 kèm thông báo "Please login"...
    if _has_hint(joined, INVALID_HINTS):
        return ("auth_fail", msg or "Auth fail", 401)

    if _has_hint(joined, RATE_LIMIT_HINTS):
        return ("temp_error", msg or "Rate limited", 429)

    # Mặc định coi là lỗi tạm (để không đánh nhầm cookie die)
    return ("temp_error", msg or "Shopee error", 503)

# Cache in-memory (simple dict)
CACHE = {}
CACHE_TTL = 7200  # 2 giờ

# ========== CACHE FUNCTIONS ==========
def get_cache(key):
    if key in CACHE:
        data, expire = CACHE[key]
        if time.time() < expire:
            return data
        else:
            del CACHE[key]
    return None

def set_cache(key, value, ttl):
    CACHE[key] = (value, time.time() + ttl)

# ========== GOOGLE SHEETS - VERIFY SHEET ID ==========
def verify_sheet_id(sheet_id: str) -> dict:
    """
    Check xem sheet_id có trong tab "Kích hoạt GGS" không
    """
    try:
        # Lấy credentials từ env
        creds_json = os.getenv("GOOGLE_SHEETS_CREDS_JSON")
        if not creds_json:
            # Fallback: Cho phép tất cả nếu không có credentials
            return {"valid": True, "msg": "OK (no verification)"}
        
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        creds_dict = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        service = build('sheets', 'v4', credentials=credentials)
        
        # Đọc tab "Kích hoạt GGS"
        sheet_name = "Kích hoạt GGS"
        range_name = f"{sheet_name}!A2:E1000"
        
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        rows = result.get('values', [])
        
        if not rows:
            return {
                "valid": False,
                "msg": "🔒 Sheet chưa được kích hoạt.\n📞 Liên hệ: " + os.getenv("CONTACT_PHONE", "0819.555.000")
            }
        
        # Tìm sheet_id trong cột B (index 1)
        for row in rows:
            if len(row) < 5:
                continue
            
            row_sheet_id = row[1].strip() if len(row) > 1 else ""
            status = row[4].strip() if len(row) > 4 else ""
            
            if row_sheet_id == sheet_id:
                if status == "Đã kích hoạt":
                    return {"valid": True, "msg": "OK"}
                else:
                    return {
                        "valid": False,
                        "msg": f"🔒 Sheet đang ở trạng thái: {status}\n📞 Liên hệ: " + os.getenv("CONTACT_PHONE", "0819.555.000")
                    }
        
        # Không tìm thấy sheet_id
        return {
            "valid": False,
            "msg": "🔒 Sheet chưa được kích hoạt.\n📞 Liên hệ: " + os.getenv("CONTACT_PHONE", "0819.555.000")
        }
        
    except Exception as e:
        print(f"⚠️ Error in verify_sheet_id: {e}")
        # Fallback: Cho phép nếu có lỗi (để không block user)
        return {"valid": True, "msg": "OK (error fallback)"}

# ========== SHOPEE API - FETCH ORDERS ==========
def fetch_orders_and_details(cookie: str, limit: int = 50):
    """
    Lấy list order_id từ Shopee (NGƯỜI MUA) rồi lấy chi tiết từng đơn.

    Trả về dict:
      - details: list[{order_id, raw}]
      - auth_fail: bool
      - temp_error: bool
      - status_code: int
      - msg: str
    """
    url = f"{BASE}/order/get_all_order_and_checkout_list"
    headers = {
        "cookie": cookie,
        "user-agent": UA,
        "referer": "https://shopee.vn/"
    }
    params = {"limit": limit, "offset": 0}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
    except Exception as e:
        return {
            "details": [],
            "temp_error": True,
            "auth_fail": False,
            "status_code": 503,
            "msg": f"Request error: {e}"
        }

    status_code = resp.status_code
    raw_text = resp.text or ""

    # HTTP lỗi tạm thời -> forward luôn
    if status_code in TEMP_ERROR_CODES:
        return {
            "details": [],
            "temp_error": True,
            "auth_fail": False,
            "status_code": status_code,
            "msg": f"HTTP {status_code}"
        }

    try:
        data = resp.json()
    except Exception:
        # Không parse được JSON: nếu có dấu hiệu auth -> auth_fail, không thì coi temp_error
        if _has_hint(raw_text, INVALID_HINTS):
            return {
                "details": [],
                "temp_error": False,
                "auth_fail": True,
                "status_code": 401,
                "msg": "Auth fail (non-json)"
            }
        return {
            "details": [],
            "temp_error": True,
            "auth_fail": False,
            "status_code": 503,
            "msg": "Shopee invalid JSON"
        }

    if not isinstance(data, dict):
        return {
            "details": [],
            "temp_error": True,
            "auth_fail": False,
            "status_code": 503,
            "msg": "Shopee response not dict"
        }

    if data.get("error") != 0:
        kind, msg, http_status = _classify_shopee_failure(status_code, data, raw_text)
        return {
            "details": [],
            "temp_error": (kind == "temp_error"),
            "auth_fail": (kind == "auth_fail"),
            "status_code": http_status,
            "msg": msg
        }

    # ===== BFS tìm tất cả order_id =====
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

    # Loại bỏ trùng
    seen = set()
    unique_ids = []
    for oid in order_ids:
        if oid not in seen:
            seen.add(oid)
            unique_ids.append(oid)

    # Lấy chi tiết từng đơn
    details = []
    for oid in unique_ids[:limit]:
        detail_data = fetch_order_detail(cookie, oid)
        if detail_data:
            details.append({"order_id": oid, "raw": detail_data})

    return {
        "details": details,
        "temp_error": False,
        "auth_fail": False,
        "status_code": 200,
        "msg": "OK"
    }

def fetch_order_detail(cookie: str, order_id: str):
    """
    Lấy chi tiết 1 đơn
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
        
        return data.get("data", {})
        
    except:
        return None

# ========== PARSE ORDER ==========
def find_first_key(obj, key):
    """Tìm key đầu tiên trong nested dict"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = find_first_key(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = find_first_key(item, key)
            if result is not None:
                return result
    return None

def pick_columns_from_detail(raw_data):
    """
    Parse thông tin đơn hàng từ raw data
    Logic từ API 1867 dòng
    """
    if not raw_data or not isinstance(raw_data, dict):
        return {}
    
    # Tracking number
    tracking_no = find_first_key(raw_data, "tracking_number") or \
                  find_first_key(raw_data, "tracking_no") or ""
    
    # Status
    status_obj = find_first_key(raw_data, "list_view_text")
    status_text = ""
    if isinstance(status_obj, dict):
        status_text = status_obj.get("text", "")
    if not status_text:
        status_text = find_first_key(raw_data, "status_label") or ""
    
    # Shipping info
    shipping_name = find_first_key(raw_data, "shipping_name") or ""
    shipping_phone = find_first_key(raw_data, "shipping_phone") or ""
    shipping_address = find_first_key(raw_data, "shipping_address") or ""
    
    # Product name - ƯU TIÊN từ items
    product_name = ""
    try:
        parcel_cards = find_first_key(raw_data, "parcel_cards")
        if isinstance(parcel_cards, list) and parcel_cards:
            p0 = parcel_cards[0] if isinstance(parcel_cards[0], dict) else {}
            pinfo = p0.get("product_info", {})
            groups = pinfo.get("item_groups", [])
            if groups and isinstance(groups[0], dict):
                items = groups[0].get("items", [])
                if isinstance(items, list):
                    names = [i.get("name", "") for i in items if isinstance(i, dict) and i.get("name")]
                    product_name = ", ".join(names)
    except:
        pass
    
    if not product_name:
        product_name = "—"
    
    # COD - FIX: chia 100000
    cod = 0
    try:
        final_total = find_first_key(raw_data, "final_total")
        if final_total and isinstance(final_total, (int, float)) and final_total > 0:
            cod = int(final_total / 100000)
    except:
        pass
    
    # Shipper
    shipper_name = find_first_key(raw_data, "shipper_name") or \
                   find_first_key(raw_data, "driver_name") or ""
    shipper_phone = find_first_key(raw_data, "shipper_phone") or \
                    find_first_key(raw_data, "driver_phone") or ""
    
    # Username
    username = find_first_key(raw_data, "username") or ""
    
    return {
        "tracking_no": tracking_no,
        "status_text": status_text,
        "shipping_name": shipping_name,
        "shipping_phone": shipping_phone,
        "shipping_address": shipping_address,
        "product_name": product_name,
        "cod": cod,
        "shipper_name": shipper_name,
        "shipper_phone": shipper_phone,
        "username": username
    }

def is_buyer_cancelled(raw_data):
    """Check xem đơn có bị buyer cancel không"""
    if not raw_data:
        return False
    
    # Tìm cancel info
    def tree_contains(obj, target):
        if isinstance(obj, dict):
            for v in obj.values():
                if tree_contains(v, target):
                    return True
        elif isinstance(obj, list):
            for v in obj:
                if tree_contains(v, target):
                    return True
        elif isinstance(obj, str):
            return obj == target
        return False
    
    # Check order_status_text_cancelled_by_buyer
    if tree_contains(raw_data, "order_status_text_cancelled_by_buyer"):
        return True
    
    # Check cancel reason
    cancel_by = find_first_key(raw_data, "cancel_by") or \
                find_first_key(raw_data, "canceled_by") or ""
    cancel_reason = find_first_key(raw_data, "cancel_reason") or \
                    find_first_key(raw_data, "buyer_cancel_reason") or ""
    
    cancel_str = str(cancel_by).lower() + " " + str(cancel_reason).lower()
    
    if any(k in cancel_str for k in ["buyer", "user", "customer", "người mua"]):
        if any(k in cancel_str for k in ["cancel", "hủy"]):
            return True
    
    return False

# ========== MAIN ENDPOINT ==========
@app.route("/api/check-cookie-v2", methods=["POST","GET"])
@app.route("/check-cookie-v2", methods=["POST","GET"])
def check_cookie_v2():
    """
    API v2 - TRẠM TRUNG CHUYỂN
    1) Check kích hoạt Sheet ID
    2) Gọi Shopee API
    3) Trả RAW DATA về cho GGScript tự parse (parseOrderResult)
    """
    # Debug nhanh: mở URL trên trình duyệt sẽ thấy JSON này
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "message": "API alive. Use POST with {cookie, sheet_id}.",
            "endpoint": "/api/check-cookie-v2"
        }), 200

    payload = request.get_json(silent=True) or {}

    cookie = (payload.get("cookie") or "").strip()
    sheet_id = (payload.get("sheet_id") or "").strip()

    if not cookie:
        return jsonify({"error": 1, "msg": "Thiếu cookie"}), 400

    if not sheet_id:
        return jsonify({"error": 1, "msg": "Thiếu sheet_id"}), 400

    # ===== VERIFY SHEET ID =====
    verify_result = verify_sheet_id(sheet_id)
    if not verify_result.get("valid"):
        return jsonify({"error": 1, "msg": verify_result.get("msg", "Sheet chưa được kích hoạt.")}), 403

    # ===== CHECK CACHE =====
    cache_key = f"v2:{sheet_id}:{cookie[:50]}"
    cached_data = get_cache(cache_key)

    if cached_data is not None:
        resp = {"error": 0, "data": cached_data, "cached": True}
        if isinstance(cached_data, dict) and isinstance(cached_data.get("orders"), list) and len(cached_data["orders"]) == 0:
            resp["msg"] = "Cookie hợp lệ nhưng chưa có đơn hàng"
            resp["login"] = True
        return jsonify(resp), 200

    # ===== FETCH SHOPEE =====
    fetched = fetch_orders_and_details(cookie, limit=50)

    if fetched.get("temp_error"):
        code = int(fetched.get("status_code") or 503)
        return jsonify({
            "ok": False,
            "success": False,
            "message": fetched.get("msg") or "Shopee temp error"
        }), code

    if fetched.get("auth_fail"):
        return jsonify({
            "ok": False,
            "success": False,
            "message": fetched.get("msg") or "Auth fail"
        }), 401

    details = fetched.get("details") or []

    if not details:
        placeholder = {"orders": []}
        set_cache(cache_key, placeholder, 600)  # 10 phút

        return jsonify({
            "error": 0,
            "data": placeholder,
            "msg": "Cookie hợp lệ nhưng chưa có đơn hàng",
            "login": True,
            "cached": False
        }), 200

    raw_data = (details[0] or {}).get("raw") or {}

    set_cache(cache_key, raw_data, CACHE_TTL)

    return jsonify({
        "error": 0,
        "data": raw_data,
        "cached": False
    }), 200

# ========== ROOT ==========
@app.route("/")
def index():
    return jsonify({
        "name": "API NgânMiu FINAL",
        "version": "2.0.0",
        "endpoints": {
            "check_cookie_v2": "POST /api/check-cookie-v2 (with activation)"
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
