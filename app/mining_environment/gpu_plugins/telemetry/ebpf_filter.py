"""eBPF Telemetry Filter Plugin - Wrapper cho eBPF filtering"""
import os
import logging
from typing import Dict, Any, List
from ..core.interfaces import IGPUTelemetryFilter

logger = logging.getLogger(__name__)

class EBPFTelemetryFilterPlugin(IGPUTelemetryFilter):
    """Plugin wrapper cho eBPF telemetry filtering"""
    
    def __init__(self):
        self.filter_manager = None
        self.running = False
        
    @property
    def name(self) -> str:
        return "ebpf_telemetry_filter"
        
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Khởi tạo eBPF filter"""
        try:
            from ..ebpf.userspace.ebpf_manager import EBPFTelemetryFilter
            
            config_path = config.get('config_path')
            self.filter_manager = EBPFTelemetryFilter(config_path)
            
            logger.info("eBPF telemetry filter initialized")
            return True
            
        except ImportError:
            logger.error("Failed to import eBPF manager")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize eBPF filter: {e}")
            return False
            
    def start(self) -> bool:
        """Start eBPF filtering"""
        if not self.filter_manager:
            logger.error("eBPF filter manager not initialized")
            return False
            
        try:
            if self.filter_manager.start_filtering():
                self.running = True
                logger.info("✅ eBPF telemetry filtering started")
                return True
            else:
                logger.error("Failed to start eBPF filtering")
                return False
        except Exception as e:
            logger.error(f"Error starting eBPF filtering: {e}")
            return False
            
    def stop(self) -> None:
        """Stop eBPF filtering"""
        if self.filter_manager:
            try:
                self.filter_manager.stop_filtering()
                logger.info("🛑 eBPF telemetry filtering stopped")
            except Exception as e:
                logger.error(f"Error stopping eBPF filtering: {e}")
                
        self.running = False
        
    def start_filtering(self) -> bool:
        """Start filtering (IGPUTelemetryFilter interface)"""
        return self.start()
        
    def stop_filtering(self) -> None:
        """Stop filtering (IGPUTelemetryFilter interface)"""
        self.stop()
        
    def update_filter_rules(self, rules: Dict[str, Any]) -> None:
        """Cập nhật filter rules"""
        if self.filter_manager:
            # Update fake metrics if provided
            if 'fake_metrics' in rules:
                self.filter_manager.update_fake_metrics(rules['fake_metrics'])
                logger.info("Updated eBPF filter rules")
                
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái eBPF filter"""
        status = {
            'name': self.name,
            'running': self.running,
            'manager_initialized': self.filter_manager is not None
        }
        
        if self.filter_manager:
            try:
                status.update(self.filter_manager.get_status())
            except Exception as e:
                status['error'] = str(e)
                
        return status