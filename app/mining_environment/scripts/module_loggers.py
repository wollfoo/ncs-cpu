# module_loggers.py

"""
**Module Loggers Configuration** (Cấu hình Logger Mô-đun)

Tạo và quản lý **dedicated loggers** (logger chuyên dụng) cho các **mining modules** (mô-đun khai thác)
và **plugin systems** (hệ thống plugin).
"""

import os
from pathlib import Path
from mining_environment.scripts.logging_config import setup_logging

# **Log directory setup** (thiết lập thư mục log)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)

# **Dedicated Module Loggers** (Logger mô-đun chuyên dụng)
cpu_plugin_logger = setup_logging('cpu_plugin', str(Path(LOGS_DIR) / 'cpu_plugin.log'), 'INFO')
# (ĐÃ GỠ) GPU plugin logger không còn cần trong bản CPU-only
gpu_plugin_logger = setup_logging('gpu_plugin_removed', str(Path(LOGS_DIR) / 'gpu_plugin_removed.log'), 'INFO')

def get_cpu_plugin_logger():
    """
    **Get CPU plugin logger** (Lấy logger plugin CPU) - Dedicated logger cho **CPU plugin operations** (hoạt động plugin CPU).
    
    Returns:
        Logger: CPU plugin logger instance
    """
    return cpu_plugin_logger

def get_gpu_plugin_logger():
    """
    **Get GPU plugin logger** (đã gỡ GPU) – trả về logger vô hại để tương thích.
    
    Returns:
        Logger: GPU plugin logger instance
    """
    return gpu_plugin_logger

def initialize_plugin_logging():
    """
    **Initialize plugin logging system** (Khởi tạo hệ thống ghi log plugin).
    Tạo **initial log entries** (mục log ban đầu) trong các **plugin log files** (tệp log plugin).
    """
    # **CPU Plugin Logging Initialization** (Khởi tạo ghi log plugin CPU)
    cpu_plugin_logger.info("===== CPU PLUGIN LOGGING SYSTEM STARTED =====")
    cpu_plugin_logger.info("CPU Plugin Logger initialized and ready")
    cpu_plugin_logger.info("Available for logging CPU plugin operations")
    cpu_plugin_logger.info("============================================")
    
    # (ĐÃ GỠ) GPU Plugin Logging Initialization – giữ chỗ an toàn
    gpu_plugin_logger.info("===== GPU PLUGIN LOGGING REMOVED (CPU-ONLY) =====")

def log_cpu_plugin_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log CPU plugin operation** (Ghi log hoạt động plugin CPU).
    
    Args:
        operation (str): **Operation name** (tên hoạt động) 
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(cpu_plugin_logger, level.lower(), cpu_plugin_logger.info)
    log_method(f"🔧 CPU Plugin - {operation}: {details}")

def log_gpu_plugin_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log GPU plugin operation** (đã gỡ GPU) – no-op logging để tương thích.
    
    Args:
        operation (str): **Operation name** (tên hoạt động)
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(gpu_plugin_logger, level.lower(), gpu_plugin_logger.info)
    log_method(f"(GPU-REMOVED) {operation}: {details}")

# **Auto-initialize** (tự động khởi tạo) khi module được import
initialize_plugin_logging()