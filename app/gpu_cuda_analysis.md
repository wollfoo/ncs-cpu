# Phân Tích GPU CUDA: "disabled (no devices)" Container Analysis

## 1. Vai Trò & Phạm Vi  
**Chuyên Gia DevOps** - Phân tích lỗi CUDA disabled trong container Docker opus-container  
**Phạm vi**: Cấu hình Docker, quyền truy cập GPU devices, mapping thư viện CUDA  

## 2. Phân Tích Nguyên Nhân  

### **TREE-OF-THOUGHT 🌳**

#### Nhánh A: [Device Mapping] **- Thiếu ánh xạ NVIDIA devices**
- Host có 2x Tesla V100 đã được phát hiện (`nvidia-smi` hiển thị bình thường)
- Container run với `--gpus all` nhưng **[inference-cuda]** không nhận diện được GPU
- `/dev/nvidia*` devices tồn tại trên host nhưng chưa chắc accessible trong container

#### Nhánh B: [CUDA Runtime Libraries] **- Mismatch phiên bản CUDA**  
- **[Dockerfile:1]** sử dụng `nvcr.io/nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04`
- **[nvidia-smi]** hiển thị `CUDA Version: 12.4` trên host
- **[inference-cuda]** binary có thể được build với CUDA version khác
- **[libmlls-cuda.so]** có thể không tương thích với CUDA runtime 12.0

#### Nhánh C: [Container Runtime] **- NVIDIA Container Toolkit issues**
- **[nvidia-container-toolkit]** được cài trong **[Dockerfile:60]** 
- Container runtime có thể không inject GPU resources đúng cách
- **[LD_PRELOAD]** hooks có thể can thiệp vào CUDA initialization

## 3. Nhánh Tốt Nhất  
**Chọn Nhánh B - CUDA Runtime Libraries Mismatch** vì:
- Log lỗi rõ ràng: `CUDA disabled (no devices)` sau khi load các hook
- **[LD_PRELOAD]** chứa `/opt/hooks/libgpuhook.so` có thể can thiệp CUDA detection
- **[libmlls-cuda.so]** binary được copy từ external source không rõ compatibility

## 4. Đề Xuất Khắc Phục  

| Hướng | Mô tả | Trích dẫn minh chứng |  
|-------|-------|----------------------|  
| **1. Tắt GPU Hooks tạm thời** | Disable `LD_PRELOAD` hooks để test CUDA detection thuần | `Dockerfile:209` - `LD_PRELOAD="/opt/hooks/libtempspoof.so:/opt/hooks/libgpuhook.so"` |  
| **2. Kiểm tra CUDA compatibility** | Verify binary `inference-cuda` với CUDA 12.0 runtime | `docker run ... --gpus all --env LD_PRELOAD="" /usr/local/bin/inference-cuda --version` |  
| **3. Test container GPU access** | Kiểm tra `nvidia-smi` trong container với devices mapping | Lệnh run có `--gpus all --device /dev/kmsg` nhưng thiếu explicit device mapping |  

## 5. Tự Phê & Chỉnh Sửa (Vòng 1)  

### **Điểm yếu được xác định:**
1. **Thiếu test cụ thể**: Chưa chạy test GPU access trực tiếp trong container
2. **Không phân tích binary**: Chưa kiểm tra dependencies của `inference-cuda` 
3. **Giả định về hooks**: Chưa verify `libgpuhook.so` thực sự block CUDA

### **Chỉnh sửa (🔄 marked):**
- 🔄 **Bổ sung test command cụ thể**: `docker exec opus-container nvidia-smi`
- 🔄 **Kiểm tra ldd dependencies**: `ldd /usr/local/bin/inference-cuda | grep cuda`
- 🔄 **Verify container device access**: `ls -la /dev/nvidia* inside container`

## 6. Phiên Bản Cuối (Sau Vòng 2)  

### **Root Cause Analysis:**
- **[Primary]**: GPU hooks trong `LD_PRELOAD` can thiệp vào CUDA device enumeration
- **[Secondary]**: Potential CUDA version mismatch giữa binary và runtime
- **[Tertiary]**: Container device mapping cần verification

### **Immediate Actions:**
1. **Test GPU access**: `docker exec opus-container nvidia-smi`
2. **Disable hooks test**: `docker exec opus-container env LD_PRELOAD="" /usr/local/bin/inference-cuda --version`  
3. **Check CUDA deps**: `docker exec opus-container ldd /usr/local/bin/inference-cuda`

### **Expected Resolution:**
Sau khi tắt GPU hooks hoặc fix device mapping, **[inference-cuda]** sẽ detect được 2x Tesla V100 devices.

---

**Evidence-Only Principle**: Tất cả khẳng định dựa trên log thực tế, cấu hình Dockerfile và output nvidia-smi đã cung cấp.  
**Anti-Hallucination**: Không bịa thêm cấu hình hay binary version chưa được verify.