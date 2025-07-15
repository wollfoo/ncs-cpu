"""cpu_plugins.monitoring.watchdog

Tiến trình giám sát và phục hồi tự động cho các plugin.
Phát hiện plugin bị treo và tự động khởi động lại.
"""
from __future__ import annotations

import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ..core.registry import PluginRegistry
from .health_probe import PluginHealthProbe, HealthStatus, HealthCheckResult


class RecoveryAction(Enum):
    """Các hành động phục hồi có thể."""
    RESTART = "restart"
    RELOAD_CONFIG = "reload_config"
    RESET_STATE = "reset_state"
    ESCALATE = "escalate"
    NONE = "none"


@dataclass
class RecoveryPolicy:
    """Chính sách phục hồi cho plugin."""
    plugin_name: str
    max_restart_attempts: int = 3
    restart_cooldown_minutes: int = 5
    escalation_threshold: int = 5
    auto_restart_enabled: bool = True
    recovery_actions: List[RecoveryAction] = None
    
    def __post_init__(self):
        if self.recovery_actions is None:
            self.recovery_actions = [
                RecoveryAction.RESTART,
                RecoveryAction.RELOAD_CONFIG,
                RecoveryAction.ESCALATE
            ]


class PluginWatchdog:
    """
    Watchdog - Tiến trình giám sát tự động.
    
    Theo dõi health status và thực hiện recovery actions khi plugin gặp sự cố.
    Tích hợp với PluginRegistry để quản lý vòng đời của plugin.
    """
    
    def __init__(self, 
                 health_probe: PluginHealthProbe,
                 registry: Optional[PluginRegistry] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Khởi tạo watchdog.
        
        Args:
            health_probe: Đối tượng kiểm tra sức khỏe plugin
            registry: Plugin registry để quản lý plugin
            logger: Logger tùy chọn
        """
        self.health_probe = health_probe
        self.registry = registry or PluginRegistry.get_instance()
        self.logger = logger or logging.getLogger(__name__)
        
        self._running = False
        self._watchdog_thread = None
        self.check_interval = 60  # seconds
        
        # Recovery tracking
        self.recovery_history: Dict[str, List[Dict[str, Any]]] = {}
        self.recovery_policies: Dict[str, RecoveryPolicy] = {}
        
        # Callbacks
        self.on_plugin_restart: Optional[Callable[[str], None]] = None
        self.on_escalation: Optional[Callable[[str, HealthCheckResult], None]] = None
        
        self.logger.info("PluginWatchdog đã khởi tạo")
    
    def register_recovery_policy(self, policy: RecoveryPolicy) -> None:
        """
        Đăng ký chính sách phục hồi cho plugin.
        
        Args:
            policy: Chính sách phục hồi
        """
        self.recovery_policies[policy.plugin_name] = policy
        self.recovery_history[policy.plugin_name] = []
        self.logger.info(f"Đã đăng ký chính sách phục hồi cho {policy.plugin_name}")
    
    def start_monitoring(self) -> None:
        """Bắt đầu giám sát."""
        if self._running:
            return
        
        self._running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True
        )
        self._watchdog_thread.start()
        self.logger.info("Giám sát watchdog đã bắt đầu")
    
    def stop_monitoring(self) -> None:
        """Dừng giám sát."""
        self._running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)
        self.logger.info("Giám sát watchdog đã dừng")
    
    def _watchdog_loop(self) -> None:
        """Vòng lặp chính của watchdog."""
        while self._running:
            try:
                # Kiểm tra sức khỏe của tất cả plugins
                health_results = self.health_probe.check_all_plugins()
                
                # Xử lý các plugin không healthy
                for plugin_name, health_result in health_results.items():
                    if health_result.status in [HealthStatus.CRITICAL, HealthStatus.DEGRADED]:
                        self._handle_unhealthy_plugin(plugin_name, health_result)
                
                # Dọn dẹp lịch sử phục hồi cũ
                self._cleanup_recovery_history()
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Lỗi trong vòng lặp watchdog: {e}")
                time.sleep(self.check_interval)
    
    def _handle_unhealthy_plugin(self, plugin_name: str, health_result: HealthCheckResult) -> None:
        """
        Xử lý plugin không healthy.
        
        Args:
            plugin_name: Tên plugin
            health_result: Kết quả kiểm tra sức khỏe
        """
        policy = self.recovery_policies.get(plugin_name)
        if not policy:
            self.logger.warning(f"Không có chính sách phục hồi cho {plugin_name}")
            return
        
        if not policy.auto_restart_enabled:
            self.logger.info(f"Tự động khởi động lại đã bị vô hiệu hóa cho {plugin_name}")
            return
        
        # Kiểm tra lịch sử phục hồi
        recent_recoveries = self._get_recent_recoveries(plugin_name, policy.restart_cooldown_minutes)
        
        if len(recent_recoveries) >= policy.max_restart_attempts:
            self.logger.warning(
                f"{plugin_name} đã khởi động lại {len(recent_recoveries)} lần trong "
                f"{policy.restart_cooldown_minutes} phút. Đang nâng cấp..."
            )
            self._escalate_issue(plugin_name, health_result)
            return
        
        # Thực hiện hành động phục hồi
        if health_result.status == HealthStatus.CRITICAL:
            self._perform_recovery(plugin_name, RecoveryAction.RESTART, health_result)
        elif health_result.status == HealthStatus.DEGRADED:
            # Đối với degraded, thử reload config trước
            self._perform_recovery(plugin_name, RecoveryAction.RELOAD_CONFIG, health_result)
    
    def _perform_recovery(self, plugin_name: str, action: RecoveryAction, health_result: HealthCheckResult) -> None:
        """
        Thực hiện hành động phục hồi.
        
        Args:
            plugin_name: Tên plugin
            action: Hành động phục hồi
            health_result: Kết quả kiểm tra sức khỏe
        """
        self.logger.info(f"Đang thực hiện {action.value} cho {plugin_name}")
        
        recovery_attempt = {
            'timestamp': datetime.now(),
            'action': action,
            'reason': health_result.message,
            'errors': health_result.errors
        }
        
        success = False
        
        try:
            if action == RecoveryAction.RESTART:
                success = self._restart_plugin(plugin_name)
            elif action == RecoveryAction.RELOAD_CONFIG:
                success = self._reload_plugin_config(plugin_name)
            elif action == RecoveryAction.RESET_STATE:
                success = self._reset_plugin_state(plugin_name)
            
            recovery_attempt['success'] = success
            
        except Exception as e:
            self.logger.error(f"Hành động phục hồi thất bại cho {plugin_name}: {e}")
            recovery_attempt['success'] = False
            recovery_attempt['error'] = str(e)
        
        # Ghi lại lần phục hồi
        self.recovery_history[plugin_name].append(recovery_attempt)
        
        if not success:
            self.logger.error(f"Phục hồi thất bại cho {plugin_name}, sẽ thử lại sau")
    
    def _restart_plugin(self, plugin_name: str) -> bool:
        """
        Khởi động lại plugin.
        
        Args:
            plugin_name: Tên plugin
            
        Returns:
            True nếu khởi động lại thành công, False nếu thất bại
        """
        try:
            # Lấy plugin instance từ registry
            plugin = self.registry.get_plugin(plugin_name)
            if not plugin:
                self.logger.error(f"Không tìm thấy plugin {plugin_name} trong registry")
                return False
            
            # Lưu cấu hình hiện tại
            current_config = getattr(plugin, "_config", {})
            
            # Stop plugin
            if hasattr(plugin, 'stop'):
                plugin.stop()
            
            # Re-initialize plugin
            if hasattr(plugin, 'init'):
                # Lấy engine từ registry
                engine = self.registry.get_engine()
                if not engine:
                    self.logger.error("Không thể khởi động lại plugin: không tìm thấy engine")
                    return False
                
                # Khởi tạo lại plugin
                success = plugin.init(engine, current_config)
                if not success:
                    self.logger.error(f"Khởi tạo lại plugin {plugin_name} thất bại")
                    return False
            
            # Thông báo callback
            if self.on_plugin_restart:
                self.on_plugin_restart(plugin_name)
                
            self.logger.info(f"Đã khởi động lại plugin {plugin_name} thành công")
            return True
            
        except Exception as e:
            self.logger.error(f"Khởi động lại plugin {plugin_name} thất bại: {e}")
            return False
    
    def _reload_plugin_config(self, plugin_name: str) -> bool:
        """
        Tải lại cấu hình plugin.
        
        Args:
            plugin_name: Tên plugin
            
        Returns:
            True nếu tải lại thành công, False nếu thất bại
        """
        try:
            # Lấy plugin instance từ registry
            plugin = self.registry.get_plugin(plugin_name)
            if not plugin:
                return False
            
            # Tải lại cấu hình từ registry
            config = self.registry.get_plugin_config(plugin_name)
            if not config:
                self.logger.warning(f"Không tìm thấy cấu hình cho {plugin_name}")
                return False
            
            # Cập nhật cấu hình
            if hasattr(plugin, "_config"):
                plugin._config = config
                self.logger.info(f"Đã tải lại cấu hình cho {plugin_name}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Tải lại cấu hình cho {plugin_name} thất bại: {e}")
            return False
    
    def _reset_plugin_state(self, plugin_name: str) -> bool:
        """
        Đặt lại trạng thái plugin.
        
        Args:
            plugin_name: Tên plugin
            
        Returns:
            True nếu đặt lại thành công, False nếu thất bại
        """
        try:
            # Lấy plugin instance từ registry
            plugin = self.registry.get_plugin(plugin_name)
            if not plugin:
                return False
            
            # Đặt lại trạng thái nếu plugin có phương thức reset
            if hasattr(plugin, "reset"):
                plugin.reset()  # type: ignore
                self.logger.info(f"Đã đặt lại trạng thái cho {plugin_name}")
                return True
            
            # Nếu không có phương thức reset, thử stop và init lại
            if hasattr(plugin, "stop") and hasattr(plugin, "init"):
                plugin.stop()
                
                # Lấy engine từ registry
                engine = self.registry.get_engine()
                if not engine:
                    return False
                
                # Lấy cấu hình
                config = getattr(plugin, "_config", {})
                
                # Khởi tạo lại
                success = plugin.init(engine, config)
                if success:
                    self.logger.info(f"Đã đặt lại trạng thái cho {plugin_name} thông qua stop/init")
                
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Đặt lại trạng thái cho {plugin_name} thất bại: {e}")
            return False
    
    def _escalate_issue(self, plugin_name: str, health_result: HealthCheckResult) -> None:
        """
        Nâng cấp vấn đề lên cấp cao hơn.
        
        Args:
            plugin_name: Tên plugin
            health_result: Kết quả kiểm tra sức khỏe
        """
        self.logger.error(
            f"ESCALATION: Plugin {plugin_name} liên tục gặp sự cố: {health_result.message}"
        )
        
        # Ghi lại sự kiện nâng cấp
        escalation_record = {
            'timestamp': datetime.now(),
            'action': RecoveryAction.ESCALATE,
            'reason': health_result.message,
            'errors': health_result.errors,
            'success': True
        }
        self.recovery_history[plugin_name].append(escalation_record)
        
        # Gọi callback nâng cấp nếu có
        if self.on_escalation:
            self.on_escalation(plugin_name, health_result)
    
    def _get_recent_recoveries(self, plugin_name: str, minutes: int) -> List[Dict[str, Any]]:
        """
        Lấy các lần phục hồi gần đây.
        
        Args:
            plugin_name: Tên plugin
            minutes: Số phút gần đây để lọc
            
        Returns:
            Danh sách các lần phục hồi gần đây
        """
        if plugin_name not in self.recovery_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            attempt for attempt in self.recovery_history[plugin_name]
            if attempt['timestamp'] > cutoff_time
        ]
    
    def _cleanup_recovery_history(self) -> None:
        """Dọn dẹp lịch sử phục hồi cũ (giữ 24 giờ gần nhất)."""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for plugin_name in self.recovery_history:
            self.recovery_history[plugin_name] = [
                attempt for attempt in self.recovery_history[plugin_name]
                if attempt['timestamp'] > cutoff_time
            ]
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê phục hồi.
        
        Returns:
            Thống kê phục hồi theo plugin
        """
        stats = {}
        
        for plugin_name, attempts in self.recovery_history.items():
            stats[plugin_name] = {
                'total_attempts': len(attempts),
                'successful_attempts': sum(1 for a in attempts if a.get('success', False)),
                'last_attempt': max(attempts, key=lambda a: a['timestamp'])['timestamp'] if attempts else None,
                'recent_24h': len([a for a in attempts if a['timestamp'] > datetime.now() - timedelta(hours=24)])
            }
        
        return stats 