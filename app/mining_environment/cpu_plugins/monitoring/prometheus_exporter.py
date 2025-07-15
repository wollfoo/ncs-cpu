"""cpu_plugins.monitoring.prometheus_exporter

Module xuất dữ liệu metrics cho Prometheus.
Thu thập và cung cấp metrics về CPU usage, errors, latency cho monitoring.
"""
from __future__ import annotations

import time
import logging
import psutil
from typing import Dict, Any, Optional, Callable

from prometheus_client import Counter, Gauge, Histogram, Info  # type: ignore
from prometheus_client import start_http_server, REGISTRY  # type: ignore
from prometheus_client import CollectorRegistry  # type: ignore

from ..core.registry import PluginRegistry
from .health_probe import PluginHealthProbe, HealthStatus


# Helper tránh duplicate metric trong Registry toàn cục
def _get_metric(metric_cls, name: str, *args, **kwargs):  # type: ignore
    if name in REGISTRY._names_to_collectors:  # type: ignore[attr-defined]
        return REGISTRY._names_to_collectors[name]  # type: ignore[index]
    return metric_cls(name, *args, **kwargs)

# Định nghĩa metrics (sử dụng helper)
plugin_info = _get_metric(Info, 'cpu_plugin', 'Thông tin về CPU plugin')
plugin_status = _get_metric(Gauge, 'cpu_plugin_status', 'Trạng thái plugin (1=healthy, 2=degraded, 3=critical)', ['plugin_name'])
plugin_cpu_usage = _get_metric(Gauge, 'cpu_plugin_cpu_usage_percent', 'CPU usage percentage', ['plugin_name'])
plugin_memory_usage = _get_metric(Gauge, 'cpu_plugin_memory_usage_mb', 'Memory usage in MB', ['plugin_name'])
plugin_response_time = _get_metric(Histogram, 'cpu_plugin_response_time_seconds', 'Response time', ['plugin_name'])
plugin_error_total = _get_metric(Counter, 'cpu_plugin_errors_total', 'Tổng số lỗi', ['plugin_name'])
plugin_apply_total = _get_metric(Counter, 'cpu_plugin_apply_total', 'Tổng số lần apply', ['plugin_name'])

# System-wide metrics
system_cpu_usage = _get_metric(Gauge, 'system_cpu_usage_percent', 'System CPU usage')
system_memory_usage = _get_metric(Gauge, 'system_memory_usage_percent', 'System memory usage')
mining_hashrate = _get_metric(Gauge, 'mining_hashrate_hs', 'Mining hashrate in H/s')


