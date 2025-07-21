#!/usr/bin/env python3
"""
🔍 **Simple Diagnostic Script** (Script chẩn đoán đơn giản)
Kiểm tra hoạt động của logging mà không cần dependencies phức tạp
"""

import os
import sys
import logging
from pathlib import Path

# ✅ **Cấu hình logging diagnostic** (Cấu hình ghi log chẩn đoán)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/azureuser/grok4/app/mining_environment/logs/diagnostic.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_logging_levels():
    """✅ **Test logging levels** (Kiểm tra các mức độ logging)"""
    logger.info("🚀 Starting simple diagnostic test...")
    
    # Test tất cả các mức độ logging
    logger.debug("🔍 This is a DEBUG message - should appear in diagnostic.log")
    logger.info("ℹ️ This is an INFO message")
    logger.warning("⚠️ This is a WARNING message")
    logger.error("❌ This is an ERROR message")
    
    # Kiểm tra các log files hiện có
    log_dir = Path('/home/azureuser/grok4/app/mining_environment/logs')
    logger.info(f"📁 Checking log directory: {log_dir}")
    
    if log_dir.exists():
        log_files = list(log_dir.glob('*.log'))
        logger.info(f"📄 Found {len(log_files)} log files:")
        
        for log_file in log_files:
            size = log_file.stat().st_size
            logger.info(f"   {log_file.name}: {size} bytes")
            
            # Đọc nội dung file log
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                    debug_count = sum(1 for line in lines if 'DEBUG' in line)
                    info_count = sum(1 for line in lines if 'INFO' in line)
                    
                    logger.info(f"   - DEBUG lines: {debug_count}")
                    logger.info(f"   - INFO lines: {info_count}")
                    
                    # Hiển thị 5 dòng cuối
                    last_lines = lines[-5:] if len(lines) > 5 else lines
                    logger.info("   Last 5 lines:")
                    for line in last_lines:
                        if line.strip():
                            logger.info(f"     {line.strip()}")
                            
            except Exception as e:
                logger.error(f"❌ Error reading {log_file}: {e}")
    
    logger.info("✅ Simple diagnostic test completed")

if __name__ == "__main__":
    test_logging_levels()