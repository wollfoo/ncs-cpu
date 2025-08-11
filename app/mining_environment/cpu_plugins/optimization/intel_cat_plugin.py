"""cpu_plugins.optimization.intel_cat_plugin

Plugin điều khiển Intel Cache Allocation Technology (CAT).
Tự động kiểm tra hỗ trợ và fallback nếu phần cứng không hỗ trợ.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..core.interfaces import ICpuTechnique, ProcessInfo

RESCTRL_PATH = Path("/sys/fs/resctrl")

class IntelCatPlugin(ICpuTechnique):
    """
    Plugin tối ưu hóa bộ nhớ đệm L3 (Last Level Cache) bằng Intel RDT CAT.
    Tự động tạo resource groups và hạn chế PID được phân bổ bao nhiêu phần trăm L3 cache.
    """
    
    name = "intel_cat"
    priority = 20
    
    def __init__(self, resource_manager: Any, logger: Optional[logging.Logger] = None, config: Dict[str, Any] = None):
        self.resource_manager = resource_manager
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.llc_percent = self.config.get('llc_percent', 25)  # Mặc định 25% LLC
        self.auto_disable = self.config.get('auto_disable_if_unsupported', True)
        
        # Khởi tạo RDT CAT manager
        try:
            from ..rdt_cache_control.manager import RdtCatManager
            self.rdt_manager = RdtCatManager(logger=self.logger, min_pct=self.llc_percent)
            self.is_supported = self.rdt_manager.is_active()
        except Exception as e:
            self.logger.warning(f"[RDT CAT] Không thể khởi tạo RDT CAT: {e}")
            self.rdt_manager = None
            self.is_supported = False
        
        # Tự động vô hiệu hóa nếu không được hỗ trợ
        if not self.is_supported and self.auto_disable:
            self.logger.warning("[RDT CAT] Phần cứng/kernel không hỗ trợ RDT CAT, plugin bị vô hiệu hóa")
            self.enabled = False
    
    def is_available(self) -> bool:
        return self.enabled and self.is_supported
    
    def apply(self, process_info: ProcessInfo) -> bool:
        """Áp dụng Intel CAT cho process đang chạy"""
        if not self.is_available():
            self.logger.debug(f"[RDT CAT] Plugin không khả dụng cho **[PID]** (Process ID - mã định danh tiến trình)={process_info.pid}")
            return False
        
        try:
            # Đặt % L3 cache cho process
            self.rdt_manager.set_cache_pct(process_info.pid, self.llc_percent)
            self.logger.info(f"[RDT CAT] Đã cấp {self.llc_percent}% L3 **[cache]** (bộ nhớ đệm) cho **[PID]** (Process ID - mã định danh tiến trình)={process_info.pid}")
            return True
        except Exception as e:
            self.logger.error(f"[RDT CAT] Lỗi khi áp dụng CAT cho **[PID]** (Process ID - mã định danh tiến trình)={process_info.pid}: {e}")
            return False
    
    def revert(self, process_info: ProcessInfo) -> bool:
        """Loại bỏ giới hạn cache cho process"""
        if not self.is_available() or not self.rdt_manager:
            return False
        
        # Không cần làm gì đặc biệt, nhóm sẽ tự xóa khi process kết thúc
        return True
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Trả về metrics về trạng thái của plugin"""
        return {
            "enabled": self.enabled,
            "supported": self.is_supported,
            "llc_percent": self.llc_percent,
            "resctrl_mounted": RESCTRL_PATH.exists() and (RESCTRL_PATH / "info" / "L3").exists()
        }
    
    def get_configuration(self) -> Dict[str, Any]:
        """Trả về cấu hình hiện tại của plugin"""
        return {
            "enabled": self.enabled,
            "llc_percent": self.llc_percent,
            "auto_disable_if_unsupported": self.auto_disable
        } 