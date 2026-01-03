# 🚀 HƯỚNG DẪN DEPLOY API NGANMIU

## ⏱️ THỜI GIAN: 15 PHÚT

---

## BƯỚC 1: CHUẨN BỊ (5 phút)

### 1.1 Tạo Sheet KeyCheckMVD

1. Vào https://sheets.google.com
2. Tạo Sheet mới: `NgânMiu - KeyCheckMVD`
3. Tab: `KeyCheckMVD`
4. Header (hàng 1):

   | A: sheet_id | B: status | C: expire_at | D: note |
   |-------------|-----------|--------------|---------|

5. Thêm 1 dòng mẫu để test:

   | sheet_id | status | expire_at | note |
   |----------|--------|-----------|------|
   | 1TEST_SHEET_ID | active | 2026-12-31 | Test |

6. Lấy Sheet ID:
   - File → Share → Copy link
   - URL: `https://docs.google.com/spreadsheets/d/1ABC...XYZ/edit`
   - Sheet ID = phần giữa `/d/` và `/edit`

### 1.2 Service Account

1. Mở file credentials JSON
2. Tìm `client_email`: `xxx@yyy.iam.gserviceaccount.com`
3. Share Sheet `KeyCheckMVD` cho email này (quyền Editor)

---

## BƯỚC 2: SETUP LOCAL (3 phút)

### 2.1 Clone/Download code

```bash
cd api-nganmiu
```

### 2.2 Tạo file `.env`

```bash
cp .env.example .env
nano .env
```

Sửa:

```env
KEYCHECK_SHEET_ID=1qP8xY2zR3aB4cD5eF6gH7iJ8kL9mN0oP
GOOGLE_SHEETS_CREDS_JSON={"type":"service_account",...}
ADMIN_API_KEY=nganmiu-admin-2026-xyz
```

### 2.3 Cài packages

```bash
pip install -r requirements.txt
```

### 2.4 Test local

```bash
python app.py
```

Mở browser: `http://localhost:5000`

Phải thấy:

```json
{
  "name": "API NgânMiu",
  "version": "2.0.0",
  ...
}
```

---

## BƯỚC 3: TEST API (3 phút)

### 3.1 Test check-cookie-v2

```bash
curl -X POST http://localhost:5000/api/check-cookie-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "cookie": "SPC_ST=...",
    "sheet_id": "1TEST_SHEET_ID"
  }'
```

**Mong đợi:** `"error": 0` (vì Sheet ID có trong KeyCheckMVD)

### 3.2 Test với Sheet ID không hợp lệ

```bash
curl -X POST http://localhost:5000/api/check-cookie-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "cookie": "SPC_ST=...",
    "sheet_id": "1INVALID_ID"
  }'
```

**Mong đợi:** `"error": 1` + msg "chưa được kích hoạt"

### 3.3 Test SPX tracking

```bash
curl "http://localhost:5000/api/spx-track?mvd=SPXVN066194857771"
```

**Mong đợi:** Có timeline

---

## BƯỚC 4: PUSH LÊN GITHUB (2 phút)

### 4.1 Init Git

```bash
git init
git add .
git commit -m "Initial commit - API NgânMiu v2"
```

### 4.2 Tạo repo GitHub

1. Vào https://github.com/new
2. Tên repo: `api-nganmiu`
3. Private
4. Create

### 4.3 Push

```bash
git remote add origin https://github.com/yourusername/api-nganmiu.git
git branch -M main
git push -u origin main
```

---

## BƯỚC 5: DEPLOY VERCEL (2 phút)

### 5.1 Import vào Vercel

1. Vào https://vercel.com/new
2. Import repo `api-nganmiu`
3. Framework Preset: **Other**
4. Click **Deploy**

### 5.2 Thêm Environment Variables

Settings → Environment Variables → Add:

**Name:** `KEYCHECK_SHEET_ID`  
**Value:** `1qP8xY2zR3aB4cD5eF6gH7iJ8kL9mN0oP`

**Name:** `GOOGLE_SHEETS_CREDS_JSON`  
**Value:** `{"type":"service_account",...}` (paste toàn bộ JSON)

**Name:** `ADMIN_API_KEY`  
**Value:** `nganmiu-admin-2026-xyz`

**Name:** `CONTACT_PHONE`  
**Value:** `0819.555.000`

**Name:** `APP_SECRET_KEY`  
**Value:** `nganmiu-api-secret-2026`

### 5.3 Redeploy

Deployments → Click ... → Redeploy

---

## BƯỚC 6: TEST PRODUCTION (2 phút)

### 6.1 Lấy URL

Vercel sẽ cho URL: `https://api-nganmiu.vercel.app`

### 6.2 Test

```bash
# Test home
curl https://api-nganmiu.vercel.app/

# Test check-cookie-v2
curl -X POST https://api-nganmiu.vercel.app/api/check-cookie-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "cookie": "SPC_ST=...",
    "sheet_id": "1TEST_SHEET_ID"
  }'
```

---

## ✅ XONG!

**API đã live tại:** `https://api-nganmiu.vercel.app`

### Endpoints:

- `POST /api/check-cookie` - Legacy
- `POST /api/check-cookie-v2` - Verify Sheet ID ⭐
- `GET /api/spx-track?mvd=...` - SPX Tracking
- `POST /api/admin/add-sheet` - Admin

---

## 🎯 SỬ DỤNG TRONG APPS SCRIPT

Sửa file `apps_script_v2.gs`:

```javascript
const API_V2_URL = "https://api-nganmiu.vercel.app/api/check-cookie-v2";
```

---

## 🔄 UPDATE SAU NÀY

### Thêm endpoint mới

1. Sửa `app.py`
2. Push lên GitHub:
   ```bash
   git add .
   git commit -m "Add new endpoint"
   git push
   ```
3. Vercel tự động deploy

### Thêm khách mới

1. Mở Sheet `KeyCheckMVD`
2. Thêm hàng:
   ```
   1NEW_ID | active | 2026-12-31 | Khách X
   ```
3. Xong (không cần deploy)

---

## 📞 HỖ TRỢ

**Call/Zalo:** 0819.555.000

---

## 🎉 CHECKLIST HOÀN TẤT

- [x] Sheet KeyCheckMVD
- [x] Service Account share
- [x] Test local
- [x] Push GitHub
- [x] Deploy Vercel
- [x] Thêm env variables
- [x] Test production
- [x] API live
