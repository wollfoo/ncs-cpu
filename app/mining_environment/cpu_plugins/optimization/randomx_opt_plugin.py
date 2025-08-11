"""**[RandomX Optimization Plugin]** (plugin tối ưu hóa RandomX)

**[Plugin]** (plugin) tối ưu hóa **[RandomX]** (thuật toán RandomX), tự động áp dụng **[Optimal Settings]** (cài đặt tối ưu) cho **[RandomX Mining]** (khai thác RandomX).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

from ..core import ICpuTechnique, register_plugin


@register_plugin("randomx_opt")
class RandomxOptPlugin(ICpuTechnique):
    """
    Tự động áp dụng **[RandomX Optimization]** (tối ưu RandomX) (**[CPU Affinity]** (gắn kết CPU) + **[NUMA]** (kiến trúc bộ nhớ không đồng nhất)) cho **[PID Miner]** (PID khai thác).
    
    Sử dụng **[Engine Method]** (phương thức engine): apply_randomx_optimization(pid, performance_profile).
    """

    name = "randomx_opt"
    priority = 25

    def __init__(self):
        """Khởi tạo **[Plugin]** (plugin)."""
        self.logger = logging.getLogger(__name__)
        self.engine = None
        self._tracked_pids: Set[int] = set()
        self._profile: str = "stealth"

    def init(self, engine: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """Khởi tạo **[Plugin]** (plugin) với **[Engine]** (bộ máy) và **[Configuration]** (cấu hình)."""
        self.engine = engine
        
        if config and isinstance(config.get("profile"), str):
            self._profile = str(config["profile"])
            
        self.logger.info(f"**[RandomX Optimization Plugin]** (plugin tối ưu RandomX) đã sẵn sàng, **[Profile]** (cấu hình)={self._profile}")
        return True

    def apply(self, pid: int) -> bool:
        """Áp dụng **[RandomX Optimization]** (tối ưu RandomX) cho một **[PID]** (ID tiến trình) cụ thể."""
        if not self.engine:
            return False
            
        self._tracked_pids.add(pid)
        
        try:
            if hasattr(self.engine, "apply_randomx_optimization"):
                self.engine.apply_randomx_optimization(pid, self._profile)
                self.logger.debug(f"Đã áp dụng **[RandomX Optimization]** (tối ưu RandomX) cho **[PID]**={pid} với **[Profile]** (cấu hình)={self._profile}")
                return True
            else:
                self.logger.warning("**[Engine]** (bộ máy) không hỗ trợ **[apply_randomx_optimization]** (phương thức tối ưu RandomX)")
                return False
        except Exception as exc:
            self.logger.error(f"Không thể áp dụng **[RandomX Optimization]** (tối ưu RandomX) cho **[PID]**={pid}: {exc}")
            return False

    def stop(self) -> bool:
        """Dừng **[Plugin]** (plugin) và giải phóng **[Resources]** (tài nguyên)."""
        self.logger.info("**[RandomX Optimization Plugin]** (plugin tối ưu RandomX) đã dừng - không cần **[Cleanup]** (dọn dẹp)")
        return True 