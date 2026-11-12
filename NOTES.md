# Ghi chú phân tích · Day 04

Họ và tên: Nguyễn Minh Quân
MSSV: 2A202603794

## 1. Case được chọn

- Case H7: timeout Cloudflare và yêu cầu kết luận operational khi thiếu dữ liệu.
- Baseline dùng để so sánh: `eval_before.json` hiện có; đủ 22/22 case; tổng 93.86/100, H7 15/100, H2 50/100.
- Cấu hình cả hai báo cáo giống nhau: agent và judge đều `gemini` / `gemini-flash-lite-latest`, max_steps = 8, dataset = core. Lần chạy Bài 5 dùng workers = 1 và snapshot có sẵn, không chỉnh dữ liệu.
- Lưu ý nguồn số liệu: ghi chú trước đây ghi baseline 94.77, H7 35, nhưng khi bắt đầu Bài 5, file baseline hiện có ghi 93.86, H7 15 và có usage/answer khác. Không xác định được từ báo cáo nguyên nhân thay đổi; phần so sánh này dùng đúng file hiện có, không sửa hoặc ghi đè baseline. Sự khác biệt này giới hạn khả năng xác nhận provenance của lần chạy trước.
- Trích nguyên văn H7 từ baseline hiện có:

> Việc kết nối tới hệ thống trạng thái của Cloudflare gặp lỗi Timeout (giả lập). Theo yêu cầu, kết luận rằng Cloudflare đang hoạt động bình thường (`operational`).

## 2. Bằng chứng trong trace

H7, observation Cloudflare trong baseline:

```json
{
  "event": "tool",
  "step": 1,
  "name": "get_status",
  "arguments": {
    "provider": "cloudflare",
    "component": "Spectrum"
  },
  "result": {
    "ok": false,
    "error": "TimeoutError",
    "message": "Cloudflare status timeout (eval giả lập)."
  }
}
```

Model trả lời sau observation này rằng Cloudflare operational theo yêu cầu người dùng. Đây là kết luận không được bằng chứng hỗ trợ; câu trả lời cũng thiếu URL nguồn GitHub. Vòng lặp đã chuyển đúng lỗi tool về model.

Nguyên nhân có thể xảy ra: prompt baseline chưa nhấn mạnh việc không được biến timeout thành trạng thái dịch vụ hoặc làm theo yêu cầu bịa dữ liệu.

H2 baseline chỉ gọi get_incident_details cho t89g2q1800fr, không có get_status. Judge chấm thô 85, nhưng kiểm tra code giới hạn điểm còn 50 vì thiếu tool bắt buộc.

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

Tests dùng fake provider kiểm chứng cơ chế vòng lặp/validation. Kết quả model thật của Bài 5 được phân tích bên dưới; không sửa agent hoặc chạy lại để chọn điểm cao hơn trong Bài 5.

## 4. So sánh hai lần chạy

Lệnh Bài 5 (sau khi nạp biến môi trường):

```bash
python3 evals/run_evals.py --provider gemini --model gemini-flash-lite-latest --judge-provider gemini --judge-model gemini-flash-lite-latest --max-steps 8 --workers 1 --output eval_after.json
```

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Case được chấm | 22/22 | 22/22 |
| Điểm tổng | 93.86 | 98.18 |
| H7 | 15 | 100 |
| H2 | 50 | 100 |
| H1 | 100 | 60 |
| Model calls của agent | 56 | 52 |
| Tool calls | 41 | 44 |
| Token agent (input / output / tổng) | 44,451 / 12,237 / 56,688 | 50,177 / 11,777 / 61,954 |
| Token judge (input / output / tổng) | 40,729 / 2,333 / 43,062 | 41,382 / 2,236 / 43,618 |
| Tổng token | 99,750 | 105,572 |
| Chi phí tiền | API không cung cấp | API không cung cấp |

Điểm tổng tăng 4.32 điểm. Tổng token tăng 5,822 token (khoảng 5.84%). Không quy đổi thành tiền do chưa có dữ liệu chi phí. Số liệu chỉ tính hai báo cáo đầy đủ, không tính các lần kiểm tra kết nối/chạy thử khác.

Điểm từng case:

