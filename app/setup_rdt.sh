#!/bin/bash
# setup_rdt.sh - Tự động thiết lập Intel RDT (Resource Director Technology)
# Tự động mount resctrl và kiểm tra hỗ trợ

# Đảm bảo chạy với quyền root
if [ "$(id -u)" -ne 0 ]; then
    echo "Lỗi: Script này cần chạy với quyền root" >&2
    exit 1
fi

# Tạo thư mục mount point nếu chưa tồn tại
mkdir -p /sys/fs/resctrl

# Kiểm tra kernel hỗ trợ resctrl
if ! grep -q resctrl /proc/filesystems; then
    echo "Kernel không hỗ trợ resctrl filesystem (CONFIG_RESCTRL_FS không được bật)"
    echo "Đang thử nạp module intel_rdt..."
    
    # Thử nạp module
    modprobe intel_rdt 2>/dev/null || true
    
    # Kiểm tra lại
    if ! grep -q resctrl /proc/filesystems; then
        echo "Kernel không hỗ trợ RDT CAT - cần cài kernel với CONFIG_RESCTRL_FS=y"
        # Vô hiệu hóa plugin trong cấu hình
        if [ -f /app/mining_environment/config/cpu_plugins.yml ]; then
            sed -i 's/name: intel_cat\n  enabled: true/name: intel_cat\n  enabled: false/' /app/mining_environment/config/cpu_plugins.yml
            echo "Đã vô hiệu hóa plugin intel_cat trong cấu hình"
        fi
        exit 0
    fi
fi

# Mount resctrl filesystem
if ! mount | grep -q "resctrl on /sys/fs/resctrl"; then
    echo "Đang mount resctrl filesystem..."
    mount -t resctrl resctrl /sys/fs/resctrl
    
    if [ $? -ne 0 ]; then
        echo "Không thể mount resctrl filesystem"
        if [ -f /app/mining_environment/config/cpu_plugins.yml ]; then
            sed -i 's/name: intel_cat\n  enabled: true/name: intel_cat\n  enabled: false/' /app/mining_environment/config/cpu_plugins.yml
            echo "Đã vô hiệu hóa plugin intel_cat trong cấu hình"
        fi
        exit 1
    fi
fi

# Xác nhận mount thành công - kiểm tra file cbm_mask
if [ -f /sys/fs/resctrl/info/L3/cbm_mask ]; then
    echo "✅ RDT CAT đã được mount thành công"
    echo "Mask bit: $(cat /sys/fs/resctrl/info/L3/cbm_mask)"
    echo "Số lượng CLOS: $(cat /sys/fs/resctrl/info/L3/num_closids)"
    exit 0
else
    echo "⚠️ Mount thành công nhưng không tìm thấy file cbm_mask"
    echo "CPU có thể không hỗ trợ CAT"
    if [ -f /app/mining_environment/config/cpu_plugins.yml ]; then
        sed -i 's/name: intel_cat\n  enabled: true/name: intel_cat\n  enabled: false/' /app/mining_environment/config/cpu_plugins.yml
        echo "Đã vô hiệu hóa plugin intel_cat trong cấu hình"
    fi
    exit 1
fi 