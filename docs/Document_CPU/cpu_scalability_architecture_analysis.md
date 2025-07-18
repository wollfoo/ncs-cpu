# Phân tích Kiến trúc Mở Rộng, Tối Ưu Hóa CPU và **CPU Cloaking**

> Tài liệu này tổng hợp đánh giá kiến trúc hiện tại, khả năng mở rộng, các kỹ thuật tối ưu hóa CPU cùng phương pháp **CPU cloaking** (ẩn/giả lập mức sử dụng CPU) của dự án _transformer_. Mọi thuật ngữ tiếng Anh tuân theo cú pháp **[Thuật ngữ]** (Giải thích tiếng Việt – mô tả chi tiết chức năng/mục đích/cách hoạt động).

---

## 1. Phân tích Kiến trúc Hiện Tại

| Yếu tố | Điểm Mạnh | Điểm Yếu |
|--------|-----------|----------|
| **Module hóa** | Tách lớp **ResourceManager** (quản trị tài nguyên) và **CloakStrategy** (chiến lược ẩn) ⇒ dễ mở rộng. | Hằng số **hard-code** (đường dẫn cgroup, ngưỡng throttle) giảm linh hoạt. |
| **Singleton Pattern** | **[Singleton Pattern]** (mẫu đơn) cho `PrivilegedOperationManager` – giảm overhead. | Coupling cao: nhiều module gọi trực tiếp, khó mock khi test. |
| **Retry Logic** | **[Retry Logic]** (logic thử lại) giúp tự hồi phục khi Sys-call lỗi. | Chưa thống nhất timeout/delay, dễ gây storm khi lỗi liên tục. |
| **Thread Background** | Health-monitor chạy nền phát hiện & tối ưu liên tục. | Mỗi container nhân bản sẽ có nhiều thread giám sát trùng lặp. |

---

## 2. Đánh Giá Khả Năng Mở Rộng

| Tiêu chí | Hiện trạng | Khả năng cải tiến |
|----------|-----------|-------------------|
| **Module hóa cấu hình** | Hằng số gắn trong mã. | Trích sang **[Config Provider]** (trình nạp YAML/ENV) → thay đổi runtime không rebuild. |
| **Tách biệt tiến trình** | Thread helper nằm chung process miner. | Dùng **[Sidecar Container]** (container đồng hành) giám sát – tránh double-thread khi scale deployment. |
| **Điều phối đa node** | Không có API từ xa. | Thêm **[gRPC Service]** (dịch vụ gRPC) để orchestrator trigger scale-out. |

---

## 3. Phân Tích Tối Ưu Hóa CPU

| # | Kỹ thuật | Hiện tại | Khuyến nghị cải tiến |
|---|----------|----------|----------------------|
| 1 | **[Auto-thread detection]** (phát hiện luồng) | Lấy số core logic và tự đặt threads. | Giới hạn trên bằng **[RLIMIT_NPROC]** (giới hạn số luồng) để tránh fork-bomb. |
| 2 | **[CPU Affinity]** (ràng buộc core) | `process.cpu_affinity()` cho từng PID. | Gọi batch `sched_setaffinity` theo nhóm core → giảm sys-call. |
| 3 | **[NUMA Rebind]** (ràng buộc NUMA) | Gọi shell `numactl --membind`. | Dùng **[libnuma]** (thư viện C) qua Python CFFI để tránh spawn process. |
| 4 | **[Cache-aware RandomX optimizer]** | Re-bench mỗi lần chạy. | Lưu kết quả vào **[SQLite]** (DB nhúng) để tái sử dụng. |
| 5 | **[CPU Frequency Scaling]** (giảm xung) | Viết trực tiếp `scaling_setspeed`. | Sử dụng **[Intel RDT]** (chia cache LLC) giữ hiệu suất thay vì hạ xung toàn CPU. |

---

## 4. **CPU Cloaking** & Cơ Chế Anti-Detection

| Kỹ thuật | Cách hoạt động | Rủi ro | Biện pháp giảm thiểu |
|----------|----------------|--------|----------------------|
| **[CpuCloakStrategy]** | Random throttle 60–90 % & core-switch. | Pattern có thể bị học máy. | Thêm **entropy seed** theo thời gian thực. |
| **[Time-based Evasion]** | `SIGSTOP/CONT` tạo %CPU ảo. | Đồng bộ pha khi nhiều worker. | Offset ngẫu nhiên mỗi PID. |
| **[Sleep Injection]** | Delay 100 µs–10 ms trong vòng lặp. | Tăng context-switch. | Theo dõi **[perf sched]** để không vượt ngưỡng. |
| **[Process Namespace Isolation]** | `unshare` tách PID. | **[nsenter]** vẫn quan sát được. | Kết hợp **[seccomp]** chặn syscall rò rỉ PID. |
| **[Adaptive Threat Throttle]** | Anti-Detection gán mức LOW/MEDIUM/HIGH. | Sai lệch khi heuristic thiếu chính xác. | Log lý do mỗi lần thay đổi throttle. |

---

## 5. Bảng So Sánh Phương Án Kiến Trúc Cho Mở Rộng & Cloaking

| Tiêu chí | **[cgroups v2]** (Kiến trúc cgroup thế hệ 2) | **[eBPF Throttling]** (Giới hạn qua eBPF) | **Affinity + rlimit** (Gắn core & giới hạn CPU/RSS) |
|----------|----------------------------------------------|-------------------------------------------|---------------------------------------------|
| Tương thích mã cũ | ⭐⭐⭐ | ⭐ | ⭐⭐ |
| Độ phức tạp triển khai | Trung bình | Cao | Thấp |
| Quản lý tài nguyên | Đầy đủ (CPU, RAM, I/O) | Rất linh hoạt | Giới hạn |
| Khả năng mở rộng | Delegate slice, dùng cho container con | Hook bất kỳ PID | Phụ thuộc số tiến trình |
| Chi phí runtime | Thấp (kernel native) | Cực thấp (in-kernel) | Không thêm chi phí kernel |
| Khả năng bị phát hiện | Trung bình (APM đọc cgroup) | Thấp (BPF nội bộ) | Cao (APM thấy nice/affinity) |

---

## 6. Khuyến Nghị Cụ Thể

1. **Ngắn hạn** – bật flag **cgroups v2** để giữ mô hình I/O file, dễ bảo trì.  
2. **Trung hạn** – phát triển nhánh **eBPF** nhằm bỏ phụ thuộc root, đạt throttle chính xác.  
3. **Dài hạn** – chuẩn hoá hằng số vào **Config Provider** & tách **ResourceManager** thành gói độc lập để tái sử dụng.

### Kiểm thử & Giám sát
* **[Unit Test]**: dùng **pyfakefs** mô phỏng `/sys/fs/cgroup` & `/proc`.  
* **[Load Test]**: `stress-ng --cpu N` đo latency context-switch.  
* **[Chaos Engineering]**: **[Pumba]** (công cụ gây lỗi container) để kiểm tra tự phục hồi cloaking.

---
*Ngày tạo: {{date}}* 