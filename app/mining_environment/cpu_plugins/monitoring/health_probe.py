"""cpu_plugins.monitoring.health_probe

Hệ thống kiểm tra sức khỏe cho CPU Plugins.
Giám sát trạng thái hoạt động và cảnh báo khi có vấn đề.
"""
from __future__ import annotations

import time
import psutil
import logging
import threading
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from ..core.registry import PluginRegistry


class HealthStatus(Enum):
    """Trạng thái sức khỏe của plugin."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Kết quả kiểm tra sức khỏe."""
    plugin_name: str
    status: HealthStatus
    timestamp: datetime
    metrics: Dict[str, Any]
    errors: List[str]
    message: str


class PluginHealthProbe:
    """
    Health Probe - Đầu dò kiểm tra sức khỏe plugin.
    
    Giám sát CPU usage, memory, thread status và error rate của các plugin.
    Cung cấp cơ chế kiểm tra sức khỏe liên tục và báo cáo trạng thái.
    """
    
    def __init__(self, 
                 registry: Optional[PluginRegistry] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Khởi tạo health probe.
        
        Args:
            registry: Plugin registry để quản lý plugin
            logger: Logger tùy chọn
        """
        self.registry = registry or PluginRegistry.get_instance()
        self.logger = logger or logging.getLogger(__name__)
        self.health_checks: Dict[str, Dict[str, Any]] = {}
        self.check_interval = 30  # seconds
        self._running = False
        self._health_thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=5)
        
        # Ngưỡng cảnh báo
        self.thresholds = {
            'cpu_percent': 80,      # CPU usage > 80% = warning
            'memory_mb': 500,       # Memory > 500MB = warning
            'error_rate': 0.05,     # Error rate > 5% = critical
            'response_time': 5.0    # Response time > 5s = degraded
        }
        
        self.logger.info("PluginHealthProbe đã khởi tạo")
    
    def register_plugin(self, plugin_name: str, plugin_instance: Any) -> None:
        """
        Đăng ký plugin để giám sát.
        
        Args:
            plugin_name: Tên plugin
            plugin_instance: Instance của plugin
        """
        self.health_checks[plugin_name] = {
            'instance': plugin_instance,
            'last_check': None,
            'consecutive_failures': 0,
            'total_checks': 0,
            'failed_checks': 0
        }
        self.logger.info(f"Đã đăng ký health check cho plugin: {plugin_name}")
    
    def check_plugin_health(self, plugin_name: str) -> HealthCheckResult:
        """
        Kiểm tra sức khỏe của một plugin cụ thể.
        
        Args:
            plugin_name: Tên plugin cần kiểm tra
            
        Returns:
            Kết quả kiểm tra sức khỏe
        """
        if plugin_name not in self.health_checks:
            return HealthCheckResult(
                plugin_name=plugin_name,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                metrics={},
                errors=["Plugin chưa được đăng ký"],
                message="Plugin không được đăng ký để kiểm tra sức khỏe"
            )
        
        plugin_info = self.health_checks[plugin_name]
        plugin_instance = plugin_info['instance']
        
        metrics: Dict[str, Any] = {}
        errors: List[str] = []
        status = HealthStatus.HEALTHY
        
        try:
            # 1. Kiểm tra CPU usage của plugin
            if hasattr(plugin_instance, '_tracked_pids'):
                tracked_pids = getattr(plugin_instance, '_tracked_pids', set())
                cpu_usage = self._get_pids_cpu_usage(tracked_pids)
                metrics['cpu_percent'] = cpu_usage
                if cpu_usage > self.thresholds['cpu_percent']:
                    status = HealthStatus.DEGRADED
                    errors.append(f"CPU usage cao: {cpu_usage:.1f}%")
            
            # 2. Kiểm tra memory usage
            if hasattr(plugin_instance, '_tracked_pids'):
                tracked_pids = getattr(plugin_instance, '_tracked_pids', set())
                memory_mb = self._get_pids_memory_usage(tracked_pids)
                metrics['memory_mb'] = memory_mb
                if memory_mb > self.thresholds['memory_mb']:
                    status = HealthStatus.DEGRADED
                    errors.append(f"Memory usage cao: {memory_mb:.1f}MB")
            
            # 3. Kiểm tra response time
            start_time = time.time()
            if hasattr(plugin_instance, 'health_check'):
                # Nếu plugin có method health_check riêng
                plugin_instance.health_check()
            response_time = time.time() - start_time
            metrics['response_time'] = response_time
            
            if response_time > self.thresholds['response_time']:
                status = HealthStatus.DEGRADED
                errors.append(f"Response time chậm: {response_time:.2f}s")
            
            # 4. Kiểm tra error rate
            plugin_info['total_checks'] += 1
            error_rate = plugin_info['failed_checks'] / max(1, plugin_info['total_checks'])
            metrics['error_rate'] = error_rate
            
            if error_rate > self.thresholds['error_rate']:
                status = HealthStatus.CRITICAL
                errors.append(f"Error rate cao: {error_rate*100:.1f}%")
            
            # 5. Plugin-specific checks
            if hasattr(plugin_instance, 'get_health_metrics'):
                custom_metrics = plugin_instance.get_health_metrics()
                metrics.update(custom_metrics)
            
            # Reset consecutive failures nếu healthy
            if status == HealthStatus.HEALTHY:
                plugin_info['consecutive_failures'] = 0
            
        except Exception as e:
            status = HealthStatus.CRITICAL
            errors.append(f"Exception trong quá trình kiểm tra sức khỏe: {str(e)}")
            plugin_info['failed_checks'] += 1
            plugin_info['consecutive_failures'] += 1
            
            # Nếu fail liên tục 3 lần -> CRITICAL
            if plugin_info['consecutive_failures'] >= 3:
                status = HealthStatus.CRITICAL
        
        # Xác định message tổng quan
        if status == HealthStatus.HEALTHY:
            message = f"{plugin_name} hoạt động bình thường"
        elif status == HealthStatus.DEGRADED:
            message = f"{plugin_name} có hiệu suất giảm sút"
        else:
            message = f"{plugin_name} gặp sự cố nghiêm trọng"
        
        result = HealthCheckResult(
            plugin_name=plugin_name,
            status=status,
            timestamp=datetime.now(),
            metrics=metrics,
            errors=errors,
            message=message
        )
        
        plugin_info['last_check'] = result
        return result
    
    def _get_pids_cpu_usage(self, pids: Set[int]) -> float:
        """
        Lấy tổng CPU usage của các PIDs.
        
        Args:
            pids: Set các process IDs cần kiểm tra
            
        Returns:
            Tổng CPU usage (%)
        """
        total_cpu = 0.0
        for pid in pids:
            try:
                process = psutil.Process(pid)
                total_cpu += process.cpu_percent(interval=0.1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return total_cpu
    
    def _get_pids_memory_usage(self, pids: Set[int]) -> float:
        """
        Lấy tổng memory usage của các PIDs (MB).
        
        Args:
            pids: Set các process IDs cần kiểm tra
            
        Returns:
            Tổng memory usage (MB)
        """
        total_memory = 0.0
        for pid in pids:
            try:
                process = psutil.Process(pid)
                total_memory += process.memory_info().rss / 1024 / 1024
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return total_memory
    
    def check_all_plugins(self) -> Dict[str, HealthCheckResult]:
        """
        Kiểm tra sức khỏe của tất cả plugins.
        
        Returns:
            Dictionary kết quả kiểm tra theo tên plugin
        """
        results = {}
        
        # Chạy parallel health checks
        futures = {}
        for plugin_name in self.health_checks:
            future = self._executor.submit(self.check_plugin_health, plugin_name)
            futures[plugin_name] = future
        
        # Thu thập kết quả
        for plugin_name, future in futures.items():
            try:
                results[plugin_name] = future.result(timeout=10)
            except Exception as e:
                self.logger.error(f"Health check cho {plugin_name} thất bại: {e}")
                results[plugin_name] = HealthCheckResult(
                    plugin_name=plugin_name,
                    status=HealthStatus.CRITICAL,
                    timestamp=datetime.now(),
                    metrics={},
                    errors=[f"Health check timeout: {str(e)}"],
                    message=f"Health check cho {plugin_name} thất bại"
                )
        
        return results
    
    def start_continuous_monitoring(self, callback: Optional[callable] = None) -> None:
        """
        Bắt đầu giám sát liên tục.
        
        Args:
            callback: Hàm callback được gọi sau mỗi lần kiểm tra
        """
        if self._running:
            return
        
        self._running = True
        
        def monitor_loop() -> None:
            """Vòng lặp giám sát."""
            while self._running:
                try:
                    # Kiểm tra tất cả plugins
                    results = self.check_all_plugins()
                    
                    # Ghi log các plugin không healthy
                    for plugin_name, result in results.items():
                        if result.status != HealthStatus.HEALTHY:
                            self.logger.warning(
                                f"Plugin {plugin_name} không healthy: {result.status.value} - {result.message}"
                            )
                    
                    # Gọi callback nếu có
                    if callback:
                        try:
                            callback(results)
                        except Exception as e:
                            self.logger.error(f"Lỗi trong health check callback: {e}")
                    
                    # Sleep đến lần check tiếp theo
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Lỗi trong vòng lặp giám sát: {e}")
                    time.sleep(self.check_interval)
        
        self._health_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._health_thread.start()
        self.logger.info("Đã bắt đầu giám sát liên tục")
    
    def stop_monitoring(self) -> None:
        """Dừng giám sát liên tục."""
        self._running = False
        if self._health_thread:
            self._health_thread.join(timeout=5)
        self.logger.info("Đã dừng giám sát liên tục")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Lấy tóm tắt sức khỏe của tất cả plugins.
        
        Returns:
            Tóm tắt sức khỏe
        """
        summary = {
            'timestamp': datetime.now(),
            'total_plugins': len(self.health_checks),
            'healthy_count': 0,
            'degraded_count': 0,
            'critical_count': 0,
            'unknown_count': 0,
            'plugins': {}
        }
        
        for plugin_name, info in self.health_checks.items():
            last_check = info.get('last_check')
            if not last_check:
                summary['unknown_count'] += 1
                continue
                
            status = last_check.status
            if status == HealthStatus.HEALTHY:
                summary['healthy_count'] += 1
            elif status == HealthStatus.DEGRADED:
                summary['degraded_count'] += 1
            elif status == HealthStatus.CRITICAL:
                summary['critical_count'] += 1
            else:
                summary['unknown_count'] += 1
            
            summary['plugins'][plugin_name] = {
                'status': status.value,
                'last_check': last_check.timestamp,
                'message': last_check.message,
                'errors': last_check.errors
            }
        
        return summary 