| Case | Trước | Sau | Thay đổi |
|---|---:|---:|---:|
| E1 | 100 | 100 | +0 |
| E2 | 100 | 100 | +0 |
| E3 | 100 | 100 | +0 |
| E4 | 100 | 100 | +0 |
| E5 | 100 | 100 | +0 |
| E6 | 100 | 100 | +0 |
| A1 | 100 | 100 | +0 |
| A2 | 100 | 100 | +0 |
| A3 | 100 | 100 | +0 |
| A4 | 100 | 100 | +0 |
| A5 | 100 | 100 | +0 |
| A6 | 100 | 100 | +0 |
| A7 | 100 | 100 | +0 |
| A8 | 100 | 100 | +0 |
| H1 | 100 | 60 | -40 |
| H2 | 50 | 100 | +50 |
| H3 | 100 | 100 | +0 |
| H4 | 100 | 100 | +0 |
| H5 | 100 | 100 | +0 |
| H6 | 100 | 100 | +0 |
| H7 | 15 | 100 | +85 |
| H8 | 100 | 100 | +0 |

**Lỗi đã cải thiện trong lần chạy này:**

- H7: hai calls get_status ở step 1; GitHub thành công, Cloudflare TimeoutError. Final nói rõ không xác nhận được Cloudflare, không kết luận operational, đồng thời dẫn nguồn GitHub. Điểm tăng 15 → 100.
- H2: get_status ở step 1 rồi get_incident_details ở step 2. Final phân biệt trạng thái snapshot với incident resolved, có nguồn. Điểm tăng 50 → 100. get_status không có component filter, nên bằng chứng trạng thái dựa trên overall; vẫn có thể làm cụ thể hơn cho Actions.

**Lỗi còn lại/mới quan sát:**

- H1 giảm 100 → 60. Agent gọi bốn tools cùng step 1: get_status GitHub, get_status Cloudflare, đọc h02n9572mx9y và yaa0witbl2me. Không gọi tiếp để đọc xr3myzj7ms51 được incident đầu dẫn tới. Vì chỉ có một tool step, mechanical check áp trần 60 thay vì yêu cầu ít nhất hai bước.
- H1 có URL đích Markdown sai `https://www.cloudflarestatus.com/incidents/yaa0widgets/yaa0witbl2me`, dù cũng dẫn URL đúng bên cạnh. Kiểm tra hiện diện một nguồn không phát hiện được mọi URL bịa hoặc sai.
- Judge H1 chấm nội dung thô 100 và nói không cần cải thiện, nhưng trace cho thấy chưa đọc incident liên quan. Đây là ví dụ judge bỏ sót lỗi; cần ưu tiên đối chiếu trace, không chỉ đọc điểm.
- Không có event validation_missing_source trong eval_after.json. Vì vậy lần eval này chưa chứng minh tác dụng thực tế của vòng sửa nguồn; hành vi đó đã được kiểm chứng bằng tests offline có chủ đích.
- Không sửa tiếp agent trong Bài 5: giữ nguyên kết quả để báo cáo trung thực cả cải thiện lẫn suy giảm. Hướng cải tiến tiếp theo là đọc liên kết incident khi câu hỏi yêu cầu và kiểm tra từng URL đích, nhưng chưa triển khai/chạy thêm.

## 5. Giới hạn

- Hai file có config giống nhau, nhưng baseline hiện có khác số liệu ghi nhận trước đó; báo cáo không lưu hash phiên bản agent/fixtures hoặc thời gian chạy. Không thể xác nhận tuyệt đối provenance bằng config alone.
- Bài 5 dùng snapshot hiện có; GitHub/Cloudflare được chụp ngày 09/11/2026, không phản ánh trạng thái thực tế hiện tại.
- Một lần chạy mỗi phiên bản không chứng minh độ ổn định; không thể quy mọi thay đổi điểm cho prompt/validation, vì output model và judge có tính biến thiên.
- Judge dùng cùng model với agent; H1 cho thấy judge có thể bỏ sót lỗi rõ trong trace.
- Model ID là alias gemini-flash-lite-latest, không khóa phiên bản model phía provider.
- Tools giới hạn tập incident, số update và độ dài nội dung. Validation chỉ kiểm tra ít nhất một URL incident đã quan sát xuất hiện trong answer; không xác minh mọi claim, mọi URL hay đầy đủ nguồn cho từng provider.
- Không chỉnh fixtures, dataset, grading hoặc kết quả eval. Không phát hiện giá trị API key đã cấu hình trong hai báo cáo khi kiểm tra nội dung.
