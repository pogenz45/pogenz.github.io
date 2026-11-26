---
trigger: always_on
description: >-
  Bộ quy chuẩn sản xuất, viết kịch bản, tối ưu Hook 0–3s, dựng hình, âm thanh,
  tương tác và kiểm duyệt nội dung video TikTok xu hướng cho dự án AI_video_tiktok.
  Mọi quy tắc đều gắn bằng chứng thực tế từ các kênh đã training theo nguyên tắc tích lũy (additive).
---

# Quy chuẩn Sản xuất Nội dung TikTok (`tiktok-content-rules`)

> **Phiên bản:** `v1.0` (Cập nhật: `2026-11-26`)  
> **Nguyên tắc bảo toàn (Additive Only):** Mọi phiên training kênh mới chỉ được **bổ sung quy tắc mới, nối thêm dẫn chứng hoặc mở rộng biến thể** — tuyệt đối KHÔNG tự ý xóa hoặc ghi đè các quy tắc cũ đang hoạt động.  
> **Nguồn dữ liệu đã tích hợp:**
> - `@tam_thefox` (*Tâm Thefox*, 495.7K followers, `median_views = 58,000` trên 248 video quét lưới, Đợt 1: 19 video mổ xẻ chi tiết tại `training_data/channels/tam_thefox/`).

---

## [R-01] Tách bạch Mục tiêu Phễu (TOFU Viral vs BOFU Chuyển đổi) trước khi lên ý tưởng
- **Quy tắc bắt buộc:** Mọi video trước khi viết kịch bản phải khai báo rõ thuộc **Tầng Phễu Trên (TOFU — kéo reach đại chúng)** hay **Tầng Phễu Dưới (BOFU — định vị chuyên gia / chốt khách / tài trợ)**; KHÔNG dùng chuẩn thời lượng hay chỉ số của tầng này để ép lên tầng kia.
  - **TOFU (Kéo view & follower):** Ưu tiên chủ đề phổ quát (tính năng mới/cài đặt ẩn nền tảng, công cụ miễn phí, giải ảo lầm tưởng số đông, listicle nỗi đau định lượng). Mục tiêu thời lượng **`40–76 giây`** (hoặc `25–35 giây` cho 1 thao tác duy nhất).
  - **BOFU (Định vị & ra khách):** Dùng khung tư duy 2×2, ẩn dụ trực quan, phân tích chi phí minh bạch (`90–180 giây`). Đánh giá bằng tỷ lệ Like (`>= 4%`), Save (`>= 1.2%`) và chất lượng bình luận hỏi dịch vụ thay vì chỉ nhìn tổng view.
- **Lý do & Bằng chứng (`@tam_thefox`):** 6/7 video organic triệu view (`#1` 15.2M/57s, `#114` 6.6M/70s, `#112` 5.7M/42s, `#94` 5.1M/76s, `#198` 3.7M/54s, `#226` 2.7M/43s) đều nằm trong khung `42–76s`; trong khi video BOFU dài 2–5 phút (`#2` Ghim 22.2K/138s — Like 5.01%, `#3` 1.5K/179s — Like 6.50%, `#4` Odoo 11.5K/296s) có view đại chúng thấp nhưng kéo trực tiếp lead hỏi khám kênh.

## [R-02] Không tách rời Viral Hữu cơ với Traffic Đẩy trả phí khi đặt Benchmark
- **Quy tắc bắt buộc:** Khi nghiên cứu kênh tham chiếu hoặc học theo mẫu thắng, bắt buộc kiểm tra nhãn `Paid partnership` / `Sponsored` và tỷ lệ `Like / View` để phân biệt viral hữu cơ (thường `Like >= 1.0%`) với lượt xem có đẩy chiến dịch nền tảng/quảng cáo (`Like < 0.6%`).
- **Lý do & Bằng chứng (`@tam_thefox`):** Video `#140` (`166.4M` views, Like `0.13%`) mang thông điệp SEO chính thức `#CreatorSearchInsights` và `#35` (`5M` views, Like `0.50%`, nhãn `Paid partnership` + bình luận `"vì 3k6 xu"`) có dấu hiệu đẩy phân phối chiến dịch; ngược lại `#114` (`6.6M`, Like `2.70%`, Save `1.02%`) và `#198` (`3.7M`, Like `4.78%`, Share `3.73%`) là chuẩn mẫu viral hữu cơ thuần để nhân bản.

