# Hybrid Auto-Publisher: 1 Kênh YouTube + 2 Kênh TikTok

Công cụ đăng & hẹn giờ video tự động theo kiến trúc **Hybrid tiết kiệm tối đa (\$0/tháng ở quy mô 1 YouTube + 2 TikTok)**:
* **1 Kênh YouTube (`yt_main`)**: Gọi thẳng **YouTube Data API v3 chính thức** (miễn phí, 100 video/ngày mặc định, hỗ trợ hẹn giờ native `publishAt`, Shorts, custom thumbnail và cờ `containsSyntheticMedia`).
* **2 Kênh TikTok (`tiktok_1`, `tiktok_2`)**: Đi qua **Zernio API** (miễn phí \$0/tháng cho 2 tài khoản đầu tiên, đã pass TikTok Direct Post Audit), hoặc chuyển sang **Upload-Post** chỉ bằng cách đổi `"provider": "upload_post"` trong `config/channels.json` mà không cần sửa code.

---

## 1. Kiến trúc & tính năng có sẵn

* **Tối ưu upload cho 2 kênh TikTok**: Khi đăng cùng 1 file video lên cả `tiktok_1` và `tiktok_2` qua Zernio, hệ thống chỉ upload presign **1 lần duy nhất** lên storage Zernio rồi dùng chung URL cho cả 2 kênh.
* **Chống đăng trùng (Idempotency)**: Lưu hash `SHA-256` của video + mã kênh + giờ hẹn vào SQLite (`data/publisher.db`). Chạy lại lệnh cũ sẽ tự động `SKIPPED` nếu đã đăng thành công.
* **Smart Retry**: Tự động thử lại tối đa 3 lần (Exponential Backoff) khi gặp lỗi mạng, `429` hoặc `5xx`; dừng ngay với lỗi `4xx` để tránh đốt quota/spam API.
* **Chuẩn hóa video FFmpeg (`--normalize`)**: Xuất bản Clean Master `1080x1920`, `H.264 (yuv420p)`, `30fps`, `AAC 48kHz`, chuẩn âm lượng `-14 LUFS`, `+faststart`.
* **Đăng lệch giờ giữa 2 kênh TikTok**: Hỗ trợ `--tiktok2-delay-min 90` hoặc file manifest JSON tùy biến riêng tiêu đề, caption, hashtag và lịch đăng cho từng kênh.

---

## 2. Hướng dẫn thiết lập từng bước (Setup ~10 phút)

### Bước 1: Cài môi trường Python
```powershell
cd d:\Project\AI_video_tiktok\publisher
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Bước 2: Tạo file cấu hình từ mẫu
```powershell
Copy-Item .env.example .env
Copy-Item config\channels.example.json config\channels.json
New-Item -ItemType Directory -Force -Path .secrets
```

### Bước 3: Thiết lập kênh YouTube (`yt_main`) — Miễn phí \$0
1. Truy cập [Google Cloud Console](https://console.cloud.google.com/) → Tạo Project mới (ví dụ `ai-video-publisher`).
2. Vào **APIs & Services → Library** → Tìm và bật **YouTube Data API v3**.
3. Vào **APIs & Services → OAuth consent screen**:
   * Chọn **External** → Điền tên app & email của bạn.
   * **CỰC KỲ QUAN TRỌNG (né bẫy token hết hạn sau 7 ngày)**: Sau khi tạo xong, bấm **Publish App** để chuyển trạng thái sang **In Production**. *(Vì dùng nội bộ cho kênh của chính bạn, bạn không cần nộp Google Verification — khi tự đăng nhập chỉ cần bấm `Advanced → Go to <app>`.)*
4. Vào **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   * Application type: **Desktop app**.
   * Tải file JSON về và lưu thành: `d:\Project\AI_video_tiktok\publisher\.secrets\youtube_client_secret.json`.
5. Chạy lệnh xác thực 1 lần duy nhất:
   ```powershell
   python -m src.cli auth-youtube
   ```
   Trình duyệt sẽ mở ra → chọn đúng tài khoản/kênh YouTube của bạn → cấp quyền → token dài hạn tự lưu tại `.secrets/youtube_token.json`.

### Bước 4: Thiết lập 2 kênh TikTok (`tiktok_1`, `tiktok_2`)

#### Phương án A (Khuyên dùng — \$0/tháng cho 2 kênh): Zernio
1. Đăng ký tài khoản tại [zernio.com](https://zernio.com) (gói Free hỗ trợ 2 connected accounts, unlimited posts).
2. Trên Dashboard Zernio → bấm **Connect Account** → kết nối OAuth cho **2 kênh TikTok** của bạn.
3. Vào mục **API Keys** → tạo API Key → dán vào `ZERNIO_API_KEY=...` trong file `.env`.
4. Chạy lệnh sau để lấy chính xác `accountId` của 2 kênh:
   ```powershell
   python -m src.cli check-zernio
   ```
5. Copy 2 mã `Account ID` vừa hiện ra dán vào trường `"account_id"` của `tiktok_1` và `tiktok_2` trong `config/channels.json`.

#### Phương án B (Dự phòng / Scale 5+ cặp kênh): Upload-Post
1. Đăng ký [upload-post.com](https://upload-post.com) (lưu ý gói Free không mở TikTok, cần gói Basic trở lên).
2. Tạo 2 user profiles và kết nối 2 kênh TikTok, lấy API Key điền vào `UPLOAD_POST_API_KEY=...` trong `.env`.
3. Trong `config/channels.json`, đổi `"provider": "upload_post"` và điền `"upload_post_user"` tương ứng.

---

## 3. Các lệnh sử dụng hằng ngày

### Kiểm tra danh sách kênh & thông số video
```powershell
python -m src.cli channels
python -m src.cli probe videos\demo.mp4
```

### Chạy thử mô phỏng (Dry-Run — KHÔNG gọi API thật)
```powershell
python -m src.cli publish videos\demo.mp4 `
  --title "3 Mẹo AI dựng video cực nhanh #shorts" `
  --caption "3 mẹo AI giúp tiết kiệm 80% thời gian dựng video!" `
  --hashtags "ai,videomarketing,fyp" `
  --schedule "2026-12-01 19:00" `
  --tiktok2-delay-min 90 `
  --ai `
  --dry-run
```

### Đăng thật lên cả 1 YouTube + 2 TikTok (kèm tự động chuẩn hóa FFmpeg)
```powershell
python -m src.cli publish videos\demo.mp4 `
  --title "3 Mẹo AI dựng video cực nhanh #shorts" `
  --description "Mô tả chuẩn SEO cho YouTube Shorts..." `
  --caption "Caption tối ưu riêng cho TikTok" `
  --hashtags "ai,xaykenhtiktok,shorts" `
  --schedule "2026-12-01 19:00" `
  --tiktok2-delay-min 90 `
  --ai `
  --normalize
```

### Đăng bài với nội dung/giờ khác nhau hoàn toàn cho từng kênh (Manifest JSON)
```powershell
python -m src.cli publish-manifest config\manifest.example.json --dry-run
python -m src.cli publish-manifest config\manifest.example.json
```

### Xem lịch sử đăng bài
```powershell
python -m src.cli history
```
