"""cpu_plugins.core

Module cốt lõi cho cpu_plugins, cung cấp các giao diện và hệ thống đăng ký.
"""

from .interfaces import ICpuTechnique
from .config import PluginConfig, CpuPluginConfig, load_plugin_config
from .registry import register_plugin, discover_plugins, get_plugin_registry

__all__ = [
    'ICpuTechnique',
    'PluginConfig',
    'CpuPluginConfig',
    'load_plugin_config',
    'register_plugin',
    'discover_plugins',
    'get_plugin_registry',
] 