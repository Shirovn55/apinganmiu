# 🚀 API NgânMiu

API tổng hợp cho các công cụ Shopee - Độc lập, chuyên nghiệp.

**Contact:** 0819.555.000

---

## 📋 TÍNH NĂNG

✅ **Check Cookie Shopee**
- Legacy API (không verify)
- API v2 (verify Sheet ID + cache 24h)
- Trả nhiều đơn (fix bug mất MVĐ)

✅ **SPX Tracking**
- Tracking đơn giản qua MVĐ
- Cache 1 giờ

✅ **Admin Tools**
- Thêm Sheet ID tự động
- Quản lý kích hoạt

✅ **Bảo mật**
- Verify Sheet ID qua Google Sheets
- Quản lý tập trung
- Cache thông minh

---

## 🌐 ENDPOINTS

### 1. GET `/`
**Mô tả:** API info

**Response:**
```json
{
  "name": "API NgânMiu",
  "version": "2.0.0",
  "contact": "0819.555.000",
  "endpoints": {...}
}
```

---

### 2. POST `/api/check-cookie`
**Mô tả:** Check cookie (legacy, không verify Sheet ID)

**Request:**
```json
{
  "cookie": "SPC_ST=..."
}
```

**Response:**
```json
{
  "data": {
    "tracking_no": "SPXVN...",
    "status": "Giao hàng thành công",
    "shipping_name": "...",
    "shipping_phone": "...",
    "shipping_address": "...",
    "product_name": "...",
    "cod": 80000,
    "shipper_name": "",
    "shipper_phone": "",
    "username": ""
  }
}
```

---

### 3. POST `/api/check-cookie-v2` ⭐
**Mô tả:** Check cookie với verify Sheet ID + cache 24h

**Request:**
```json
{
  "cookie": "SPC_ST=...",
  "sheet_id": "1ABC...XYZ"
}
```

**Response (thành công):**
```json
{
  "error": 0,
  "orders": [
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
  ],
  "total": 2,
  "cached": false,
  "expire_at": "2026-12-31"
}
```

**Response (Sheet chưa kích hoạt):**
```json
{
  "error": 1,
  "msg": "🔒 Sheet chưa được kích hoạt.\n📞 Liên hệ: 0819.555.000"
}
```

---

### 4. GET `/api/spx-track`
**Mô tả:** Tracking SPX

**Query:**
```
?mvd=SPXVN066194857771&language_code=vi
```

**Response:**
```json
{
  "error": 0,
  "timeline": [
    "2024-12-15 10:30 — Giao hàng thành công",
    "2024-12-14 08:00 — Đang giao hàng"
  ],
  "status": "Giao hàng thành công"
}
```

---

### 5. POST `/api/admin/add-sheet` 🔒
**Mô tả:** Admin thêm Sheet ID vào KeyCheckMVD

**Request:**
```json
{
  "admin_key": "SECRET_KEY",
  "sheet_id": "1ABC...XYZ",
  "expire_at": "2026-12-31",
  "note": "Khách VIP"
}
```

**Response:**
```json
{
  "error": 0,
  "msg": "Đã thêm Sheet ID thành công"
}
```

---

## 🛠️ SETUP

### 1. Clone repo

```bash
git clone https://github.com/yourusername/api-nganmiu.git
cd api-nganmiu
```

### 2. Cài packages

```bash
pip install -r requirements.txt
```

### 3. Tạo file `.env`

Copy từ `.env.example`:

```bash
cp .env.example .env
```

Sửa các giá trị:
- `KEYCHECK_SHEET_ID` - Sheet ID của KeyCheckMVD
- `GOOGLE_SHEETS_CREDS_JSON` - Service Account JSON
- `ADMIN_API_KEY` - Key bí mật cho admin

### 4. Chạy local

```bash
python app.py
```

API chạy tại: `http://localhost:5000`

### 5. Test

```bash
# Test home
curl http://localhost:5000/

# Test check cookie v2
curl -X POST http://localhost:5000/api/check-cookie-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "cookie": "SPC_ST=...",
    "sheet_id": "1ABC...XYZ"
  }'

# Test SPX tracking
curl "http://localhost:5000/api/spx-track?mvd=SPXVN066194857771"
```

---

## 🚀 DEPLOY

### Deploy lên Vercel

1. Push code lên GitHub

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

2. Import vào Vercel

- Vào https://vercel.com/new
- Import repo GitHub
- Framework: **Other**
- Deploy

3. Thêm Environment Variables

Vào Settings → Environment Variables, thêm:

- `APP_SECRET_KEY`
- `CONTACT_PHONE`
- `KEYCHECK_SHEET_ID`
- `GOOGLE_SHEETS_CREDS_JSON`
- `ADMIN_API_KEY`

4. Redeploy

---

## 📊 CẤU TRÚC SHEET KEYCHECKMVD

| sheet_id | status | expire_at | note |
|----------|--------|-----------|------|
| 1ABC...XYZ | active | 2026-12-31 | Khách VIP |
| 1DEF...GHI | active | 2026-06-30 | Trial |
| 1JKL...MNO | banned |  | Vi phạm |

**Cột:**
- `sheet_id` - ID của Google Sheet khách hàng
- `status` - `active` hoặc `banned`
- `expire_at` - Ngày hết hạn (format: `YYYY-MM-DD`)
- `note` - Ghi chú

---

## 🔐 BẢO MẬT

✅ Verify Sheet ID qua Google Sheets  
✅ Cache 24h giảm request  
✅ Admin API có authentication  
✅ Fail-open khi lỗi verify (không block user)  
✅ Error handling toàn diện  

---

## 📞 LIÊN HỆ

**Zalo/Call:** 0819.555.000

**Email:** nganmiu.store@gmail.com

---

## 📝 LICENSE

© 2026 NgânMiu.Store - All rights reserved.
