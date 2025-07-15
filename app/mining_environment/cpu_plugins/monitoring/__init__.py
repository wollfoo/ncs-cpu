"""
Package monitoring - Giám sát và quản lý tài nguyên hệ thống.

Module này chứa các công cụ để giám sát sức khỏe hệ thống, xuất telemetry 
và phát hiện các công cụ giám sát bên ngoài.
"""

from typing import Dict, Any

# Khởi tạo version
__version__ = "1.0.0"

# Xuất các module chính
try:
    from .health_probe import HealthProbe
except ImportError:
    # Fallback nếu module chưa tồn tại
    HealthProbe = None

try:
    from .watchdog import SystemWatchdog
except ImportError:
    # Fallback nếu module chưa tồn tại  
    SystemWatchdog = None

try:
    from .anti_detection import AntiDetectionSystem, create_anti_detection_system
except ImportError:
    # Fallback nếu module chưa tồn tại
    AntiDetectionSystem, create_anti_detection_system = None, None

try:  
    from .prometheus_exporter import PrometheusExporter
except ImportError:
    # Fallback nếu module chưa tồn tại
    PrometheusExporter = None


# Dictionary cấu hình mặc định cho module monitoring
DEFAULT_CONFIG: Dict[str, Any] = {
    "health_probe": {
        "enabled": True,
        "interval": 15,
        "thresholds": {
            "cpu": 95,
            "memory": 90,
            "disk": 95
        }
    },
    "anti_detection": {
        "enabled": True,
        "monitoring_interval": 30
    },
    "watchdog": {
        "enabled": True,
        "interval": 20
    },
    "prometheus": {
        "enabled": False,
        "port": 9090,
        "path": "/metrics"
    }
} 