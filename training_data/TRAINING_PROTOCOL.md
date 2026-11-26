# TikTok Content Training Protocol (`Bot_training_tiktok_content`)

Tài liệu này định nghĩa quy trình chuẩn để conversation `Bot_training_tiktok_content` tự động phân tích các kênh/video TikTok, trích xuất bài học thực chiến, và chuyển hóa thành **Workspace Rules** cùng **Workspace Skills** chuẩn Antigravity trong dự án `d:\Project\AI_video_tiktok`.

---

## 1. Nguyên tắc bắt buộc

1. **Dữ liệu thật 100% — Không suy diễn bịa đặt**:
   - Chỉ ghi nhận các chỉ số, nội dung hình ảnh, văn bản, âm thanh và bình luận thực sự quan sát được qua trình duyệt (`browser` subagent).
   - Nếu một video không phát được, thiếu âm thanh hoặc không hiện chỉ số nào, ghi rõ `null` / `"không quan sát được"` thay vì đoán.
2. **Tuân thủ cơ chế chống bot & CAPTCHA**:
   - Luôn truy cập TikTok qua `browser` subagent (dùng `Model: "flash"`), không dùng script cào trái phép.
   - **Tuyệt đối không cố giải hay vượt CAPTCHA / xác minh người thật**. Nếu TikTok hiển thị CAPTCHA hoặc chặn truy cập yêu cầu đăng nhập, phải **dừng lại và báo rõ cho người dùng** thao tác trực tiếp trên cửa sổ trình duyệt, sau đó tiếp tục phân tích trên cùng tab đó bằng `send_message`.
3. **Tích lũy không phá hủy (Additive & Non-Destructive)**:
   - Mỗi khi train thêm kênh hoặc video mới, **giữ nguyên toàn bộ kiến thức, Rule và Skill cũ**, chỉ nối thêm dữ liệu mới, bổ sung bằng chứng hoặc nâng cấp phiên bản kèm nguồn dẫn chiếu (`@handle`).
   - Không chỉnh sửa hay xóa các rule toàn cục bên ngoài workspace `d:\Project\AI_video_tiktok`.

---

## 2. Quy trình Training 5 bước cho mỗi Profile TikTok

### Bước 1 — Khảo sát tổng quan kênh (`profile_overview.md`)
Mở link profile bằng `browser` subagent và thu thập:
- Handle, tên hiển thị, bio, link gắn bio, số lượng Following / Followers / Total Likes.
- Chủ đề chính, phong cách nhân vật/kênh, đối tượng khán giả mục tiêu.
- Danh sách lưới video hiện có trên trang profile (URL video, caption/alt ngắn, lượt xem hiển thị trên lưới, đánh dấu video ghim).

### Bước 2 — Chuẩn hóa số liệu & Chọn thứ tự mổ xẻ
- Tính `median_views` (trung vị lượt xem) từ danh sách video quét được trên lưới.
- Với từng video, tính:
  - `outlier_score = views / median_views`
- Quy tắc phạm vi phân tích:
  - Nếu kênh có **≤ 25 video**: phân tích chi tiết **toàn bộ từng video**.
  - Nếu kênh có **> 25 video**: phân tích theo đợt — Đợt 1 gồm toàn bộ **video ghim** + **Top Outlier cao nhất** + **các video mới nhất** + **3–5 video view thấp nhất** để so sánh tương phản (tổng ~15–25 video/đợt), sau đó ghi rõ danh sách các video còn lại để có thể train tiếp ở lượt sau.

### Bước 3 — Mổ xẻ chi tiết từng video (10 trục phân tích)
Mở từng video và trích xuất đầy đủ các trục sau vào JSON & Markdown:
1. **Metadata & Metrics**: `video_id`, `url`, `posted_date` (nếu thấy), `caption`, `hashtags`, `is_pinned`, `views`, `likes`, `comments_count`, `bookmarks`, `shares`, `outlier_score`.
2. **Hook 0–3 giây đầu**:
   - `visual_hook`: cảnh mở đầu có hành động/biểu cảm/bối cảnh gì gây dừng lướt?
   - `text_hook`: dòng chữ xuất hiện đầu video (nội dung, màu sắc, vị trí).
   - `audio_hook`: câu nói/âm thanh mở đầu (nếu có subtitle/audio).
