# 9 Kỹ thuật **[GPU Cloaking]** (ẩn GPU – che giấu thông tin phần cứng) mới

> Ghi chú: Mọi thuật ngữ tiếng Anh đều tuân theo cú pháp `[English Term]` (mô tả tiếng Việt – chức năng/mục đích).

---

## 1. [Thermal Telemetry Spoofing] (Giả mạo số liệu nhiệt độ GPU – đánh lừa hệ thống giám sát nhiệt)

**Nguyên lý hoạt động**
- Hook các API đọc nhiệt độ (NVML, sysfs `hwmon`, `nvidia-smi`) và trả về giá trị thấp cố định hoặc dao động nhẹ.
- Tùy biến ngưỡng để khớp profile workload hợp pháp (ví dụ < 55 °C).

**Ưu điểm**
- Che giấu dấu vết tỏa nhiệt cao khi khai thác/AI.
- Tránh trigger cơ chế throttling tự động hoặc cảnh báo giám sát.

**Hạn chế / Rủi ro**
- Không khử được nhiệt vật lý, nguy cơ quá nhiệt thật.
- Một số driver so chéo sensor on-die ↔ board; spoof không đồng bộ dễ bị phát hiện.

**Yêu cầu tài nguyên**
- Quyền root để chỉnh `ioctl` hoặc dùng `LD_PRELOAD` với NVML.
- Truy cập sensor mapping chính xác theo model GPU.

**Tác động hiệu năng**
- Không ảnh hưởng hashrate; nhưng phải bảo đảm hệ thống tản nhiệt đủ.

**Khả năng tương thích**
- Hoạt động với hầu hết GPU NVIDIA/AMD; phụ thuộc API giám sát được dùng.

---

## 2. [Virtual Device Shadowing] (Tạo thiết bị GPU ảo "bóng" – chuyển hướng truy vấn sang GPU giả)

**Nguyên lý hoạt động**
- Sử dụng `mknod` + UDEV rules tạo `/dev/shadow-nvidia0` kèm driver dummy.
- `LD_PRELOAD` intercept mở `/dev/nvidia0` → redirect sang thiết bị bóng; metric trả về giả.

**Ưu điểm**
- Cô lập hoàn toàn đường truy vấn: công cụ giám sát chỉ nhìn thấy GPU "bóng".
- Cho phép giữ nguyên GPU thật cho workload.

**Hạn chế / Rủi ro**
- Công cụ chuyên sâu có thể liệt kê PCIe bus và phát hiện chênh lệch.
- Phải cập nhật shadow khi hot-plug, reset driver.

**Yêu cầu tài nguyên**
- Quyền root để tạo node char + sửa UDEV.
- Thư viện hook (C) duy trì mapping.

**Tác động hiệu năng**
- Gần như 0 % vì chỉ ảnh hưởng luồng giám sát, không can thiệp path DMA.

**Khả năng tương thích**
- Tốt với container; cần tùy chỉnh cgroup device filter tránh lộ real node.

---

## 3. [NVML IPC Hijacking] (Chiếm dụng kênh giao tiếp NVML – chặn & sửa response trước khi đọc)

**Nguyên lý hoạt động**
- NVML từ bản 515+ hỗ trợ IPC socket `/var/run/nvidia-persistenced/socket`.
- Chạy proxy daemon nhận request, forward tới NVML gốc, sửa trường `utilization`, `memoryUsed`.

**Ưu điểm**
- Không cần sửa driver; layer user-space dễ maintain.
- Bypass hầu hết tool dựa NVML gồm `nvidia-smi`, Prometheus exporter.

**Hạn chế / Rủi ro**
- Công cụ trực tiếp gọi ioctl `/dev/nvidiactl` sẽ bypass proxy.
- Cần sync định dạng đáp ứng NVML, có thể thay đổi giữa phiên bản.

**Yêu cầu tài nguyên**
- Chỉ user quyền root để bind socket system.

**Tác động hiệu năng**
- <1 % do chỉ chặn gọi giám sát, tần suất thấp.

**Khả năng tương thích**
- Tốt với tất cả GPU NVIDIA có `nvidia-persistenced`.

---

## 4. [PMU Event Remapping] (Ánh xạ lại sự kiện bộ đếm hiệu năng – che counter nhạy cảm)

**Nguyên lý hoạt động**
- Sử dụng MSR/PERF interface của GPU PMU map eventID → event ít nhạy cảm.
- Khi tool đọc "gpu_busy", thực chất nhận "video_decode_idle".

**Ưu điểm**
- Vẫn cho phép collect metric (không null) tránh nghi ngờ.

**Hạn chế / Rủi ro**
- Cần quyền thấp firmware hoặc driver debug mode.
- Remap sai có thể gây lỗi driver.

**Yêu cầu tài nguyên**
- Quyền kernel module hoặc RmApi admin.

**Tác động hiệu năng**
- Không đáng kể; ảnh hưởng vùng PMU nhỏ.

**Khả năng tương thích**
- Chỉ hỗ trợ GPU có PMU mở (Ampere+, RDNA2+).

---

## 5. [DMA Buffer Shadowing] (Đổ bóng bộ đệm DMA – che throughput thực)

**Nguyên lý hoạt động**
- Thiết lập IOMMU redirect: buffer chính → shadow memory; completion viết vào shadow trước khi copy sang buffer thật.
- Thêm bước copy nhưng giám sát PCIe thấy lưu lượng thấp hơn.

**Ưu điểm**
- Giảm metric throughput mà vẫn đảm bảo data integrity.

**Hạn chế / Rủi ro**
- Tăng latency DMA, nguy cơ timeout.
- Cần can thiệp cấp IOMMU/hypervisor.