## [R-03] Quy tắc 3 Lớp Hook trong 0–3 Giây Đầu (Zero Friction)
- **Quy tắc bắt buộc:** Trong 3 giây đầu (`00:00–00:03`), video BẮT BUỘC hội tụ đủ 3 yếu tố và đạt độ dễ hiểu tức thời (không bắt người xem giải đố hay đọc câu dài):
  1. **Visual Hook tự nhiên (Native TikTok Feel):** Khung hình người thật toàn màn hình (trong xe hơi, studio sáng, hoặc 2 nhân vật đối lập màu) HOẶC ảnh/màn hình app thật có **khoanh tròn/khung chữ nhật màu đỏ** chỉ đích danh 1 nút bấm.
  2. **Text Hook 2 tầng tương phản (khuyến nghị mạnh cho TOFU):** Pill trên nền trắng chữ đen in hoa nêu chủ đề/lợi ích (`CÁCH TĂNG LƯỢT XEM`, `TÍNH NĂNG MỚI`) + Pill dưới nền đỏ đậm chữ trắng xóa rào cản hoặc chốt kết quả (`mà không tốn thêm chi phí`, `Giúp bạn làm video nhanh hơn`).
  3. **Câu mở lời đánh thẳng 1 con số nỗi đau, 1 hành động bắt buộc, hoặc 1 lầm tưởng phổ biến** (`"dưới 200 lượt xem"`, `"mà bạn bắt buộc [bật] một cái cài đặt"`, `"Cứ tưởng nhạc hot auto lên xu hướng"`).
- **Cấm tuyệt đối ở 0–3s:**
  - KHÔNG mở đầu bằng nền đồ họa dạng slide/poster đóng khung mặt nhỏ giống quảng cáo (`@tam_thefox #9` chỉ đạt `6,065` views, `OS = 0.10x` dù ngắn 37s và Like 6%).
  - KHÔNG để trống hoàn toàn text hook / phụ đề (`@tam_thefox #128` trồng cây không chữ đạt `4,947` views, `OS = 0.09x`).
  - KHÔNG bắt người xem giải đố điền chữ dài (`@tam_thefox #77` đạt `6,585` views, `OS = 0.11x`).
  - KHÔNG mở đầu bằng nhật ký cá nhân tự quy chiếu không liên quan lợi ích người xem (`@tam_thefox #37` `"giờ mình ra sân bay"` đạt `5,010` views, `OS = 0.09x`).

## [R-04] Thiết kế Nhịp dựng & Reset Chú ý (Pattern Interrupts)
- **Quy tắc bắt buộc:**
  - Với video **≤ 75 giây**: Phải có ít nhất 1 bước chuyển thị giác rõ rệt trước mốc 45% thời lượng (chuyển sang demo màn hình điện thoại kèm PiP mặt, chèn meme chia đôi màn hình, hoặc cắt luân phiên 2 nhân vật mỗi 2–4s).
  - Với video **> 90 giây** (talking-head 1 góc máy hoặc hướng dẫn sâu): Bắt buộc **đổi Banner phân chương trên đầu mỗi 35–45 giây** hoặc dùng **thanh tiến trình đánh số (`① → ⑤`) + pill teaser giữ chân** (`"👁 Tí nữa xem tận mắt"`), kết hợp **chớp tint đỏ (red flash)** tại từ khóa cao trào hoặc vòng tròn đánh số màu vàng (`1`, `2`...).
  - Với video **Listicle** (`3/5 lý do...`): Phải đưa **mục số `1` xuất hiện ngay ở giây thứ 3–5**, tuyệt đối không rào đón quá 5 giây.
- **Lý do & Bằng chứng (`@tam_thefox`):** `#49` (`4.5M` views dù dài `111s` quay 1 góc studio) đổi banner phân chương ở `00:50` và bật pill đỏ chốt nguyên lý ở `01:38`; `#226` (`2.7M`, `43s`) chèn meme split-screen ở `00:18` rồi demo `TikTok Creative Center` ở `00:37`; `#6` (`74.2K`, `OS = 1.28x`) vào thẳng số `1` kèm red flash ngay `00:03`.

