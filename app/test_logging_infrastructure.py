#!/usr/bin/env python3
"""
Test script để kiểm tra logging infrastructure hoạt động
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

def setup_test_logger(name, log_file, level=logging.INFO):
    """Setup test logger similar to our production loggers"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        
        # Tạo log file directory
        log_file_path = Path(log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

def test_logging_infrastructure():
    """Test logging infrastructure cho mining environment"""
    print("🔍 Testing Mining Environment Logging Infrastructure...")
    
    # Container paths
    container_logs_dir = "/app/mining_environment/logs"
    local_logs_dir = "./mining_environment/logs"
    
    # Sử dụng local path nếu container path không accessible
    logs_dir = container_logs_dir if os.path.exists("/app") else local_logs_dir
    
    print(f"📁 Using logs directory: {logs_dir}")
    
    # Test 1: Cloak Strategies Logger  
    print("\n🎯 Testing Cloak Strategies Logger...")
    cloak_logger = setup_test_logger(
        'cloak_strategies',
        f'{logs_dir}/cloak_strategies.log'
    )
    
    cloak_logger.info("🎯 [CPU Strategy] Processing CPU process: ml-inference (PID=12345)")
    cloak_logger.info("📊 [CPU Strategy] Hardware classification: CPU_MINING")
    cloak_logger.info("✅ [CPU Strategy] Successfully applied CPU cloaking to ml-inference (PID=12345)")
    print("✅ Cloak strategies logging test completed")
    
    # Test 2: Resource Control Logger
    print("\n🎛️ Testing Resource Control Logger...")
    resource_logger = setup_test_logger(
        'resource_control',
        f'{logs_dir}/resource_control.log'
    )
    
    resource_logger.info("🎛️ [CPU Throttle] Starting throttling for PID=12345")
    resource_logger.info("📊 [CPU Throttle] Target throttle: 75%, cores: [0, 1, 2, 3]")
    resource_logger.info("✅ [CPU Throttle] Successfully applied throttling to PID=12345")
    print("✅ Resource control logging test completed")
    
    # Test 3: Enhanced Mining Logs
    print("\n🚀 Testing Enhanced Mining Logs...")
    mining_logger = setup_test_logger(
        'mining_enhanced',
        f'{logs_dir}/mining_operations.log'
    )
    
    mining_logger.info("📁 [Mining Log] Creating log file: /app/mining_environment/logs/cpu_miner.log")
    mining_logger.info("✅ [Mining Log] Log file initialized: /app/mining_environment/logs/cpu_miner.log")
    mining_logger.info("🚀 [Mining Log] Dual logging thread started for ml-inference")
    print("✅ Enhanced mining logging test completed")
    
    # Test 4: CPU và GPU Plugin Logs (centralized)
    print("\n🔧 Testing CPU và GPU Plugin Logs...")
    
    # CPU plugin logs tập trung trong thư mục chính
    cpu_plugin_logger = setup_test_logger(
        'cpu_plugins',
        f'{logs_dir}/cpu_plugins.log'
    )
    cpu_plugin_logger.info("🚀 [CPU Plugin] CPU optimization plugin activated for PID=12345")
    cpu_plugin_logger.info("⚡ [CPU Plugin] Applied RandomX optimization with 15% performance gain")
    cpu_plugin_logger.info("🎯 [CPU Plugin] CPU affinity set to cores [0,1,2,3] for stealth mining")
    
    # GPU plugin logs tập trung trong thư mục chính  
    gpu_plugin_logger = setup_test_logger(
        'gpu_plugins',
        f'{logs_dir}/gpu_plugins.log'
    )
    gpu_plugin_logger.info("🎮 [GPU Plugin] GPU cloaking plugin activated for PID=67890")
    gpu_plugin_logger.info("🌡️ [GPU Plugin] Thermal management applied: target=75°C, current=68°C")
    gpu_plugin_logger.info("⚡ [GPU Plugin] Power limit set to 180W for stealth operation")
    
    print("✅ CPU và GPU plugin logs test completed")
    
    # Test 5: Verify Log Files Creation
    print("\n📋 Verifying Log Files Creation...")
    expected_logs = [
        f'{logs_dir}/cloak_strategies.log',
        f'{logs_dir}/resource_control.log', 
        f'{logs_dir}/mining_operations.log',
        f'{logs_dir}/cpu_plugins.log',
        f'{logs_dir}/gpu_plugins.log'
    ]
    
    created_logs = []
    missing_logs = []
    
    for log_file in expected_logs:
        if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
            created_logs.append(log_file)
            print(f"✅ {log_file} - {os.path.getsize(log_file)} bytes")
        else:
            missing_logs.append(log_file)
            print(f"❌ {log_file} - Missing or empty")
    
    # Summary
    print(f"\n📊 LOGGING INFRASTRUCTURE TEST SUMMARY:")
    print(f"✅ Created logs: {len(created_logs)}/{len(expected_logs)}")
    print(f"❌ Missing logs: {len(missing_logs)}")
    print(f"📁 Logs directory: {logs_dir}")
    
    if missing_logs:
        print(f"\n⚠️ Missing log files:")
        for log in missing_logs:
            print(f"   - {log}")
    
    if len(created_logs) == len(expected_logs):
        print(f"\n🎉 SUCCESS: All logging infrastructure components are working correctly!")
        return True
    else:
        print(f"\n⚠️ PARTIAL: Some logging components need attention")
        return False

if __name__ == "__main__":
    success = test_logging_infrastructure()
    sys.exit(0 if success else 1)