"""
API NgânMiu - CHỈ ENDPOINT (không web)
Logic từ API 1867 dòng + Hệ thống kích hoạt
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import time

app = Flask(__name__)
CORS(app)

# ========== CONFIG ==========
BASE = "https://shopee.vn/api/v4"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Cache in-memory
CACHE = {}
CACHE_TTL = 7200  # 2 giờ

# ========== CACHE ==========
def get_cache(key):
    if key in CACHE:
        data, expire = CACHE[key]
        if time.time() < expire:
            return data
        del CACHE[key]
    return None

def set_cache(key, value, ttl):
    CACHE[key] = (value, time.time() + ttl)

# ========== GOOGLE SHEETS - VERIFY ==========
def verify_sheet_id(sheet_id: str) -> dict:
    """Check sheet_id trong tab 'Kích hoạt GGS'"""
    try:
        creds_json = os.getenv("GOOGLE_SHEETS_CREDS_JSON")
        if not creds_json:
            return {"valid": True, "msg": "OK (dev)"}
        
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        creds_dict = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        service = build('sheets', 'v4', credentials=credentials)
        range_name = "Kích hoạt GGS!A2:E1000"
        
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
                        "msg": f"🔒 Sheet: {status}\n📞 Liên hệ: " + os.getenv("CONTACT_PHONE", "0819.555.000")
                    }
        
        return {
            "valid": False,
            "msg": "🔒 Sheet chưa được kích hoạt.\n📞 Liên hệ: " + os.getenv("CONTACT_PHONE", "0819.555.000")
        }
        
    except Exception as e:
        print(f"⚠️ verify error: {e}")
        return {"valid": True, "msg": "OK (fallback)"}

# ========== HELPER - FIND KEY ==========
def find_first_key(obj, key):
    """BFS tìm key đầu tiên trong nested dict"""
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

# ========== SHOPEE API ==========
def fetch_orders_and_details(cookie: str, limit: int = 50, offset: int = 0):
    """
    Lấy danh sách đơn từ Shopee (NGƯỜI MUA)
    Logic từ API 1867 dòng
    """
    url = f"{BASE}/order/get_all_order_and_checkout_list"
    headers = {
        "cookie": cookie,
        "user-agent": UA,
        "referer": "https://shopee.vn/"
    }
    params = {"limit": limit, "offset": offset}
    
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
        
        # Loại trùng
        seen = set()
        unique_ids = []
        for oid in order_ids:
            if oid not in seen:
                seen.add(oid)
                unique_ids.append(oid)
        
        if not unique_ids:
            return {"details": []}
        
        # Lấy chi tiết từng đơn
        details = []
        for oid in unique_ids[:limit]:
            detail_data = fetch_order_detail(cookie, oid)
            if detail_data:
                details.append({"order_id": oid, "raw": detail_data})
        
        return {"details": details}
        
    except Exception as e:
        print(f"fetch_orders error: {e}")
        return {"details": []}

def fetch_order_detail(cookie: str, order_id: str):
    """Lấy chi tiết 1 đơn"""
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

def is_buyer_cancelled(raw_data):
    """Check đơn bị buyer cancel"""
    if not raw_data:
        return False
    
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
    
    if tree_contains(raw_data, "order_status_text_cancelled_by_buyer"):
        return True
    
    cancel_by = find_first_key(raw_data, "cancel_by") or \
                find_first_key(raw_data, "canceled_by") or ""
    cancel_reason = find_first_key(raw_data, "cancel_reason") or \
                    find_first_key(raw_data, "buyer_cancel_reason") or ""
    
    cancel_str = str(cancel_by).lower() + " " + str(cancel_reason).lower()
    
    if any(k in cancel_str for k in ["buyer", "user", "customer", "người mua"]):
        if any(k in cancel_str for k in ["cancel", "hủy"]):
            return True
    
    return False

def pick_columns_from_detail(raw_data):
    """Parse summary từ raw data"""
    if not raw_data or not isinstance(raw_data, dict):
        return {}
    
    tracking_no = find_first_key(raw_data, "tracking_number") or \
                  find_first_key(raw_data, "tracking_no") or ""
    
    status_obj = find_first_key(raw_data, "list_view_text")
    status_text = ""
    if isinstance(status_obj, dict):
        status_text = status_obj.get("text", "")
    if not status_text:
        status_text = find_first_key(raw_data, "status_label") or ""
    
    return {
        "tracking_no": tracking_no,
        "status_text": status_text
    }

# ========== ENDPOINT ==========
@app.route("/api/check-cookie-v2", methods=["POST"])
def check_cookie_v2():
    """
    API v2 - Check cookie + kích hoạt
    Trả RAW DATA từ Shopee
    """
    try:
        payload = request.get_json(silent=True) or {}
        cookie = (payload.get("cookie") or "").strip()
        sheet_id = (payload.get("sheet_id") or "").strip()
        
        if not cookie:
            return jsonify({"error": 1, "msg": "Thiếu cookie"}), 400
        
        if not sheet_id:
            return jsonify({"error": 1, "msg": "Thiếu sheet_id"}), 400
        
        # ===== VERIFY =====
        verify_result = verify_sheet_id(sheet_id)
        
        if not verify_result["valid"]:
            return jsonify({
                "error": 1,
                "msg": verify_result["msg"]
            }), 403
        
        # ===== CACHE =====
        cache_key = f"v2:{sheet_id}:{cookie[:50]}"
        cached = get_cache(cache_key)
        
        if cached is not None:
            return jsonify({
                "error": 0,
                "data": cached,
                "cached": True
            })
        
        # ===== FETCH =====
        fetched = fetch_orders_and_details(cookie, limit=50, offset=0)
        details = fetched.get("details", []) if isinstance(fetched, dict) else []
        
        chosen_raw = None
        
        # Chọn đơn đầu tiên hợp lệ (không buyer-cancelled, có MVD hoặc status)
        for det in details:
            raw = det.get("raw") or {}
            if is_buyer_cancelled(raw):
                continue
            s = pick_columns_from_detail(raw)
            has_any = bool(s.get("tracking_no") or s.get("status_text"))
            if has_any:
                chosen_raw = raw
                break
        
        # Không có đơn
        if not chosen_raw:
            result = {
                "error": 0,
                "data": None,
                "msg": "Cookie hợp lệ nhưng chưa có đơn hàng",
                "cached": False
            }
            set_cache(cache_key, None, 3600)
            return jsonify(result)
        
        # ===== TRẢ RAW DATA =====
        set_cache(cache_key, chosen_raw, CACHE_TTL)
        
        return jsonify({
            "error": 0,
            "data": chosen_raw,
            "cached": False
        })
        
    except Exception as e:
        return jsonify({"error": 1, "msg": str(e)}), 500

@app.route("/")
def index():
    return jsonify({
        "name": "API NgânMiu - ENDPOINT ONLY",
        "version": "2.0.0",
        "endpoints": {
            "check_cookie_v2": "POST /api/check-cookie-v2"
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
