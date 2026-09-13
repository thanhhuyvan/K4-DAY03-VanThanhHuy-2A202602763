# Demo tổng hợp Discord từ ảnh chụp

Dữ liệu: 16 khối tin trong kênh 💬-chung, ngày 13/09/2026 từ 00:08 đến 12:31.
Nguồn là 4 ảnh người dùng cung cấp; chưa đủ ngày, chưa kết nối Discord API.

## Chạy nhanh trong PowerShell

Đứng tại thư mục gốc dự án:

```powershell
.\.venv\Scripts\python.exe src/app.py --provider mock --all
.\.venv\Scripts\python.exe src/app.py --provider mock --interactive
```

Mock trích đoạn theo quy tắc để kiểm tra luồng, không phải tóm tắt AI.
Mỗi câu hỏi tương tác là một phiên độc lập.

## Chạy Gemini thật

Điền trực tiếp trong .env:

```dotenv
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=your_actual_key
```

```powershell
.\.venv\Scripts\python.exe src/app.py --provider gemini
.\.venv\Scripts\python.exe src/app.py --provider gemini --all
```

Lệnh đầu chỉ chạy một bản tổng hợp. Lệnh --all chạy cả 5 câu hỏi.
Văn bản hội thoại được gửi đến Gemini khi chọn provider gemini; ảnh gốc không được gửi.
Demo hiện hỗ trợ mock và Gemini. providers.py của starter được giữ làm tham khảo; app.py dùng discord_providers.py.
API lỗi sẽ dừng và báo lỗi, không tự chuyển sang mock.

## Kịch bản trình bày 2–3 phút

1. Mở dữ liệu và ảnh trong data/private/discord_demo_2026-09-13.
2. Chạy một bản tổng hợp bằng Gemini.
3. Chỉ ra dòng Tool: read_day, câu trả lời có ID nguồn và cảnh báo chưa đủ ngày.
4. Chạy --interactive, hỏi: Ngày 2026-09-13 đăng nhập Zoom bằng email nào?
5. Hỏi: Đọc demo_msg_012 để đối chiếu nguồn ảnh.
6. Hỏi: Tổng hợp ngày 2026-09-12 để minh họa xử lý thiếu dữ liệu.

## Công cụ và giới hạn

- read_day(day): đọc bản dữ liệu đúng ngày.
- get_message(message_id): đọc tin cụ thể cùng nguồn ảnh.
- Lớp mcp_server.py là dispatcher trong cùng tiến trình, kế thừa mô phỏng của lab; chưa có MCP transport qua mạng.
- Tối đa 3 lượt LLM và 3 lần gọi tool mỗi yêu cầu; lượt LLM cuối không công bố tool.
- Gemini giới hạn 700 output tokens/lượt; tắt thinking cho dòng gemini-2.5-flash để giảm chi phí.
- Thường một lần gọi tool và một lần tổng hợp, tức 2 lượt LLM; không phải mức chi phí bảo đảm.
- Kiểm tra ID nguồn có trong dữ liệu đã đọc; điều này không bảo đảm mọi kết luận được nguồn hỗ trợ, vẫn cần đọc đối chiếu.
- ID demo_msg_NNN là ID nội bộ, không phải link Discord.
- Dữ liệu ngoài ngày/kênh và nội dung file đính kèm không được truy vấn.

## Kết quả lưu trên máy

Mỗi lần chạy tạo outputs/private/<provider>_<timestamp>/ gồm:
- summary.md: câu trả lời.
- trace.json: provider, trạng thái mock/live, câu hỏi, tool, observation, độ trễ thực đo và usage API khi có.

docs/trace_waterfall.json giữ bản trace lần chạy gần nhất để phù hợp artifact bài lab.
File này có nội dung hội thoại; chỉ chia sẻ sau khi kiểm tra/ẩn danh nếu cần.
data/private và outputs/private được Git bỏ qua. Bản clone mới cần dữ liệu demo tương ứng trên máy.

## Kiểm thử offline

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

5 test case ở config/test_cases.json có expected_behavior để đối chiếu khi chạy API thật.
Thông báo hoàn tất kỹ thuật chỉ xác nhận chương trình trả kết quả, không tự chấm đúng ngữ nghĩa.