## [R-05] Quy chuẩn Vùng An toàn Phụ đề & Đồ họa (TikTok UI Safe Zone)
- **Quy tắc bắt buộc:**
  - Mọi video nói chuyện/hướng dẫn **bắt buộc có phụ đề cứng (burnt-in subtitles)** nổi bật, ưu tiên chữ **vàng đậm có viền đen** (hoặc pill nền tối tô vàng từ khóa chính cho video chuyên gia).
  - Đặt phụ đề ở **vùng giữa-dưới an toàn (`55%–60%` chiều cao khung hình)**, cách mép phải tối thiểu 18% (tránh cột icon Like/Comment/Save/Share) và cách mép dưới tối thiểu 25% (tránh caption, tên âm thanh và nhãn anchor CapCut).
  - Banner tiêu đề / thanh phân chương đặt ở **vùng trên-giữa (`15%–28%` chiều cao)**, tránh bị thanh điều hướng `Following / For You` trên cùng che khuất.
- **Lý do & Bằng chứng (`@tam_thefox`):** Toàn bộ 7/7 video organic triệu view (`#1`, `#114`, `#112`, `#94`, `#49`, `#198`, `#226`) giữ phụ đề vàng viền đen ở vùng `y ≈ 55–60%`, hiển thị sắc nét không đè UI; ngược lại `#245` (`3,407` views, `OS = 0.06x`) dùng chữ trắng mỏng kém tương phản trên nền tối.

## [R-06] Cơ chế Kích hoạt Bình luận, Lưu (Save) & Chia sẻ (Share) Chủ động
- **Quy tắc bắt buộc:** Mỗi kịch bản phải thiết kế sẵn ít nhất **1 động cơ hành vi cụ thể** (không chỉ nói chung chung "nhớ like và follow"):
  1. **Vòng lặp Bình luận Từ khóa (Keyword Comment Loop):** Nhắc tên 1 công cụ/thuật ngữ cụ thể (`Creator Search Insights`, `TikTok Creative Center`) hoặc hiện thẻ CTA cam lớn (`BÌNH LUẬN [TỪ KHÓA]`) / câu mồi ngắn dễ gõ (`tự tìm đến`) để người xem tự bình luận ghi nhớ.
  2. **Visual Comment CTA 3 giây cuối:** Chèn đồ họa bong bóng bình luận đang gõ kèm câu hỏi kiểm tra dễ trả lời Có/Không (`"có tính năng này không và bình luận cho mình biết"`).
  3. **Động cơ Lưu (Bookmark):** Đưa bằng chứng trực quan đáng xem lại (danh sách số liệu, nút cài đặt khoanh đỏ, bảng 5 bước/chi phí, danh sách ví dụ sai/đúng).
  4. **Động cơ Chia sẻ / Meta-Share:** Giải ảo 1 lầm tưởng phổ biến hoặc hài hóa một thao tác quen thuộc khiến người xem muốn gửi cho đồng đội hoặc thử bấm tương tác.
- **Lý do & Bằng chứng (`@tam_thefox`):** `#114` (`6.6M`) đạt `7,901` bình luận (8/8 top comment gõ `"Creator Search Insights"`) & `67.4K` saves; `#1` (`15.2M`) dùng graphic bong bóng comment cuối clip đạt `5,947` comments; `#198` (`3.7M`) khai thác meta-share `"Sao chép liên kết"` đạt kỷ lục **`138,000` shares (`3.73%`)**.

## [R-07] Quy chuẩn Âm thanh & Giọng dẫn
- **Quy tắc bắt buộc:**
  - Kênh chia sẻ giá trị/hướng dẫn **bắt buộc dùng giọng nói rõ nét (voice-led)** bằng micro cài áo/thu âm sạch làm xương sống; KHÔNG bỏ giọng dẫn sang làm kịch câm theo nhạc nền không lời.
  - Chỉ dùng nhạc nền trend (như speed-up) ở mức âm lượng nền nhỏ hoặc khi khớp trực tiếp với chủ đề video (ví dụ nói về nhạc xu hướng).
- **Lý do & Bằng chứng (`@tam_thefox`):** 8/9 Top Outlier dùng `âm thanh gốc / nhạc nền - Tâm Thefox` làm trục chính; `#226` (`2.7M`) ghép nhạc trend `Valentina (Speed up)` đúng chủ đề nhạc xu hướng; ngược lại `#77` (`6.5K`, kịch câm theo `Little Things`) và `#128` (`4.9K`, B-roll không giọng nói) đều tụt sâu về `OS = 0.09x–0.11x`.