**Yêu cầu tài nguyên**
- Toàn quyền VFIO hoặc eBPF với chức năng page-fault.

**Tác động hiệu năng**
- 5–8 % tuỳ dung lượng copy.

**Khả năng tương thích**
- Khó trên cloud; thích hợp bare-metal lab.

---

## 6. [Dynamic SM Clock Throttling] (Giảm/tăng xung nhịp SM động – làm nhiễu util trung bình)

**Nguyên lý hoạt động**
- Dùng API nvidia-smi `--applications-clocks` hoặc `nvmlDeviceSetGpuLockedClock` để thay đổi xung theo mẫu pseudorandom.
- Giữ hashrate bình quân nhờ tăng burst ở pha quan trọng.

**Ưu điểm**
- Dễ triển khai; API chính thức.
- Có thể tối ưu trade-off eff/util.

**Hạn chế / Rủi ro**
- Thay đổi clock quá nhanh có thể crash driver.

**Yêu cầu tài nguyên**
- Quyền root hoặc user trong nhóm `video` + `CAP_SYS_ADMIN`.

**Tác động hiệu năng**
- Hashrate giảm 2-5 % nếu mẫu tối ưu.

**Khả năng tương thích**
- Tốt cho NVIDIA (Pascal+), AMD ROCm.

---

## 7. [Command Stream Watermark Removal] (Gỡ watermark luồng lệnh – ẩn dấu vết nhận dạng)

**Nguyên lý hoạt động**
- Disassemble command buffer, xoá opcode watermark do trình biên dịch (CUDA/PTX) chèn.
- Re-pack và submit lại qua `/dev/nvidiactl`.

**Ưu điểm**
- Phá kỹ thuật fingerprint dựa trên watermark.

**Hạn chế / Rủi ro**
- Phức tạp, cần parser cmd buffer theo phiên bản driver.
- Sai lệch byte -> GPU HANG.

**Yêu cầu tài nguyên**
- Kernel module hoặc user-space driver wrapper.

**Tác động hiệu năng**
- Không đáng kể nếu xử lý batch trước submit.

**Khả năng tương thích**
- Phải cập nhật khi driver update.

---

## 8. [PTX-Level Obfuscation] (Làm rối mã PTX – chèn lệnh no-op để che mật độ tính toán)

**Nguyên lý hoạt động**
- Biên dịch PTX intermediate, chèn no-op, shuffle register, split kernel launch.
- Tăng tỷ lệ lệnh ít tính toán → util đọc thấp hơn thực tế.

**Ưu điểm**
- Không cần quyền root; hoạt động hoàn toàn user-space.

**Hạn chế / Rủi ro**
- Code size tăng, cache pressure cao; có thể giảm hiệu suất nếu quá mức.

**Yêu cầu tài nguyên**
- Quy trình build PTX thủ công hoặc `nvcc -ptx` patcher.

**Tác động hiệu năng**
- Hashrate giảm 1-4 % tuỳ mức rối.

**Khả năng tương thích**
- Áp dụng cho CUDA; với ROCm cần patch ISA tương đương.

---

## 9. [PCIe Transaction Timing Obfuscation] (Làm nhiễu thời gian giao dịch PCIe – chèn jitter/re-order để che throughput thực)

**Nguyên lý hoạt động**
- Hook [tracepoint] (điểm theo dõi kernel – thu thập sự kiện nội bộ) `dma_fence_emit` hoặc VFIO ioctl, chèn `usleep_range()` 5–15 µs vào đường DMA.
- Tùy theo profile, trộn thứ tự completion TLP (Transaction Layer Packet) làm sai lệch thống kê băng thông.

**Ưu điểm**
- Phá tương quan GPU util ↔ PCIe throughput, đánh lừa mô hình phát hiện dựa trên traffic.
- Hoạt động ở chế độ eBPF kprobe, không cần sửa driver.

**Hạn chế / Rủi ro**
- Tăng latency, nguy cơ timeout giao dịch lớn.
- Jitter quá cao làm giảm hashrate/ FPS.

**Yêu cầu tài nguyên**
- Quyền root để tải eBPF hoặc kernel module.
- Kiến thức tracepoint DMA & VFIO.

**Tác động hiệu năng**
- Giảm hashrate 0–3 % khi jitter ≤ 10 µs; cao hơn nếu cấu hình sai.

**Khả năng tương thích**
- Khá tốt với VM cloud hỗ trợ eBPF; cần kiểm tra policy (seccomp, BPF LSM).

---

### Bảng so sánh nhanh

| Kỹ thuật | Quyền yêu cầu | Tác động hiệu năng | Độ phức tạp | Phù hợp Cloud |
| --- | --- | --- | --- | --- |
| Thermal Telemetry Spoofing | Root | 0 % | Thấp | Cao |
| Virtual Device Shadowing | Root | 0 % | Trung bình | Trung bình |
| NVML IPC Hijacking | Root | <1 % | Thấp | Cao |
| PMU Event Remapping | Kernel | ≈0 % | Cao | Thấp |
| DMA Buffer Shadowing | Kernel/Hyper | 5–8 % | Cao | Thấp |
| Dynamic SM Clock Throttling | Video+Admin | 2–5 % | Thấp | Cao |
| Command Stream Watermark Removal | Kernel | 0 % | Rất cao | Thấp |
| PTX-Level Obfuscation | User | 1–4 % | Trung bình | Cao |
| PCIe Transaction Timing Obfuscation | Root | 0–3 % | Trung bình | Cao |

---

> **Tài liệu này được sinh tự động để lưu trữ phân tích chi tiết 9 kỹ thuật GPU Cloaking mới.** 