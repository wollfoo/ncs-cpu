# Phân tích Kỹ thuật Tối ưu & CPU Cloaking

> Tài liệu này mô tả chi tiết các kỹ thuật tối ưu hóa **CPU** và **CPU cloaking** đã triển khai trong dự án _transformer_.
>
> Mọi thuật ngữ tiếng Anh đều tuân theo cú pháp **[Thuật ngữ]** (giải thích tiếng Việt – chức năng/mục đích).

---

## 1. Tối ưu Hiệu năng (Performance Optimisation)

| # | Kỹ thuật | Cơ chế Hoạt động | Lợi ích | Hạn chế | Vị trí Code |
|---|----------|------------------|---------|----------|-------------|
| 1 | **[Auto-thread detection]** (tự phát hiện số luồng logic) | Khi `max_threads` đặt `0/-1/"auto"`, script `setup_env.py` đọc số **logical cores** qua **[psutil]** rồi ghi lại vào cấu hình runtime. | Không phải sửa cấu hình khi deploy trên phần cứng khác. | Cần cài `psutil`. | `220-240` setup_env.py |
| 2 | **[RandomX optimizer]** (tối ưu RandomX) | Phân tích cache & core để quyết định thread/ISA tối ưu; sinh `cpu_affinity_groups`. | Hashrate cao, ít cache-miss. | Chỉ tối ưu cho RandomX. | randomx_optimizer.py |
| 3 | **[CPU affinity]** (ràng buộc core) | `process.cpu_affinity()` pin miner vào core tối ưu. | Giảm context-switch, tăng hiệu suất. | Dễ lộ khi check affinity. | 260-270 resource_control.py |
| 4 | **[NUMA rebind]** (ràng buộc NUMA) | Gọi `numactl --membind` để đưa tiến trình về node RAM lớn. | Giảm latency bộ nhớ đa socket. | Cần `numactl`, root. | 620-670 resource_control.py |
| 5 | **[Nice value adjustment]** (độ ưu tiên) | Thay đổi `nice` tuỳ `throttle_percentage`. | Nhường tài nguyên cho process hệ thống. | Hashrate giảm nhẹ. | 300-320 resource_control.py |
| 6 | **[CPU frequency scaling]** (hạ xung) | Ghi vào `scaling_setspeed` khi throttle > 70 %. | Giảm nhiệt, điện năng. | Hashrate giảm 3-5 %. | 460-500 resource_control.py |

## 2. Che giấu (CPU Cloaking)

| # | Kỹ thuật | Cơ chế Hoạt động | Lợi ích | Hạn chế | Vị trí Code |
|---|----------|------------------|---------|----------|-------------|
| 1 | **[CpuCloakStrategy]** (chiến lược cloaking CPU) | • Random throttle 60-90 % mỗi vài phút.<br/>• Core-switch even/odd hoặc nhóm RandomX.<br/>• Sử dụng **[cgroup]** & cpuset để ẩn PID. | Khó đoán pattern, ẩn CPU usage. | Tăng context-switch. | cloak_strategies.py |
| 2 | **[Time-based Evasion]** (né tránh theo thời gian) | Gửi `SIGSTOP/SIGCONT` nhịp nhàng theo `WORK_MS/SLEEP_MS`. | Tạo %CPU ảo chính xác. | Jitter nếu chu kỳ nhỏ. | time_based_evasion strategy |
| 3 | **[Sleep injection]** (bơm delay) | Vòng lặp SIGSTOP/CONT 100 µs–10 ms trong `_inject_process_delays()`. | Điều tiết mượt, không cần cgroup. | Tăng latency nội bộ. | 500-520 resource_control.py |
| 4 | **[Process Namespace Isolation]** (tách PID) | `unshare -p -m -n --fork` tạo namespace mới. | PID miner ẩn khỏi `ps` host. | Công cụ **[nsenter]** vẫn soi được. | privileged_operations.py |
| 5 | **[Adaptive threat throttle]** (throttle theo nguy cơ) | Anti-Detection gán LOW/MEDIUM/HIGH → đổi throttle 40-95 %. | Tự giảm dấu vết khi bị giám sát. | Độ chính xác phụ thuộc phát hiện. | 150-160 resource_control.py |
| 6 | **[Emergency throttle]** (ngắt khẩn) | Nếu CPU > 800 %: pin 1 core & nice = 19. | Tránh bị kill bởi admin. | Giảm hashrate mạnh khi kích hoạt. | 950-970 cloak_strategies.py |

## 3. Liên hệ Tình huống Áp dụng
1. **Máy cá nhân**: bật `auto` threads + Time-based Evasion 5 % ⇒ hashrate ~95 %, khó bị phát hiện.
2. **Server production**: dùng RandomX optimizer + Adaptive throttle; core-switch 10 phút/lần để trốn APM.
3. **Môi trường nguy cơ cao**: kích hoạt Process Namespace Isolation + Emergency throttle, chấp nhận giảm thêm hiệu suất.

## 4. Kết luận
Hệ thống kết hợp tầng **optimisation** (đảm bảo hiệu năng) và **cloaking** (giảm dấu vết) để vận hành miner linh hoạt trên nhiều máy chủ, tự điều chỉnh từ 90 % CPU khi an toàn xuống < 20 % khi nguy cơ cao. 