3. **Chủ đề & Góc tiếp cận (Angle)**: đánh vào cảm xúc nào (tò mò, đồng cảm, tranh cãi, hài hước, hữu ích, FOMO...)?
4. **Cấu trúc kịch bản**: chia mốc thời gian mở đầu → phát triển → cao trào/twist → kết thúc/CTA.
5. **Nhịp dựng & Hình ảnh (Visual & Pacing)**: phong cách hình ảnh (người thật, hoạt hình/AI, màn hình, storytelling...), tốc độ cắt cảnh, bố cục chữ so với vùng che UI TikTok.
6. **Âm thanh & Nhạc**: tên âm thanh/nhạc hiển thị trên video, vai trò của nhạc/SFX/voice.
7. **Phân tích Bình luận (Comment Insights)**: tóm tắt các nhóm phản ứng chính, câu hỏi lặp lại, yếu tố khiến người xem phải bình luận.
8. **Lý do Viral / Hiệu quả tốt** (với video `outlier_score >= 1.5` hoặc tương tác cao).
9. **Điểm yếu / Lý do kém hiệu quả** (đối chiếu ở các video `outlier_score < 0.7`).
10. **Bài học rút ra từ video này** (ngắn gọn, áp dụng được ngay).

### Bước 4 — Lưu dữ liệu chuẩn hóa theo từng kênh
Lưu toàn bộ kết quả tại `d:\Project\AI_video_tiktok\training_data\channels\<handle>\`:
- `profile_overview.md` — Tổng quan kênh & bảng xếp hạng video theo `outlier_score`.
- `videos_analysis.json` — Dữ liệu cấu trúc đầy đủ của từng video đã phân tích.
- `videos_analysis.md` — Bản đọc chi tiết từng video bằng tiếng Việt.
- `lessons_learned.md` — Tổng hợp quy luật thắng/thua, so sánh nhóm Top vs Bottom của kênh.

### Bước 5 — Chuyển hóa thành Workspace Rules & Workspace Skills
Tổng hợp kiến thức đã kiểm chứng thành tài sản tái sử dụng chuẩn Antigravity:

1. **Workspace Rules**:
   - `d:\Project\AI_video_tiktok\.agents\rules\tiktok-content-rules.md`: Bộ quy tắc bắt buộc khi xây dựng ý tưởng, viết kịch bản, chọn hook, nhịp dựng, caption/hashtag và kiểm duyệt video TikTok (mỗi rule kèm lý do & dẫn chứng video thực tế).
   - `d:\Project\AI_video_tiktok\AGENTS.md`: Rule cấp dự án ngắn gọn (< 24 KB), giữ nguyên mọi rule cũ đã có và tham chiếu tới `.agents/rules/tiktok-content-rules.md` cùng các skill của dự án.
2. **Workspace Skills**:
   - `d:\Project\AI_video_tiktok\.agents\skills\tiktok-trend-video-creator\SKILL.md`: Skill hoàn chỉnh (đúng chuẩn YAML frontmatter `name` + `description`) hướng dẫn quy trình từng bước tạo video xu hướng trên TikTok (từ chọn ý tưởng → viết Hook 3s → dựng cấu trúc kịch bản → tối ưu visual/audio/caption → chấm điểm theo rubric trước khi đăng).
   - `d:\Project\AI_video_tiktok\.agents\skills\tiktok-trend-video-creator\references\hook-bank.md`: Ngân hàng mẫu Hook thực chiến trích từ các video thắng.
   - `d:\Project\AI_video_tiktok\.agents\skills\tiktok-trend-video-creator\references\script-templates.md`: Các khung kịch bản & case study thực chiến để AI tham chiếu theo cơ chế Progressive Disclosure.

---

## 3. Tiêu chí hoàn thành mỗi phiên Training
Một phiên training chỉ được coi là hoàn tất khi:
- Đã lưu đầy đủ 4 file phân tích kênh trong `training_data/channels/<handle>/`.
- Đã tạo/cập nhật (additive) `.agents/rules/tiktok-content-rules.md`, `AGENTS.md`, và skill `.agents/skills/tiktok-trend-video-creator/` (kèm `references/`).
- Trình bày bản tóm tắt rõ ràng cho người dùng: số video đã phân tích, top phát hiện quan trọng nhất, danh sách các Rule & Skill đã tạo kèm đường dẫn file.
