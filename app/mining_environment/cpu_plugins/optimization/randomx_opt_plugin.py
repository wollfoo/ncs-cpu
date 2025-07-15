"""cpu_plugins.optimization.randomx_opt_plugin

Plugin tối ưu hóa RandomX, tự động áp dụng các cài đặt tối ưu cho RandomX mining.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

from ..core import ICpuTechnique, register_plugin


@register_plugin("randomx_opt")
class RandomxOptPlugin(ICpuTechnique):
    """
    Tự động áp dụng RandomX tối ưu (affinity + NUMA) cho PID miner.
    
    Sử dụng engine.apply_randomx_optimization(pid, performance_profile).
    """

    name = "randomx_opt"
    priority = 25

    def __init__(self):
        """Khởi tạo plugin."""
        self.logger = logging.getLogger(__name__)
        self.engine = None
        self._tracked_pids: Set[int] = set()
        self._profile: str = "stealth"

    def init(self, engine: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """Khởi tạo plugin với engine và cấu hình."""
        self.engine = engine
        
        if config and isinstance(config.get("profile"), str):
            self._profile = str(config["profile"])
            
        self.logger.info(f"RandomX optimization plugin đã sẵn sàng, profile={self._profile}")
        return True

    def apply(self, pid: int) -> bool:
        """Áp dụng tối ưu RandomX cho một PID cụ thể."""
        if not self.engine:
            return False
            
        self._tracked_pids.add(pid)
        
        try:
            if hasattr(self.engine, "apply_randomx_optimization"):
                self.engine.apply_randomx_optimization(pid, self._profile)
                self.logger.debug(f"Đã áp dụng tối ưu RandomX cho PID={pid} với profile={self._profile}")
                return True
            else:
                self.logger.warning("Engine không hỗ trợ apply_randomx_optimization")
                return False
        except Exception as exc:
            self.logger.error(f"Không thể áp dụng tối ưu RandomX cho PID={pid}: {exc}")
            return False

    def stop(self) -> bool:
        """Dừng plugin và giải phóng tài nguyên."""
        self.logger.info("RandomX optimization plugin đã dừng - không cần dọn dẹp")
        return True 