## [R-08] Quy chuẩn Caption, Hashtag & Phễu Ghim Profile
- **Quy tắc bắt buộc:**
  - **Caption:** Ngắn gọn 1 dòng (3–15 từ) gợi tò mò hoặc kêu gọi thử ngay (`"Nhớ bật lên nhé"`, `"Thử cách đăng này nhé"`, `"5 lý do dưới 200 lượt xem"`), KHÔNG viết mơ hồ học thuật (`"thể hiện được yếu tố này"`).
  - **Hashtag:** Đúng **4–5 hashtag** bám sát ngách (`1 hashtag thương hiệu` + `2–3 hashtag ngành` + `1 hashtag từ khóa cụ thể của video`); **TUYỆT ĐỐI tránh** hashtag rác quá chung chung (`#xuhuong`, `#viral`, `#hot`) và **kiểm tra kỹ dấu cách giữa các hashtag** (tránh lỗi dính liền như `#tamthefox#tamthefoxm` ở `#4`).
  - **Chiến lược Ghim Profile (2–3 video):** Ghim `#1` = Video triệu view chứng minh năng lực & kéo phễu; Ghim `#2` = Video khung tư duy chuyên sâu lọc đúng khách hàng mục tiêu của Bio.
- **Lý do & Bằng chứng (`@tam_thefox`):** Chính Tâm cảnh báo tránh `#xuhướng`, `#viral`, `#hot` trong `#6` (`74.2K`); các video triệu view đều dùng 4–5 hashtag sạch; cấu trúc Ghim `#1` (`15.2M`) + Ghim `#2` (`22.2K`, 2×2 framework) tối ưu cả uy tín lẫn chuyển đổi về `www.tamthefox.com`.

## [R-09] Chu trình Vận hành Sau đăng: Seeding 24h & Vòng lặp Bình luận → Kịch bản
- **Quy tắc bắt buộc:**
  - Trong **24 giờ đầu sau khi đăng**, chủ kênh phải chủ động **thả tim và phản hồi** các bình luận gõ từ khóa, bình luận hỏi chi tiết và bình luận kể trải nghiệm thật.
  - Sau mỗi video đạt `outlier_score >= 1.5`, bắt buộc quét Top 20 bình luận để lọc ra **rào cản / câu hỏi lặp lại nhiều like nhất** và chuyển hóa thẳng thành kịch bản video kế tiếp (Comment-to-Content Flywheel).
- **Lý do & Bằng chứng (`@tam_thefox`):** Bình luận `165 likes` `"Dính bản quyền tắt tiếng"` dưới `#226` (`2.7M`) sinh ra video `#203` (`2.2M` — *"Cách tìm nhạc sắp trend có bản quyền"*); làn sóng spam `"Fl chéo"` dưới `#1` (`15.2M`) và `#94` (`5.1M`) sinh ra video `#55` (`1.9M` — *"Đừng follow chéo nữa!!"*).

## [R-10] Cổng Kiểm duyệt Chống Flop (Bắt buộc trước khi Sản xuất / Đăng)
Trước khi chốt bất kỳ kịch bản hoặc bản dựng nào, bắt buộc đối chiếu 5 câu hỏi loại trừ:
1. Video có đi đúng chủ đề cốt lõi của kênh không? *(Chặn lỗi lệch ngách `#128`)*
2. Người lạ hoàn toàn (chưa từng biết kênh, chưa xem Phần 1) có hiểu ngay giá trị trong 3 giây đầu dù tắt tiếng không? *(Chặn lỗi `#9`, `#37`, `#77`, `#5`)*
3. Video có tránh mở đầu bằng slide đóng khung tĩnh / ánh sáng tối / thuật ngữ hàn lâm không? *(Chặn lỗi `#9`, `#245`)*
4. Thời lượng đã khớp đúng mục tiêu phễu chưa (`40–76s` cho TOFU, hoặc có đổi banner mỗi 40s nếu `> 90s`)? *(Chặn lỗi dài lan man `#37` 389s)*
5. Đã có ít nhất 1 bằng chứng trực quan (demo màn hình / khoanh đỏ / sơ đồ / 2 nhân vật) và 1 động cơ Comment/Save/Share cụ thể chưa?
