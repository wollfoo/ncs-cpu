# -*- coding: utf-8 -*-
"""GPU Plugins Package - Quan ly tat ca GPU-related components

Tach biet hoan toan GPU logic khoi CPU plugins de:
- Tang tinh mo-dun va de maintain
- Cung cap interface chuan cho GPU operations
- Ho tro multiple GPU cloaking strategies
- Centralized GPU telemetry filtering
"""

from .core.interfaces import (
    IGPUPlugin,
    IGPUCloakService, 
    IGPUTelemetryFilter,
    IGPUHookManager
)

from .core.registry import gpu_plugin_registry
from .core.manager import GPUPluginManager

# Version info
__version__ = "1.0.0"
__author__ = "GPU Plugins Team"

# Export main APIs
__all__ = [
    "IGPUPlugin",
    "IGPUCloakService",
    "IGPUTelemetryFilter", 
    "IGPUHookManager",
    "gpu_plugin_registry",
    "GPUPluginManager"
]

def create_gpu_manager(config_path=None):
    """Convenience function de tao GPU Plugin Manager
    
    Args:
        config_path: Duong dan toi config file (optional)
        
    Returns:
        GPUPluginManager instance
    """
    return GPUPluginManager(config_path)

def get_plugin_registry():
    """Lay global GPU plugin registry
    
    Returns:
        GPUPluginRegistry instance
    """
    return gpu_plugin_registry