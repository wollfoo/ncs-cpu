#!/usr/bin/env python3
"""
🔍 **EventBus Diagnostic Script** (Script chẩn đoán EventBus)
Kiểm tra hoạt động của EventBus và xác minh các hàm có DEBUG logs có được gọi không
"""

import os
import sys
import time
import logging
from pathlib import Path

# Thêm path để import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.mining_environment.scripts.resource_manager import ResourceManager
from app.mining_environment.scripts.resource_control import MiningProcess

# ✅ **Cấu hình logging diagnostic** (Cấu hình ghi log chẩn đoán)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('eventbus_diagnostic.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_eventbus_activity():
    """✅ **Test EventBus Activity** (Kiểm tra hoạt động EventBus)"""
    logger.info("🚀 Starting EventBus diagnostic test...")
    
    # Khởi tạo ResourceManager
    manager = ResourceManager()
    
    # Tạo test process
    test_process = MiningProcess(
        pid=9999,
        name="test_process",
        priority=5,
        cpu_usage=50.0,
        memory_usage=100.0
    )
    
    logger.info(f"📊 Created test process: {test_process.name} (PID={test_process.pid})")
    
    # Test enqueue_cloaking
    logger.info("🔍 Testing enqueue_cloaking...")
    manager.enqueue_cloaking(test_process)
    
    # Đợi một chút để xử lý
    time.sleep(2)
    
    # Kiểm tra queue status
    queue_size = manager.resource_adjustment_queue.qsize()
    logger.info(f"📦 Queue size after enqueue: {queue_size}")
    
    # Kiểm tra log files
    log_files = ['cloak_strategies.log', 'resource_control.log', 'eventbus_diagnostic.log']
    for log_file in log_files:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            logger.info(f"📄 {log_file}: {size} bytes")
            
            # Đọc 10 dòng cuối
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    last_lines = lines[-10:] if len(lines) > 10 else lines
                    logger.info(f"   Last lines: {len(last_lines)}")
                    for line in last_lines:
                        logger.info(f"   {line.strip()}")
            except Exception as e:
                logger.error(f"❌ Error reading {log_file}: {e}")
    
    logger.info("✅ EventBus diagnostic test completed")

if __name__ == "__main__":
    test_eventbus_activity()