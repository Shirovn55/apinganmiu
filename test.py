"""
Test script cho API NgânMiu
Chạy: python test.py
"""

import requests
import json

# ========== CONFIG ==========
API_URL = "http://localhost:5000"  # Local
# API_URL = "https://api-nganmiu.vercel.app"  # Production

# Cookie mẫu (thay bằng cookie thật)
COOKIE_ST = "SPC_ST=your_cookie_here"

# Sheet ID test (phải có trong KeyCheckMVD)
SHEET_ID_VALID = "1TEST_SHEET_ID"
SHEET_ID_INVALID = "1INVALID_NOT_IN_DB"

# Admin key (từ .env)
ADMIN_KEY = "nganmiu-admin-2026-xyz"

# ========== HELPERS ==========

def print_result(title, response):
    """In kết quả test đẹp"""
    print(f"\n{'='*60}")
    print(f"🧪 TEST: {title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    
    try:
        data = response.json()
        print(f"\nResponse:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(f"\nResponse (text):")
        print(response.text)

# ========== TESTS ==========

def test_home():
    """Test GET /"""
    resp = requests.get(f"{API_URL}/")
    print_result("GET / - API Info", resp)
    assert resp.status_code == 200
    assert resp.json()["name"] == "API NgânMiu"

def test_check_cookie_legacy():
    """Test POST /api/check-cookie"""
    payload = {"cookie": COOKIE_ST}
    resp = requests.post(f"{API_URL}/api/check-cookie", json=payload)
    print_result("POST /api/check-cookie - Legacy", resp)

def test_check_cookie_v2_valid():
    """Test POST /api/check-cookie-v2 - Sheet ID hợp lệ"""
    payload = {
        "cookie": COOKIE_ST,
        "sheet_id": SHEET_ID_VALID
    }
    resp = requests.post(f"{API_URL}/api/check-cookie-v2", json=payload)
    print_result("POST /api/check-cookie-v2 - Valid Sheet ID", resp)

def test_check_cookie_v2_invalid():
    """Test POST /api/check-cookie-v2 - Sheet ID không hợp lệ"""
    payload = {
        "cookie": COOKIE_ST,
        "sheet_id": SHEET_ID_INVALID
    }
    resp = requests.post(f"{API_URL}/api/check-cookie-v2", json=payload)
    print_result("POST /api/check-cookie-v2 - Invalid Sheet ID", resp)
    assert resp.status_code == 403
    assert "chưa được kích hoạt" in resp.json()["msg"]

def test_spx_track():
    """Test GET /api/spx-track"""
    mvd = "SPXVN066194857771"
    resp = requests.get(f"{API_URL}/api/spx-track", params={"mvd": mvd})
    print_result(f"GET /api/spx-track?mvd={mvd}", resp)

def test_admin_add_sheet():
    """Test POST /api/admin/add-sheet"""
    payload = {
        "admin_key": ADMIN_KEY,
        "sheet_id": "1NEW_TEST_SHEET",
        "expire_at": "2026-12-31",
        "note": "Test tự động"
    }
    resp = requests.post(f"{API_URL}/api/admin/add-sheet", json=payload)
    print_result("POST /api/admin/add-sheet", resp)

def test_admin_add_sheet_unauthorized():
    """Test POST /api/admin/add-sheet - Unauthorized"""
    payload = {
        "admin_key": "WRONG_KEY",
        "sheet_id": "1ABC",
        "expire_at": "2026-12-31",
        "note": "Test"
    }
    resp = requests.post(f"{API_URL}/api/admin/add-sheet", json=payload)
    print_result("POST /api/admin/add-sheet - Unauthorized", resp)
    assert resp.status_code == 403

# ========== MAIN ==========

if __name__ == "__main__":
    print(f"\n🚀 Testing API NgânMiu")
    print(f"URL: {API_URL}")
    print(f"\n⚠️  Đảm bảo:")
    print(f"1. API đang chạy (python app.py)")
    print(f"2. Sheet KeyCheckMVD đã có dữ liệu")
    print(f"3. Cookie ST hợp lệ (sửa biến COOKIE_ST)")
    
    try:
        # Test cơ bản
        test_home()
        
        # Test check cookie
        # test_check_cookie_legacy()
        # test_check_cookie_v2_valid()
        test_check_cookie_v2_invalid()
        
        # Test SPX
        test_spx_track()
        
        # Test admin
        # test_admin_add_sheet()
        test_admin_add_sheet_unauthorized()
        
        print(f"\n{'='*60}")
        print(f"✅ TẤT CẢ TEST HOÀN TẤT")
        print(f"{'='*60}\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
