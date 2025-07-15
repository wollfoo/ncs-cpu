# Giải pháp thay thế **cgroup** trong môi trường **container**

> Tài liệu tóm lược các phương pháp/ kỹ thuật quản lý và giới hạn tài nguyên có thể sử dụng thay cho **cgroup** (Control Groups) truyền thống của Linux, đặc biệt khi chạy bên trong container.

| # | Giải pháp | Mô tả ngắn |
|---|-----------|-----------|
| 1 | **[Linux Namespace]** (Không gian tên) | Cô lập tài nguyên logic (PID, mạng, IPC, mount…) giữa các container; không điều tiết mức sử dụng nhưng giảm va chạm tài nguyên. |
| 2 | **[rlimit / setrlimit]** (Giới hạn tiến trình) | Đặt ngưỡng *hard*/*soft* cho CPU-time, số file descriptor, bộ nhớ…; áp dụng bên trong container mà không cần quyền root host. |
| 3 | **[CPU Affinity]** (Gắn core) | Ràng buộc tiến trình vào tập core nhất định qua `sched_setaffinity`/`taskset`; tránh phải tạo cgroup cpu. |
| 4 | **[seccomp]** (Bộ lọc syscall) | Chặn lời gọi hệ thống nguy hiểm/tốn tài nguyên; gián tiếp hạn chế tiêu hao tài nguyên. |
| 5 | **[eBPF / BPF]** (Chương trình trong kernel) | Theo dõi & chủ động *throttle* CPU/ I/O/ network mà không lệ thuộc cgroup; hoạt động linh hoạt trong container. |
| 6 | **[systemd Slice/Unit]** | Dùng systemd tạo *slice* gom tiến trình và áp hạn mức CPU/Memory/I/O; thao tác dễ hơn cgroup thuần. |
| 7 | **[cgroups v2 Unified Hierarchy]** | Kiến trúc cgroup thế hệ 2, hợp nhất subsystems, khắc phục hạn chế v1 khi container lồng nhau. |
| 8 | **[Hypervisor-based MicroVM]** (Firecracker, Kata) | Cô lập bằng ảo hoá siêu nhẹ, tách biệt kernel và tài nguyên phần cứng khỏi host. |
| 9 | **[Kubernetes QoS & ResourceQuota]** | Giới hạn CPU/Memory ở mức Pod/Namespace; người dùng cấu hình YAML, K8s tạo cgroup tự động. |
|10 | **[Userspace I/O Throttling]** (`ionice`, token bucket) | Giới hạn I/O từ không gian người dùng; không thay đổi cgroup cấp hệ. |
|11 | **[Nice / Priority Scheduling]** | Thay đổi độ ưu tiên (`nice`, `renice`) để container bớt được scheduler ưu ái. |
|12 | **[NUMA Control]** (`numactl`) | Gắn container vào NUMA node riêng, giảm tranh chấp cache và bộ nhớ. |
|13 | **[Control Plane API Rate-Limiting]** | Hạn chế số request tới Docker daemon, Kubelet… để ngăn "bão" container gây cạn tài nguyên. |
|14 | **[Sidecar Limiter]** (Container phụ) | Quan sát & gửi `SIGSTOP`/`SIGCONT` cho container chính khi vượt ngưỡng; không chạm trực tiếp cgroup host. |

---
*Ngày tạo: {{date}}* 