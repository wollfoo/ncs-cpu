"""
✅ UNIFIED LOGGING SYSTEM
Hệ thống quản lý [Logging] (ghi log) tập trung cho tất cả mô-đun của môi trường khai thác.
Loại bỏ [duplicate loggers] (các logger trùng lặp) và chuẩn hoá [log formatting] (định dạng log) trên toàn hệ thống.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Any
from logging.handlers import RotatingFileHandler
import sys
import time

class UnifiedLoggerManager:
    """
    ✅ CENTRALIZED: Hệ thống quản lý [Unified Logger] (logger hợp nhất) cho [consistent logging] (ghi log nhất quán).
    Một điểm kiểm soát duy nhất cho tất cả logger của mô-đun với [standardized formatting] (định dạng chuẩn hoá).
    """
    
    _instance: Optional['UnifiedLoggerManager'] = None
    _lock = threading.RLock()
    
    # ✅ STANDARDIZED: Định dạng log chung cho tất cả mô-đun
    STANDARD_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    # ✅ HIERARCHY: Cây tên [Logger] (bộ ghi log) cho [organized logging] (ghi log có tổ chức)
    LOGGER_HIERARCHY = {
        'mining_environment': {
            'level': logging.INFO,
            'file': 'mining_environment.log',
            'description': "[Main Mining Environment Logger] (bộ ghi log chính cho môi trường khai thác)"
        },
        'mining_environment.resource_manager': {
            'level': logging.INFO,
            'file': 'resource_manager.log',
            'description': "[Resource Management Operations] (các thao tác quản lý tài nguyên)"
        },
        'mining_environment.cloak_strategies': {
            # ⚙️ Nâng mức log lên DEBUG để ghi chi tiết chiến lược cloaking
            'level': logging.DEBUG,
            'file': 'cloak_strategies.log',
            'description': "[Cloaking Strategy Implementations] (các triển khai chiến lược che giấu)"
        },
        'mining_environment.cpu_cloaking': {
            # 🔧 CPU cloaking operations (Legacy external stealth only)
            'level': logging.DEBUG,
            'file': 'cpu_cloaking_manager.log',
            'description': "[CPU Cloaking Legacy Operations] (thao tác che giấu CPU kiểu cũ) và [External Stealth Attempts] (thử nghiệm che giấu bên ngoài)"
        },
        # (CPU-only) GPU cloaking logger removed
        'mining_environment.resource_control': {
            # ⚙️ Nâng mức log lên DEBUG để ghi chi tiết điều khiển tài nguyên
            'level': logging.DEBUG,
            'file': 'resource_control.log',
            'description': "[Low-level Resource Control Operations] (các thao tác điều khiển tài nguyên cấp thấp)"
        },
        'mining_environment.event_bus': {
            'level': logging.INFO,
            'file': 'event_bus.log',
            'description': "[Event Bus Communication] (giao tiếp qua bus sự kiện)"
        }
    }
    
    def __new__(cls) -> 'UnifiedLoggerManager':
        """Triển khai [Singleton Pattern] (mẫu đơn thể – đảm bảo duy nhất một thể hiện)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Khởi tạo bộ quản lý [Unified Logger] (logger hợp nhất)."""
        if getattr(self, '_initialized', False):
            return
            
        self._initialized = True
        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: Dict[str, logging.Handler] = {}
        
        # ✅ CENTRALIZED: Create centralized log directory
        try:
            self.log_dir = Path('/app/mining_environment/logs')
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to local directory if /app is not accessible
            self.log_dir = Path('./logs')
            self.log_dir.mkdir(parents=True, exist_ok=True)
            print(f"⚠️ [UnifiedLogging] Using fallback log directory: {self.log_dir.absolute()}")
        
        # ✅ SETUP: Initialize all loggers in hierarchy
        self._setup_logger_hierarchy()
        
        print(f"✅ [UnifiedLogging] Initialized {len(self._loggers)} loggers in hierarchy")
    
    def _setup_logger_hierarchy(self) -> None:
        """Thiết lập đầy đủ cây [logger hierarchy] (phân cấp logger) với cấu hình chuẩn hoá."""
        try:
            for logger_name, config in self.LOGGER_HIERARCHY.items():
                self._create_logger(
                    name=logger_name,
                    level=config['level'],
                    log_file=config['file'],
                    description=config['description']
                )
            
            # ✅ ROOT LOGGER: Thiết lập [root logger] (logger gốc) cho tình huống dự phòng
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.WARNING)  # Only critical messages to root
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Thiết lập hệ phân cấp [logger hierarchy] (cây phân cấp logger) thất bại: {e}")
            raise
    
    def _create_logger(self, name: str, level: int, log_file: str, description: str) -> logging.Logger:
        """Tạo [logger] (bộ ghi log) riêng lẻ với cấu hình chuẩn hoá."""
        try:
            logger = logging.getLogger(name)
            
            # ✅ PREVENT DUPLICATES: Clear existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            
            logger.setLevel(level)
            logger.propagate = False  # Prevent propagation to avoid duplicates
            
            # ✅ FILE HANDLER: [Rotating file handler] (bộ xử lý file xoay vòng) cho [log rotation] (xoay vòng log)
            log_path = self.log_dir / log_file
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=10*1024*1024,  # 10MB max per file
                backupCount=5,           # Keep 5 backup files
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            
            # ✅ CONSOLE HANDLER: [Console output] (xuất ra bảng điều khiển) cho các thông điệp quan trọng
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
            
            # ✅ STANDARDIZED FORMATTING: [Định dạng chuẩn hoá]
            formatter = logging.Formatter(self.STANDARD_FORMAT, self.DATE_FORMAT)
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # ✅ ADD HANDLERS: Thêm các [handler] (bộ xử lý)
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            
            # ✅ STORE REFERENCES: Lưu tham chiếu
            self._loggers[name] = logger
            self._handlers[f"{name}_file"] = file_handler
            self._handlers[f"{name}_console"] = console_handler
            
            # ✅ LOG CREATION
            logger.info(f"📋 [UnifiedLogging] [Logger] (bộ ghi **[log]** (nhật ký)) '{name}' đã khởi tạo: {description}")
            
            return logger
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Tạo [logger] (bộ ghi log) thất bại '{name}': {e}")
            raise
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        ✅ PRIMARY METHOD: Lấy [logger] (bộ ghi log) theo tên từ cây hợp nhất.
        
        :param name: Tên [Logger] (có thể là tên đầy đủ theo phân cấp hoặc tên mô-đun)
        :return: Thể hiện [logger] (bộ ghi log) đã được cấu hình
        """
        try:
            # ✅ DIRECT MATCH: Check if exact name exists
            if name in self._loggers:
                return self._loggers[name]
            
            # ✅ HIERARCHY MATCH: Try to find in hierarchy
            full_name = f"mining_environment.{name}"
            if full_name in self._loggers:
                return self._loggers[full_name]
            
            # ✅ FALLBACK: Create ad-hoc logger if not in hierarchy
            return self._create_adhoc_logger(name)
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Lỗi khi lấy [logger] (bộ ghi log) '{name}': {e}")
            # ✅ SAFETY FALLBACK: Return basic logger
            return logging.getLogger(name)
    
    def _create_adhoc_logger(self, name: str) -> logging.Logger:
        """Tạo [ad-hoc logger] (logger tuỳ biến tức thời) cho mô-đun không nằm trong phân cấp định nghĩa trước."""
        try:
            logger_name = f"mining_environment.{name}" if not name.startswith('mining_environment') else name
            
            return self._create_logger(
                name=logger_name,
                level=logging.INFO,
                log_file=f"{name.replace('.', '_')}.log",
                description=f"[Ad-hoc Logger] (logger tuỳ biến tức thời) cho {name}"
            )
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Tạo [ad-hoc logger] (logger tuỳ biến tức thời) thất bại '{name}': {e}")
            return logging.getLogger(name)
    
    def get_logging_status(self) -> Dict[str, Any]:
        """
        ✅ MONITORING: Lấy trạng thái toàn diện của hệ thống [logging] (ghi log).
        
        :return: Từ điển chứa các chỉ số hệ thống ghi log
        """
        try:
            status = {
                'timestamp': time.time(),
                'total_loggers': len(self._loggers),
                'total_handlers': len(self._handlers),
                'log_directory': str(self.log_dir),
                'loggers': {},
                'disk_usage': {}
            }
            
            # ✅ LOGGER DETAILS: Thông tin chi tiết các [logger]
            for name, logger in self._loggers.items():
                status['loggers'][name] = {
                    'level': logging.getLevelName(logger.level),
                    'handlers': len(logger.handlers),
                    'propagate': logger.propagate
                }
            
            # ✅ DISK USAGE: Mức sử dụng đĩa
            try:
                for log_file in self.log_dir.glob('*.log'):
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    status['disk_usage'][log_file.name] = f"{size_mb:.2f} MB"
            except Exception:
                status['disk_usage'] = "Unable to calculate"
            
            return status
            
        except Exception as e:
            return {'error': f"Lấy [logging status] (trạng thái hệ thống ghi log) thất bại: {e}"}
    
    def cleanup_old_logs(self, days_to_keep: int = 7) -> int:
        """
        ✅ MAINTENANCE: Dọn dẹp các tệp log cũ để quản lý dung lượng đĩa.
        
        :param days_to_keep: Số ngày giữ lại tệp log
        :return: Số tệp đã được dọn dẹp
        """
        try:
            import time
            import os
            
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            cleaned_count = 0
            
            for log_file in self.log_dir.glob('*.log*'):
                try:
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        cleaned_count += 1
                except Exception:
                    continue  # Skip files that can't be deleted
            
            if cleaned_count > 0:
                # Ghi vào [main logger] (logger chính)
                main_logger = self.get_logger('mining_environment')
                main_logger.info(f"🧹 [UnifiedLogging] Đã dọn {cleaned_count} tệp **[log]** (nhật ký) cũ")
            
            return cleaned_count
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Log cleanup failed: {e}")
            return 0

# ✅ GLOBAL INSTANCE: Create global unified logger manager instance
_unified_manager = UnifiedLoggerManager()

def get_unified_logger(name: str) -> logging.Logger:
    """
    ✅ CONVENIENCE FUNCTION: Get unified logger instance.
    
    :param name: Module name (e.g., 'resource_manager', 'cloak_strategies')
    :return: Configured logger from unified hierarchy
    """
    return _unified_manager.get_logger(name)

def get_logging_status() -> Dict[str, Any]:
    """
    ✅ CONVENIENCE FUNCTION: Get logging system status.
    
    :return: Logging system metrics and status
    """
    return _unified_manager.get_logging_status()

def cleanup_logs(days_to_keep: int = 7) -> int:
    """
    ✅ CONVENIENCE FUNCTION: Clean up old log files.
    
    :param days_to_keep: Days to keep log files (default: 7)
    :return: Number of files cleaned up
    """
    return _unified_manager.cleanup_old_logs(days_to_keep)