class CPUPluginPrometheusExporter:
    """
    Prometheus Exporter cho CPU Plugins.
    
    Export metrics về hiệu suất, lỗi và trạng thái của các plugin.
    Tích hợp với hệ thống health monitoring để cập nhật metrics tự động.
    """
    
    def __init__(self, 
                 health_probe: PluginHealthProbe,
                 registry: Optional[PluginRegistry] = None,
                 port: int = 9090,
                 logger: Optional[logging.Logger] = None):
        """
        Khởi tạo Prometheus exporter.
        
        Args:
            health_probe: Đối tượng kiểm tra sức khỏe plugin
            registry: Plugin registry để quản lý plugin
            port: Port cho HTTP server
            logger: Logger tùy chọn
        """
        self.health_probe = health_probe
        self.registry = registry or PluginRegistry.get_instance()
        self.port = port
        self.logger = logger or logging.getLogger(__name__)
        self._metrics_server_started = False
        
        # Mapping status to numeric values
        self.status_mapping = {
            HealthStatus.HEALTHY: 1,
            HealthStatus.DEGRADED: 2,
            HealthStatus.CRITICAL: 3,
            HealthStatus.UNKNOWN: 0
        }
        
        self.logger.info(f"Prometheus Exporter khởi tạo trên port {port}")
    
    def start_metrics_server(self) -> None:
        """Khởi động HTTP server để Prometheus scrape metrics."""
        if not self._metrics_server_started:
            start_http_server(self.port)
            self._metrics_server_started = True
            self.logger.info(f"Prometheus metrics server đã khởi động trên port {self.port}")
    
    def update_metrics(self, health_results: Dict[str, Any]) -> None:
        """
        Cập nhật metrics dựa trên kết quả health check.
        
        Args:
            health_results: Kết quả kiểm tra sức khỏe từ health probe
        """
        try:
            # Cập nhật metrics cho từng plugin
            for plugin_name, result in health_results.items():
                # Status metric
                status_value = self.status_mapping.get(result.status, 0)
                plugin_status.labels(plugin_name=plugin_name).set(status_value)
                
                # CPU usage
                if 'cpu_percent' in result.metrics:
                    plugin_cpu_usage.labels(plugin_name=plugin_name).set(
                        result.metrics['cpu_percent']
                    )
                
                # Memory usage
                if 'memory_mb' in result.metrics:
                    plugin_memory_usage.labels(plugin_name=plugin_name).set(
                        result.metrics['memory_mb']
                    )
                
                # Response time
                if 'response_time' in result.metrics:
                    plugin_response_time.labels(plugin_name=plugin_name).observe(
                        result.metrics['response_time']
                    )
                
                # Error count
                if result.errors:
                    plugin_error_total.labels(plugin_name=plugin_name).inc(len(result.errors))
            
            # Cập nhật metrics toàn hệ thống
            system_cpu_usage.set(psutil.cpu_percent(interval=0.1))
            system_memory_usage.set(psutil.virtual_memory().percent)
            
            self.logger.debug("Đã cập nhật metrics thành công")
            
        except Exception as e:
            self.logger.error(f"Lỗi khi cập nhật metrics: {e}")
    
    def record_plugin_apply(self, plugin_name: str) -> None:
        """
        Ghi nhận mỗi lần plugin được apply.
        
        Args:
            plugin_name: Tên plugin
        """
        plugin_apply_total.labels(plugin_name=plugin_name).inc()
    
    def record_hashrate(self, hashrate: float) -> None:
        """
        Cập nhật hashrate metric.
        
        Args:
            hashrate: Giá trị hashrate (H/s)
        """
        mining_hashrate.set(hashrate)
    
    def get_metrics_endpoint(self) -> str:
        """
        Trả về endpoint để cấu hình trong Prometheus.
        
        Returns:
            URL endpoint cho Prometheus scrape
        """
        return f"http://localhost:{self.port}/metrics"
    
    def create_prometheus_config(self) -> Dict[str, Any]:
        """
        Tạo cấu hình mẫu cho Prometheus scrape config.
        
        Returns:
            Cấu hình Prometheus scrape
        """
        return {
            'job_name': 'cpu_plugins',
            'scrape_interval': '30s',
            'static_configs': [{
                'targets': [f'localhost:{self.port}']
            }]
        }
    
    def register_with_health_probe(self) -> None:
        """Đăng ký callback với health probe để cập nhật metrics tự động."""
        callback = self.create_metrics_callback()
        if hasattr(self.health_probe, 'start_continuous_monitoring'):
            self.health_probe.start_continuous_monitoring(callback)
            self.logger.info("Đã đăng ký metrics callback với health probe")
    
    def create_metrics_callback(self) -> Callable[[Dict[str, Any]], None]:
        """
        Tạo callback function cho health monitoring.
        
        Returns:
            Callback function để cập nhật metrics
        """
        def callback(health_results: Dict[str, Any]) -> None:
            self.update_metrics(health_results)
        return callback


# Prometheus alerting rules mẫu
PROMETHEUS_ALERT_RULES = """
groups:
  - name: cpu_plugin_alerts
    interval: 30s
    rules:
      - alert: PluginCritical
        expr: cpu_plugin_status == 3
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "CPU Plugin {{ $labels.plugin_name }} ở trạng thái CRITICAL"
          description: "Plugin {{ $labels.plugin_name }} đã ở trạng thái critical trong 2 phút"
      
      - alert: HighCPUUsage
        expr: cpu_plugin_cpu_usage_percent > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CPU usage cao cho plugin {{ $labels.plugin_name }}"
          description: "Plugin {{ $labels.plugin_name }} sử dụng {{ $value }}% CPU"
      
      - alert: HighMemoryUsage
        expr: cpu_plugin_memory_usage_mb > 600
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage cao cho plugin {{ $labels.plugin_name }}"
          description: "Plugin {{ $labels.plugin_name }} sử dụng {{ $value }}MB memory"
      
      - alert: HighErrorRate
        expr: rate(cpu_plugin_errors_total[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Error rate cao cho plugin {{ $labels.plugin_name }}"
          description: "Plugin {{ $labels.plugin_name }} có error rate {{ $value }} errors/second"
      
      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, cpu_plugin_response_time_seconds) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Response time chậm cho plugin {{ $labels.plugin_name }}"
          description: "95th percentile response time là {{ $value }}s"
"""


def save_alert_rules(filepath: str = "/etc/prometheus/cpu_plugin_alerts.yml") -> None:
    """
    Lưu alert rules vào file.
    
    Args:
        filepath: Đường dẫn file để lưu alert rules
    """
    try:
        with open(filepath, 'w') as f:
            f.write(PROMETHEUS_ALERT_RULES)
        print(f"Đã lưu alert rules vào {filepath}")
    except Exception as e:
        print(f"Lỗi khi lưu alert rules: {e}") 