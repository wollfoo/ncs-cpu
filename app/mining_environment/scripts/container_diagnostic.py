#!/usr/bin/env python3
"""
🔍 **Container Diagnostic Script** (Script chẩn đoán trong container)
Kiểm tra hoạt động của logging và xác minh các log levels
"""

import os
import sys
import logging
from pathlib import Path

# ✅ **Cấu hình logging đơn giản** (Simple logging configuration)
# Sử dụng /tmp để tránh vấn đề permission
log_file = '/tmp/container_diagnostic.log'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('ContainerDiagnostic')

def analyze_existing_logs():
    """✅ **Phân tích log files hiện có** (Analyze existing log files)"""
    log_dir = Path('/app/mining_environment/logs')
    
    logger.info("🔍 Starting container diagnostic...")
    logger.info(f"📁 Checking log directory: {log_dir}")
    
    if log_dir.exists():
        log_files = list(log_dir.glob('*.log'))
        logger.info(f"📄 Found {len(log_files)} log files:")
        
        for log_file in log_files:
            try:
                size = log_file.stat().st_size
                logger.info(f"   {log_file.name}: {size} bytes")
                
                # Đọc và phân tích nội dung
                with open(log_file, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                    # Đếm các loại log messages
                    debug_count = sum(1 for line in lines if 'DEBUG' in line)
                    info_count = sum(1 for line in lines if 'INFO' in line)
                    warning_count = sum(1 for line in lines if 'WARNING' in line)
                    error_count = sum(1 for line in lines if 'ERROR' in line)
                    
                    logger.info(f"   - DEBUG: {debug_count} lines")
                    logger.info(f"   - INFO: {info_count} lines")
                    logger.info(f"   - WARNING: {warning_count} lines")
                    logger.info(f"   - ERROR: {error_count} lines")
                    
                    # Hiển thị 3 dòng đầu và cuối
                    if lines:
                        logger.info("   First 3 lines:")
                        for line in lines[:3]:
                            if line.strip():
                                logger.info(f"     {line.strip()}")
                        
                        logger.info("   Last 3 lines:")
                        for line in lines[-3:]:
                            if line.strip():
                                logger.info(f"     {line.strip()}")
                                
            except Exception as e:
                logger.error(f"❌ Error analyzing {log_file}: {e}")
    else:
        logger.error(f"❌ Log directory {log_dir} does not exist")

def test_logger_levels():
    """✅ **Test các mức độ logger** (Test logger levels)"""
    logger.info("🧪 Testing logger levels...")
    
    # Test các mức độ khác nhau
    logger.debug("🔍 DEBUG: This should appear if DEBUG level is enabled")
    logger.info("ℹ️ INFO: This should appear if INFO level or higher is enabled")
    logger.warning("⚠️ WARNING: This should appear if WARNING level or higher is enabled")
    logger.error("❌ ERROR: This should always appear")

def check_file_permissions():
    """✅ **Kiểm tra quyền truy cập file** (Check file permissions)"""
    log_dir = Path('/app/mining_environment/logs')
    
    logger.info("🔐 Checking file permissions...")
    
    if log_dir.exists():
        stat_info = log_dir.stat()
        logger.info(f"📁 Log directory permissions: {oct(stat_info.st_mode)[-3:]}")
        logger.info(f"📁 Log directory owner: {stat_info.st_uid}")
        logger.info(f"📁 Log directory group: {stat_info.st_gid}")
        
        # Kiểm tra quyền write
        can_write = os.access(log_dir, os.W_OK)
        logger.info(f"✏️ Can write to log directory: {can_write}")
        
        # Kiểm tra từng file log
        for log_file in log_dir.glob('*.log'):
            can_write_file = os.access(log_file, os.W_OK)
            logger.info(f"✏️ Can write to {log_file.name}: {can_write_file}")

if __name__ == "__main__":
    logger.info("🚀 Starting container diagnostic...")
    
    test_logger_levels()
    analyze_existing_logs()
    check_file_permissions()
    
    logger.info("✅ Container diagnostic completed")
    logger.info(f"📋 Diagnostic log saved to: {log_file}")