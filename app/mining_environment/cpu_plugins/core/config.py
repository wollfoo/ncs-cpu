"""cpu_plugins.core.config

Pydantic model & helper để tải cấu hình từ cpu_plugins.yml.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml
from pydantic import BaseModel, validator


class PluginCfg(BaseModel):
    """Cấu hình cho một plugin."""
    name: str
    enabled: bool = True
    priority: int = 50
    module: Optional[str] = None
    config: Dict[str, Any] = {}

    @validator("priority")
    def _prio_range(cls, v: int):  # noqa: N805
        """Xác thực giá trị priority nằm trong khoảng 0-100."""
        if not 0 <= v <= 100:
            raise ValueError("priority phải nằm trong khoảng 0-100")
        return v


class MonitoringCfg(BaseModel):
    """Cấu hình cho hệ thống giám sát."""
    enabled: bool = True
    check_interval: int = 30


class WatchdogCfg(BaseModel):
    """Cấu hình cho watchdog."""
    enabled: bool = True
    auto_restart: bool = True
    restart_cooldown_minutes: int = 5
    max_restart_attempts: int = 3


class PrometheusCfg(BaseModel):
    """Cấu hình cho Prometheus exporter."""
    enabled: bool = True
    port: int = 9090


class MonitoringConfig(BaseModel):
    """Cấu hình tổng thể cho monitoring."""
    health_probe: MonitoringCfg = MonitoringCfg()
    watchdog: WatchdogCfg = WatchdogCfg()
    prometheus: PrometheusCfg = PrometheusCfg()


class CpuPluginFile(BaseModel):
    """Cấu trúc tệp cấu hình CPU plugin."""
    plugins: List[PluginCfg] = []
    monitoring: Optional[MonitoringConfig] = None


# ---------------------------------------------------------------------------
# Loader helper
# ---------------------------------------------------------------------------

def load_plugin_cfg(path: Path) -> CpuPluginFile:
    """
    Đọc tệp YAML và trả về model đã được xác thực.

    Args:
        path: Đường dẫn đến tệp cấu hình

    Returns:
        CpuPluginFile: Cấu hình đã được xác thực
        
    Notes:
        Nếu tệp không tồn tại => trả về cấu hình rỗng (tất cả plugin được kích hoạt mặc định).
    """
    if not path.exists():
        return CpuPluginFile()
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raw = {}
    return CpuPluginFile(**raw) 


# ---------------------------------------------------------------------------
# Backward-compatibility aliases (v0.x → v1.x)
# ---------------------------------------------------------------------------

# Một số module cũ vẫn kỳ vọng tên `PluginConfig`, `CpuPluginConfig` và
# hàm `load_plugin_config`. Chúng ta tạo alias để tránh ImportError.

PluginConfig = PluginCfg  # giữ nguyên cấu trúc
CpuPluginConfig = CpuPluginFile  # alias cho tệp cấu hình tổng


def load_plugin_config(path: Path) -> CpuPluginConfig:  # type: ignore[valid-type]
    """Alias cho hàm load_plugin_cfg cũ nhằm tương thích ngược."""
    return load_plugin_cfg(path) 