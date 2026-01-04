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
    Lấy list order_id từ Shopee (NGƯỜI MUA)
    Logic từ API 1867 dòng
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
            return {"details": []}
        
        # BFS tìm tất cả order_id
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
        
        return {"details": details}
        
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return {"details": []}

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
@app.route("/api/check-cookie-v2", methods=["POST"])
def check_cookie_v2():
    """
    API v2 - TRẠM TRUNG CHUYỂN
    1. Check kích hoạt Sheet ID
    2. Gọi Shopee API
    3. Trả RAW DATA về cho GGScript tự parse
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
    cache_key = f"v2:{sheet_id}:{cookie[:50]}"
    cached_data = get_cache(cache_key)
    
    if cached_data is not None:
        return jsonify({
            "error": 0,
            "data": cached_data,
            "cached": True
        })
    
    # ===== FETCH SHOPEE - LOGIC TỪ API 1867 DÒNG =====
    fetched = fetch_orders_and_details(cookie, limit=50)
    details = fetched.get("details", [])
    
    if not details:
        # Cookie live nhưng chưa có đơn
        result = {
            "error": 0,
            "data": None,
            "msg": "Cookie hợp lệ nhưng chưa có đơn hàng",
            "cached": False
        }
        set_cache(cache_key, None, 3600)
        return jsonify(result)
    
    # ===== TRẢ RAW DATA ĐƠN ĐẦU TIÊN =====
    # GGScript sẽ tự parse qua parseOrderResult()
    raw_data = details[0].get("raw", {})
    
    # Cache raw data
    set_cache(cache_key, raw_data, CACHE_TTL)
    
    return jsonify({
        "error": 0,
        "data": raw_data,  # ← RAW DATA từ Shopee
        "cached": False
    })

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
