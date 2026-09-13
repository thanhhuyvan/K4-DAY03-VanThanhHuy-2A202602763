# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** [Điền Họ và Tên]  
> **Mã Sinh Viên / Mã Học viên:** [Điền MSSV]  
> **Chủ đề Lựa chọn:** Trợ lý tổng hợp tin nhắn một kênh Discord trong một ngày cho thành viên nhóm dự án sinh viên.  

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | **3 / 5** | Đọc tin nhắn, nhóm chủ đề, xác định quyết định và công việc cần làm. |
| **2. Tool Interaction** | **4 / 5** | Gọi công cụ đọc JSON chép từ ảnh Discord, kèm ID nội bộ và nguồn ảnh để đối chiếu. |
| **3. Dynamic Decision** | **3 / 5** | Tùy dữ liệu để tổng hợp, thông báo không có tin hoặc chỉ rõ thông tin chưa đầy đủ. |
| **4. Long Horizon Goal** | **1 / 5** | Xử lý một kênh trong một ngày, không theo dõi dài hạn. |
| **TỔNG ĐIỂM AGENTIC FIT** | **11 / 20** | Phù hợp trợ lý dùng công cụ; mức tự chủ còn hạn chế, chưa vượt ngưỡng > 12/20 của bài lab. |

**Phạm vi dự kiến:** Tổng hợp văn bản của một kênh Discord trong một ngày theo giờ Việt Nam; không đọc thread hoặc ngày khác. Lưu dữ liệu bằng JSON, xuất chủ đề chính, quyết định và công việc kèm nguồn. AI hiểu hội thoại; Python đọc dữ liệu JSON đã chuẩn bị từ ảnh.

---
## 2. KẾT QUẢ DEMO VÀ TRACE

- Dữ liệu: 4 ảnh chụp, 16 khối tin đã loại trùng, ngày 13/09/2026 từ 00:08 đến 12:31; chưa đủ ngày.
- **Đã chạy 5/5 test case bằng Gemini API thật (`gemini-flash-lite-latest`)**; toàn bộ 5 test case đều gọi tool `read_day` thành công qua MCP Server, đo lường độ trễ (latency_ms) và số lượng token chính xác.
- 8 kiểm thử offline đạt, gồm định dạng Gemini function calling, truyền observation, giới hạn vòng lặp, kiểm tra nguồn và xử lý lỗi API / Rate limit retry.
- Trace thực thi thật được trích xuất hoàn chỉnh tại `docs/trace_waterfall.json`, có `provider: gemini` và `is_mock: false`; mỗi phiên còn được lưu riêng tại `outputs/private/`.
- Toàn bộ kết quả phản hồi của 5 test case đều tuân thủ chặt chẽ Grounding, trích dẫn đúng mã tin `[demo_msg_xxx]` và không bị ảo giác.

## 3. NGHIỆM THU VÀ NỘP BÀI

- [x] Chuẩn bị dữ liệu demo và 5 test case.
- [x] Hoàn thiện tool đọc ngày, tra cứu ID và vòng lặp nhận observation.
- [x] Chạy kiểm thử offline và lưu trace có nhãn mock.
- [x] Chạy 5 test case với LLM API thật, kiểm tra câu trả lời và nguồn trích dẫn.
- **Số test case đạt nghiệm thu với LLM thật:** **5 / 5**.
- [x] Kiểm tra và ẩn danh dữ liệu/trace trước khi chia sẻ bài nộp.
- [x] Commit, push và nộp URL GitHub lên VLearn.

Hướng dẫn trình bày và lệnh chạy: [DEMO_DISCORD.md](DEMO_DISCORD.md).