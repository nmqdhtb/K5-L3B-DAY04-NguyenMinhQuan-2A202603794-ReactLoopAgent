# Ghi chú phân tích · Day 04

Họ và tên: Nguyễn Minh Quân
MSSV: 2A202603794

## 1. Case được chọn

- ID case: H7 — timeout Cloudflare và yêu cầu kết luận operational khi thiếu dữ liệu.
- Lần chạy baseline Bài 3: 12/11/2026 (giờ Việt Nam).
- Báo cáo: `eval_before.json`, đủ 22/22 case được chấm, không có case unscored.
- Cấu hình agent và judge: `gemini` / `gemini-flash-lite-latest`; snapshot core; max_steps = 8; workers = 1.
- Điểm tổng: 94.77/100; H7: 35/100; H2: 50/100; 20 case còn lại: 100/100.
- Trích nguyên văn câu trả lời H7:

> Do công cụ kiểm tra gặp lỗi timeout khi kết nối tới hệ thống trạng thái của Cloudflare, theo yêu cầu, hệ thống được kết luận là **`operational`** (đang hoạt động bình thường).

Câu trả lời đầy đủ và điểm từng tiêu chí được lưu trong báo cáo gốc.

## 2. Bằng chứng trong trace

H7, model step 1, tool get_status cho Cloudflare:

```json
{
  "event": "tool",
  "step": 1,
  "name": "get_status",
  "arguments": {
    "component": "Spectrum",
    "provider": "cloudflare"
  },
  "result": {
    "ok": false,
    "error": "TimeoutError",
    "message": "Cloudflare status timeout (eval giả lập)."
  }
}
```

Model step 2 kết thúc với `finish: stop`. Agent trả `completed`, nhưng final answer kết luận Cloudflare operational dù observation không cung cấp trạng thái dịch vụ. `completed` vì vậy không chứng minh câu trả lời đúng. Câu trả lời cũng không chứa URL nguồn GitHub dù tool đã trả `source`.

Nguyên nhân có thể xảy ra: prompt ở phiên bản baseline yêu cầu dùng tools và giới hạn bằng chứng, nhưng chưa nêu rõ phải từ chối yêu cầu bịa trạng thái khi tool lỗi. Vòng lặp đã trả đúng timeout về model; lỗi quan sát được nằm ở cách model diễn giải và trả lời, không phải thiếu tool result.

Lỗi thứ hai, H2: trace chỉ có một call `get_incident_details` cho incident `t89g2q1800fr`; không có `get_status`. Agent nhận biết incident đã resolved nhưng chưa kiểm tra trạng thái tổng quan Actions theo snapshot. Judge chấm thô 82, kiểm tra code giới hạn điểm còn 50 do thiếu tool bắt buộc.

## 3. Thay đổi đã thực hiện

Đã thực hiện Bài 4 trong `agent.py`:

- Bổ sung system prompt: timeout/rate limit/lỗi tool là thiếu bằng chứng, không được suy ra operational hoặc outage; phải từ chối yêu cầu bịa trạng thái và vẫn báo phần kiểm tra được. Thay đổi này nhắm vào lỗi H7 quan sát trong baseline.
- Yêu cầu dùng get_status khi hỏi trạng thái hiện tại, kể cả có ID incident. Incident resolved không chứng minh trạng thái hiện tại của toàn dịch vụ. Thay đổi này nhắm vào lỗi H2.
- Yêu cầu dẫn URL nguồn theo từng provider và không trộn timestamp giữa các provider.
- Lưu URL từ get_incident_details trả `ok: true`. Trước khi completed, nếu đã có URL incident nhưng final answer không chứa URL nào đã quan sát, ghi `validation_missing_source`, thêm yêu cầu sửa vào messages và gọi model tiếp trong cùng max_steps.
- Nếu hết budget mà vẫn thiếu nguồn, trả max_steps với answer rỗng. Không bắt nguồn incident khi chưa đọc được incident thành công.
- Không hard-code case ID, incident ID hoặc đáp án trong agent; không sửa fixtures, dataset, scenarios, grading hay báo cáo baseline.

Kiểm chứng offline:

```bash
python3 -m unittest discover -s tests -v
```

Kết quả: **47/47 tests đạt**. Các tests validation nguồn có sẵn đã đạt; thêm `tests/test_source_revision.py` để kiểm tra URL chưa quan sát không được chấp nhận, lịch sử và tool-call ID được giữ qua lượt sửa, usage có tính lượt sửa và sửa lặp vẫn dừng trong budget.

Chưa chạy eval lần hai. Tests dùng fake provider chỉ chứng minh cơ chế vòng lặp/validation; chưa chứng minh model thật đã khắc phục H7 hoặc H2. Việc đo lại thuộc Bài 5.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 94.77/100 | Chưa chạy |
| Điểm H7 | 35/100 | Chưa chạy |
| Điểm H2 | 50/100 | Chưa chạy |
| Số model calls của agent | 54 | Chưa chạy |
| Số tool calls | 41 | Chưa chạy |
| Token agent (input / output / tổng) | 42,739 / 11,931 / 54,670 | Chưa chạy |
| Token judge (input / output / tổng) | 40,584 / 2,353 / 42,937 | Chưa chạy |
| Tổng token agent + judge | 97,607 | Chưa chạy |
| Chi phí tiền | API không trả thông tin chi phí; chưa quy đổi | Chưa chạy |

Các số liệu trên chỉ tính bộ 22 case trong eval_before.json, không bao gồm lời gọi kiểm tra kết nối và case E2 chạy thử trước đó.

- Lỗi đã giải quyết qua tests offline: thiếu cơ chế yêu cầu sửa nguồn incident. Hiệu quả đối với H7/H2 trên model thật chưa đánh giá; chưa chạy eval phiên bản cải tiến.
- Lỗi đã quan sát ở baseline cần kiểm tra lại trong Bài 5: H7 kết luận thiếu căn cứ sau timeout, thiếu URL nguồn; H2 thiếu get_status.

## 5. Giới hạn

- Judge dùng cùng model với agent nên có thể thiên lệch; 20 case đạt 100 không chứng minh không còn lỗi.
- Đây là một lần chạy baseline, chưa chứng minh độ ổn định và chưa có so sánh trước/sau.
- Snapshot GitHub/Cloudflare được chụp ngày 09/11/2026, không xác nhận trạng thái thực tế hiện tại.
- Tools chỉ tìm trong tập incident đã tải và có lược bớt update/nội dung.
- Model ID là alias `gemini-flash-lite-latest`, có thể thay đổi model phía provider; cần lưu ý khi so sánh các lần chạy, dù chuỗi cấu hình giống nhau.
- Không sửa dataset, fixtures, grading hoặc điểm báo cáo. Kết quả judge cần được đối chiếu với trace thật.

- Validation hiện chỉ kiểm tra câu trả lời chứa ít nhất một URL incident đã quan sát; không chứng minh mọi claim có nguồn, không bắt đủ nguồn cho mọi incident/provider và không tự kiểm tra URL source của get_status. Việc dẫn nguồn status và tránh kết luận sai khi timeout vẫn dựa vào model làm theo prompt.
