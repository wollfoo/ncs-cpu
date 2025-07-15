# Phân tích Toàn diện Việc Sử dụng **cgroup** và Kế hoạch Chuyển đổi

> Tài liệu này tổng hợp kết quả rà soát mã nguồn, đánh giá hiệu năng, đồng thời đề xuất lộ trình thay thế **cgroup** trong dự án _transformer_. Mọi thuật ngữ tiếng Anh tuân thủ cú pháp **[Thuật ngữ]** (mô tả tiếng Việt – chức năng/mục đích).

---

## 1. Các **module** đang dùng **cgroup**

| # | Module | Vai trò | Mã tiêu biểu |
|---|---------|---------|--------------|
| 1 | `PrivilegedOperationManager` | Tạo & cấu hình cgroup CPU/RAM cho PID miner | ```235:257:app/mining_environment/scripts/privileged_operations.py``` |
| 2 | `CpuCloakStrategy` | Gọi hàm trên để khởi tạo cgroup trước khi throttle | ```695:705:app/mining_environment/scripts/cloak_strategies.py``` |
| 3 | `CPUResourceManager` | • **[optimize_thread_scheduling]** (dùng cpuset)<br/>• **[delete_cgroup]** (xoá rác)<br/>• **[unassign_all_pids_in_cgroup]** (di chuyển PID) | ```560:578``` / ```823:836``` / ```881:918:app/mining_environment/scripts/resource_control.py``` |
| 4 | **Unit-tests** | Kiểm thử hàm tạo cgroup | ```160:173:app/mining_environment/scripts/tests/test_privileged_operations.py``` |

---

## 2. **Dependencies** & **Integration Points**

* **[Pathlib]** (thao tác file) và **[psutil]** (quản lý tiến trình) là 2 phụ thuộc chính.
* Luồng gọi chính:
  ```
  start_mining.py → CloakStrategyFactory → CpuCloakStrategy.apply()
                               ↘
              PrivilegedOperationManager.setup_cgroup_limits()
  ```
* Các hằng path cgroup (CPU, cpuset) đang **hard-code** bên trong `CPUResourceManager` ⇒ khó port sang container không được mount đầy đủ.

---

## 3. **Performance impact** (ảnh hưởng hiệu năng)

* Việc tạo folder & ghi quota O(1) nhưng tăng I/O khi nhiều PID.
* `throttle_cpu_usage()` hiện **không** dùng quota ⇒ phần cloaking vẫn phụ thuộc `nice`/`SIGSTOP` → cgroup chưa phát huy hết.
* Hàm `delete_cgroup()` quét **[glob]** toàn cây `/sys/fs/cgroup` có thể tốn thời gian nếu có hàng nghìn cgroup.

---

## 4. **Resource constraints** (ràng buộc tài nguyên hiện tại)

| Tài nguyên | File cgroup | Giá trị mặc định |
|------------|------------|------------------|
| CPU quota | `cpu.cfs_quota_us` | `100000 × throttle%` |
| Period CPU | `cpu.cfs_period_us` | 100 000 µs (mặc định kernel) |
| RAM | `memory.limit_in_bytes` | 2 GiB |
| cpuset | `cpuset.mems` (đặt = 0); `cpuset.cpus` chưa ghi | N/A |

---

## 5. Phương án thay thế **cgroup**

| # | Giải pháp | Mô tả | Phù hợp |
|---|-----------|-------|---------|
| 1 | **[cgroups v2 Unified Hierarchy]** | Chuyển tới kiến trúc v2, dùng file `cpu.max`, `memory.max` | Dễ tích hợp với systemd/K8s |
| 2 | **[eBPF-based Throttling]** | Viết chương trình eBPF theo dõi & giới hạn CPU/I-O | Chính xác, không cần mount cgroup |
| 3 | **[CPU Affinity + rlimit]** | Gắn core + `setrlimit()` CPU/RSS | Đơn giản, không req. quyền root host |

### So sánh chi tiết

| Tiêu chí | v2 | eBPF | Affinity + rlimit |
|----------|----|------|-------------------|
| **Compatibility** với mã cũ | ⭐⭐⭐ | ⭐ | ⭐⭐ |
| **Độ phức tạp** | Trung bình | Cao | Thấp |
| **Quản lý tài nguyên** | Đầy đủ | Toàn diện (tuỳ code) | Giới hạn |
| **Hỗ trợ platform** | Kernel ≥ 4.15 | Kernel ≥ 5.x + CAP_BPF | Mọi Linux |

---

## 6. **Migration strategy** (giả định chọn cgroups v2)

1. **Chuẩn bị**: Bật kernel flag `systemd.unified_cgroup_hierarchy=1` hoặc Docker `--cgroupns=host`.
2. **Refactor mã**:
   * Đổi path cgroup sang v2 slice/scope.
   * Ghi quota qua `cpu.max` (`"<quota> <period>"`).
   * Ghi RAM qua `memory.max`.
3. **Feature flag**: `USE_CGROUP_V2=1` → nhánh code mới; giai đoạn **dual-write** song song v1/v2.
4. **Canary & Gradual rollout**: 10 % → 25 % → 100 % node.
5. **Deprecate**: Sau 2 tuần không lỗi, xoá nhánh v1, cập nhật tài liệu.

### Breaking changes
* Kernel < 4.15 không hỗ trợ v2.
* Tool userspace cũ (`cgdelete`, `ionice` cho blkio) chưa tương thích.

### Testing approach
* **[Unit test]**: Mock FS `/sys/fs/cgroup` v2, kiểm tra file ghi đúng.
* **[Integration test]**: Chạy container privileged trên Ubuntu 22.04, đo CPU quota với **[stress-ng]**.
* **[Performance regression]**: Thu thập `perf schedstat`, đảm bảo latency context-switch < 5 %.
* **[Chaos test]**: SIGKILL miner, xác thực `delete_cgroup()` dọn slice.

---
*Ngày tạo: {{date}}* 