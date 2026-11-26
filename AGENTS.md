# Quy chuẩn Dự án `AI_video_tiktok` (`AGENTS.md`)

Tài liệu này định nghĩa các nguyên tắc vận hành cốt lõi ở cấp workspace cho dự án **`AI_video_tiktok`** — hệ thống tự học từ dữ liệu kênh TikTok thực tế và sản xuất nội dung/video TikTok xu hướng.

## 1. Kiến trúc Tri thức & Customizations của Dự án
- **Quy chuẩn nội dung bắt buộc (Workspace Rule):** [.agents/rules/tiktok-content-rules.md](.agents/rules/tiktok-content-rules.md) — Bộ quy tắc `[R-01]` đến `[R-10]` được kiểm chứng từ dữ liệu thực tế (hiện đã tích hợp `@tam_thefox`, v1.0).
- **Kỹ năng sản xuất video xu hướng (Workspace Skill):** [.agents/skills/tiktok-trend-video-creator/SKILL.md](.agents/skills/tiktok-trend-video-creator/SKILL.md) — Quy trình 6 bước lập ý tưởng, viết Hook 0–3s, dựng kịch bản, tối ưu visual/audio và chấm điểm Rubric 100 điểm trước khi đăng, kèm kho mẫu [`hook-bank.md`](.agents/skills/tiktok-trend-video-creator/references/hook-bank.md) và [`script-templates.md`](.agents/skills/tiktok-trend-video-creator/references/script-templates.md).
- **Quy trình tự học kênh mới (Training Protocol):** [training_data/TRAINING_PROTOCOL.md](training_data/TRAINING_PROTOCOL.md) — Quy trình 5 bước thu thập & mổ xẻ 10 trục cho mỗi profile TikTok mới; kho dữ liệu kênh lưu tại `training_data/channels/<handle>/`.

## 2. Nguyên tắc Bắt buộc khi Làm việc trong Workspace
1. **Khi người dùng yêu cầu lên ý tưởng, viết kịch bản, tối ưu hook, dựng storyboard hoặc chấm điểm video TikTok:**
   - Bắt buộc tuân thủ toàn bộ quy tắc trong `.agents/rules/tiktok-content-rules.md`.
   - Kích hoạt và thực hiện theo quy trình của skill `tiktok-trend-video-creator` (`.agents/skills/tiktok-trend-video-creator/SKILL.md`), chỉ đọc thêm `references/hook-bank.md` và `references/script-templates.md` khi cần mẫu chi tiết (Progressive Disclosure).
2. **Khi người dùng cung cấp link profile/video TikTok mới để training (`Bot_training_tiktok_content`):**
   - Thực hiện đúng 5 bước trong `training_data/TRAINING_PROTOCOL.md` bằng `browser` subagent (`Model: "flash"`).
   - **Trung thực dữ liệu 100%:** Chỉ ghi nhận số liệu, hình ảnh, phụ đề và bình luận quan sát trực tiếp; không suy diễn bịa đặt; ghi rõ `null` / `"không quan sát được"` nếu thiếu.
   - **Tuyệt đối không vượt CAPTCHA / chống bot:** Nếu gặp CAPTCHA hoặc chặn đăng nhập, dừng ngay và báo người dùng thao tác trực tiếp trên trình duyệt rồi tiếp tục trên cùng tab đó.
3. **Nguyên tắc Tích lũy Không Phá hủy (Additive & Non-Destructive):**
   - Mọi cập nhật vào `.agents/rules/tiktok-content-rules.md`, `AGENTS.md` hoặc `.agents/skills/tiktok-trend-video-creator/` khi học thêm kênh mới **chỉ được nối thêm (append)** quy luật mới, bằng chứng `@handle` mới và mẫu mới; **tuyệt đối không xóa hoặc ghi đè** các quy tắc và kiến thức cũ đã kiểm chứng.
   - Không chỉnh sửa hay xóa các rule toàn cục bên ngoài workspace `d:\Project\AI_video_tiktok`.

## 3. Lịch sử Kênh đã Training
| Phiên bản | Ngày | Kênh nguồn | Quy mô dữ liệu | Tài liệu chi tiết |
|---|---|---|---|---|
| `v1.0` | `2026-11-26` | `@tam_thefox` (*Tâm Thefox*) | 248 video lưới (`median = 58K`) · Đợt 1: 19 video mổ xẻ 10 trục | `training_data/channels/tam_thefox/` |
