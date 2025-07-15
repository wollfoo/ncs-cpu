#!/bin/bash
#
# clear-docker-all.sh - Xóa triệt để tất cả tài nguyên Docker
#

echo "======================================================================"
echo "   XÓA TRIỆT ĐỂ TẤT CẢ TÀI NGUYÊN DOCKER (CONTAINER, IMAGE, VOLUME)   "
echo "======================================================================"
echo ""
echo "⚠️  CẢNH BÁO NGHIÊM TRỌNG ⚠️"
echo "Script này sẽ XÓA VĨNH VIỄN:"
echo "  - TẤT CẢ container (bao gồm cả đang chạy)"
echo "  - TẤT CẢ image"
echo "  - TẤT CẢ volume & dữ liệu trong đó"
echo "  - TẤT CẢ network"
echo "  - TẤT CẢ build cache"
echo ""
echo "Dữ liệu đã xóa KHÔNG THỂ KHÔI PHỤC!"
echo ""

# Yêu cầu xác nhận
read -p "Bạn có chắc chắn muốn tiếp tục không? (gõ 'xoa-tat-ca' để xác nhận): " confirm
if [[ "$confirm" != "xoa-tat-ca" ]]; then
    echo "Xác nhận không chính xác. Đã hủy thao tác."
    exit 1
fi

echo ""
echo "🔄 Bắt đầu quá trình dọn dẹp Docker..."
echo ""

# Dừng tất cả container đang chạy
echo "👉 [1/6] Dừng tất cả container đang chạy..."
sudo docker stop $(sudo docker ps -q) 2>/dev/null || true

# Xóa tất cả container
echo "👉 [2/6] Xóa tất cả container..."
sudo docker rm -f $(sudo docker ps -a -q) 2>/dev/null || true

# Xóa tất cả image
echo "👉 [3/6] Xóa tất cả image..."
sudo docker rmi -f $(sudo docker images -q) 2>/dev/null || true

# Dọn dẹp build cache
echo "👉 [4/6] Dọn dẹp build cache..."
sudo docker builder prune --all --force

# Dọn dẹp network
echo "👉 [5/6] Dọn dẹp network..."
sudo docker network prune --force

# Dọn dẹp volume
echo "👉 [6/6] Dọn dẹp volume..."
sudo docker volume prune --force

echo ""
echo "✅ HOÀN TẤT: Tất cả tài nguyên Docker đã được dọn sạch!"
echo ""
echo "💡 Kiểm tra trạng thái hiện tại: sudo docker system df"
echo "======================================================================" 