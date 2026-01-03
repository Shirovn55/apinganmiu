# 📦 API NGANMIU - BỘ CODE HOÀN CHỈNH

## 🎯 TỔNG QUAN

**Project:** API NgânMiu - API tổng hợp cho Shopee Tools  
**Version:** 2.0.0  
**Contact:** 0819.555.000

---

## 📂 CẤU TRÚC THỨ MỤC

```
api-nganmiu/
├── app.py                 # Main API file (Flask)
├── requirements.txt       # Python packages
├── vercel.json           # Vercel config
├── .env.example          # File .env mẫu
├── .gitignore            # Git ignore
├── README.md             # Tài liệu API
├── DEPLOY.md             # Hướng dẫn deploy
└── test.py               # Test script
```

---

## 🚀 TÍNH NĂNG

### ✅ API Endpoints

1. **GET /** - API Info
2. **POST /api/check-cookie** - Check cookie legacy
3. **POST /api/check-cookie-v2** ⭐ - Check cookie + verify Sheet ID
4. **GET /api/spx-track** - SPX Tracking
5. **POST /api/admin/add-sheet** 🔒 - Admin thêm Sheet ID

### ✅ Bảo mật

- ✅ Verify Sheet ID qua Google Sheets
- ✅ Cache 24h giảm request
- ✅ Admin API có authentication
- ✅ Fail-open khi lỗi
- ✅ Error handling toàn diện

### ✅ Tối ưu

- ✅ Cache thông minh
- ✅ Fix bug mất MVĐ (trả nhiều đơn)
- ✅ Lightweight (chỉ 7 packages)
- ✅ Serverless-ready (Vercel)

---

## ⚡ QUICKSTART (3 BƯỚC)

### 1. Clone code

```bash
cd api-nganmiu
pip install -r requirements.txt
```

### 2. Tạo `.env`

```bash
cp .env.example .env
nano .env
```

Sửa:
- `KEYCHECK_SHEET_ID` - Sheet ID KeyCheckMVD
- `GOOGLE_SHEETS_CREDS_JSON` - Service Account JSON
- `ADMIN_API_KEY` - Key admin

### 3. Chạy

```bash
python app.py
```

API live tại: `http://localhost:5000`

---

## 📋 SHEET KEYCHECKMVD

### Cấu trúc

| A: sheet_id | B: status | C: expire_at | D: note |
|-------------|-----------|--------------|---------|
| 1ABC...XYZ | active | 2026-12-31 | Khách VIP |
| 1DEF...GHI | banned |  | Vi phạm |

### Quy tắc

- **status:**
  - `active` = Dùng được
  - `banned` = Bị khóa
  - Khác = Chưa kích hoạt

- **expire_at:**
  - Format: `YYYY-MM-DD`
  - Trống = Lifetime
  - Quá hạn = Tự động chặn

### Cách tạo

1. Tạo Google Sheet mới
2. Tab: `KeyCheckMVD`
3. Header: `sheet_id | status | expire_at | note`
4. Share cho Service Account (quyền Editor)
5. Lấy Sheet ID → Set vào `KEYCHECK_SHEET_ID`

---

## 🌐 DEPLOY LÊN VERCEL

### Bước 1: Push GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git push
```

### Bước 2: Import vào Vercel

- Vào https://vercel.com/new
- Import repo
- Framework: Other
- Deploy

### Bước 3: Thêm Environment Variables

Settings → Environment Variables:

- `KEYCHECK_SHEET_ID`
- `GOOGLE_SHEETS_CREDS_JSON`
- `ADMIN_API_KEY`
- `CONTACT_PHONE`
- `APP_SECRET_KEY`

### Bước 4: Redeploy

Deployments → Redeploy

---

## 🧪 TEST

### Local

```bash
python test.py
```

### Production

```bash
# Test home
curl https://api-nganmiu.vercel.app/

# Test check-cookie-v2
curl -X POST https://api-nganmiu.vercel.app/api/check-cookie-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "cookie": "SPC_ST=...",
    "sheet_id": "1ABC...XYZ"
  }'
```

---

## 📱 TÍCH HỢP VỚI APPS SCRIPT

### File: `apps_script_v2.gs`

```javascript
const API_V2_URL = "https://api-nganmiu.vercel.app/api/check-cookie-v2";

function fetchCookieV2(cookie) {
  const sheetId = SpreadsheetApp.getActiveSpreadsheet().getId();
  
  const res = UrlFetchApp.fetch(API_V2_URL, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      cookie: cookie,
      sheet_id: sheetId
    }),
    muteHttpExceptions: true
  });
  
  return JSON.parse(res.getContentText());
}
```

---

## 🔄 QUY TRÌNH SỬ DỤNG

### Thêm khách mới

1. Khách gửi Sheet ID
2. Mở Sheet `KeyCheckMVD`
3. Thêm hàng:
   ```
   1NEW_ID | active | 2026-12-31 | Khách X
   ```
4. Xong (không cần deploy)

### Gia hạn

Sửa cột `expire_at`:
```
2025-12-31 → 2027-12-31
```

### Khóa

Đổi cột `status`:
```
active → banned
```

---

## 📊 API RESPONSE EXAMPLES

### ✅ Thành công

```json
{
  "error": 0,
  "orders": [
    {
      "tracking_no": "SPXVN066194857771",
      "status": "Giao hàng thành công",
      "shipping_name": "Nguyễn Văn A",
      "shipping_phone": "0123456789",
      "shipping_address": "123 ABC, Q1, TP.HCM",
      "product_name": "Dầu đậu nành Simply 1 lít",
      "cod": 80000,
      "shipper_name": "",
      "shipper_phone": "",
      "username": "user123"
    }
  ],
  "total": 1,
  "cached": false,
  "expire_at": "2026-12-31"
}
```

### ❌ Sheet chưa kích hoạt

```json
{
  "error": 1,
  "msg": "🔒 Sheet chưa được kích hoạt.\n📞 Liên hệ: 0819.555.000"
}
```

### ⏰ Sheet hết hạn

```json
{
  "error": 1,
  "msg": "⏰ Gói đã hết hạn (2025-12-31).\n📞 Liên hệ: 0819.555.000 để gia hạn"
}
```

---

## 🛠️ TROUBLESHOOTING

### Lỗi: "KEYCHECK_SHEET_ID chưa được cấu hình"

**Nguyên nhân:** Chưa set biến môi trường

**Giải pháp:** Thêm `KEYCHECK_SHEET_ID` vào `.env` hoặc Vercel

### Lỗi: "Lỗi kết nối Google Sheets"

**Nguyên nhân:** Service Account chưa được share

**Giải pháp:** Share Sheet `KeyCheckMVD` cho email Service Account

### Lỗi: "Cookie không hợp lệ"

**Nguyên nhân:** Cookie sai hoặc hết hạn

**Giải pháp:** Lấy cookie mới từ Shopee

---

## 📞 LIÊN HỆ

**Call/Zalo:** 0819.555.000  
**Email:** nganmiu.store@gmail.com

---

## 📝 CHANGELOG

### v2.0.0 (2026-01-03)
- ✅ Tách riêng thành project độc lập
- ✅ Thêm verify Sheet ID
- ✅ Cache 24h
- ✅ Fix bug mất MVĐ (trả nhiều đơn)
- ✅ Admin API
- ✅ SPX Tracking
- ✅ Tài liệu đầy đủ

---

## 📄 LICENSE

© 2026 NgânMiu.Store - All rights reserved.

---

## 🎉 KẾT LUẬN

**API NgânMiu v2** là bộ API hoàn chỉnh, chuyên nghiệp cho Shopee Tools:

✅ Độc lập (không dùng chung với web nganmiu.store)  
✅ Bảo mật cao (verify Sheet ID)  
✅ Hiệu năng tốt (cache 24h)  
✅ Dễ mở rộng (thêm endpoint mới dễ dàng)  
✅ Tài liệu đầy đủ  

**Sẵn sàng deploy và sử dụng!** 🚀
