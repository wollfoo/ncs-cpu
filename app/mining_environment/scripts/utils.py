# utils.py

import logging
import subprocess
import functools
import time
import psutil
import threading
from typing import Any, Dict, Optional

# (ĐÃ GỠ) Các helper liên quan GPU đã bị loại bỏ

###############################################################################
#                           DECORATOR retry (đồng bộ)                          #
###############################################################################
def retry(exception_to_check: Any, tries: int = 4, delay: float = 3.0, backoff: float = 2.0):
    """
    Decorator đồng bộ để retry một hàm nếu gặp exception cụ thể.

    :param exception_to_check: Exception hoặc tuple exceptions cần bắt để retry.
    :param tries: Số lần thử (int).
    :param delay: Thời gian chờ ban đầu giữa các lần thử (float, tính bằng giây).
    :param backoff: Hệ số nhân thời gian chờ (float).
    :return: Giá trị hàm nếu thành công, hoặc raise exception nếu hết tries.
    """
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exception_to_check as e:
                    logging.getLogger(__name__).warning(
                        f"Lỗi '{e}' xảy ra trong '{func.__name__}'. "
                        f"Thử lại sau {mdelay} giây..."
                    )
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return wrapper_retry
    return decorator_retry

###############################################################################
#                    (ĐÃ GỠ) Tất cả lớp/hàm quản lý GPU                       #
###############################################################################

###############################################################################
#                           LỚP MiningProcess                                  #
###############################################################################
class MiningProcess:
    """
    Lớp đại diện cho một tiến trình khai thác tiền điện tử (hoặc AI),
    cung cấp thông tin về CPU usage, GPU usage, RAM, Disk I/O, Network I/O, v.v.

    Attributes:
        pid (int): PID tiến trình.
        name (str): Tên tiến trình.
        priority (int): Độ ưu tiên của tiến trình.
        network_interface (str): Giao diện mạng (default='eth0').
        logger (logging.Logger): Logger để ghi log.
        is_cloaked (bool): Cờ đánh dấu tiến trình đã được cloaking.
        (ĐÃ GỠ) Các thuộc tính quản lý GPU.

        cpu_usage (float): % sử dụng CPU hiện tại.
        gpu_usage (float): % sử dụng GPU hiện tại.
        memory_usage (float): % sử dụng RAM hiện tại.
        disk_io (float): Lưu lượng Disk I/O (MB) kể từ lần cập nhật trước.
        network_io (float): Lưu lượng Network I/O (MB) kể từ lần cập nhật trước.
        mark (int): Mark để sử dụng với iptables (VD: PID % 65535).
        _prev_bytes_sent (Optional[int]): Lưu bytes_sent cũ để tính chênh lệch.
        _prev_bytes_recv (Optional[int]): Lưu bytes_recv cũ để tính chênh lệch.
    """

    def __init__(
        self,
        pid: int,
        name: str,
        is_gpu: bool = False,
        priority: int = 1,
        network_interface: str = 'eth0',
        logger: Optional[logging.Logger] = None
    ):
        """
        ✅ ENHANCED: Khởi tạo MiningProcess với classification metadata.

        :param pid: PID của tiến trình.
        :param name: Tên tiến trình.
        :param is_gpu: Cờ đánh dấu tiến trình GPU (bool).
        :param priority: Độ ưu tiên (int).
        :param network_interface: Tên giao diện mạng (str).
        :param logger: Đối tượng Logger (nếu None => tạo logger mặc định).
        """
        self.pid = pid
        self.name = name
        self.priority = priority
        self.cpu_usage = 0.0
        self.gpu_usage = 0.0
        self.memory_usage = 0.0
        self.disk_io = 0.0
        self.network_io = 0.0
        self.mark = pid % 65535
        self.network_interface = network_interface
        self._prev_bytes_sent: Optional[int] = None
        self._prev_bytes_recv: Optional[int] = None
        self.is_cloaked = False
        self.logger = logger or logging.getLogger(__name__)

        # (ĐÃ GỠ) Không còn quản lý GPU trong phiên bản CPU-only
        
        # ✅ ENHANCED: Classification metadata system
        self._is_gpu = is_gpu
        self.process_type = 'GPU' if is_gpu else 'CPU'
        
        # 🎯 HARDWARE CLASSIFICATION
        self.hardware_classification = {
            'is_gpu_process': is_gpu,
            'requires_nvml': is_gpu,
            'resource_requirements': self._determine_resource_requirements(is_gpu),
            'optimization_profile': self._get_optimization_profile(is_gpu),
            'hardware_affinity': 'compute_intensive' if is_gpu else 'general_purpose'
        }
        
        # 🚀 STRATEGY OPTIMIZATION HINTS
        self.strategy_hints = {
            'preferred_cgroup_config': 'gpu_intensive' if is_gpu else 'cpu_balanced',
            'stealth_requirements': 'high' if is_gpu else 'medium',
            'resource_limits': self._calculate_resource_limits(is_gpu),
            'priority_class': 'high_performance' if is_gpu else 'balanced',
            'cloaking_aggressiveness': 'aggressive' if is_gpu else 'moderate'
        }
        
        # 📊 METADATA TRACKING
        self.classification_metadata = {
            'classification_time': time.time(),
            'classification_source': 'constructor',
            'confidence_score': 1.0,  # High confidence from explicit parameter
            'auto_detected': False,  # Explicitly set via parameter
            'fallback_classification': self._fallback_classification_check()
        }

    def is_gpu_process(self) -> bool:
        """
        ✅ ENHANCED: Kiểm tra process type từ classification metadata.

        :return: True nếu process được classified là GPU, False nếu CPU.
        """
        return self._is_gpu
    
    def get_process_type(self) -> str:
        """
        ✅ NEW: Get classified process type.
        
        :return: 'GPU' hoặc 'CPU' based on classification.
        """
        return self.process_type
    
    def get_hardware_classification(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get hardware classification metadata.
        
        :return: Dictionary chứa hardware classification data.
        """
        return self.hardware_classification.copy()
    
    def get_strategy_hints(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get optimization hints for strategies.
        
        :return: Dictionary chứa strategy optimization hints.
        """
        return self.strategy_hints.copy()
    
    def get_classification_metadata(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get classification metadata và tracking info.
        
        :return: Dictionary chứa classification metadata.
        """
        return self.classification_metadata.copy()
    
    def _determine_resource_requirements(self, is_gpu: bool) -> Dict[str, Any]:
        """
        ✅ HELPER: Determine resource requirements based on process type.
        
        :param is_gpu: Process type indicator.
        :return: Resource requirements dictionary.
        """
        if is_gpu:
            return {
                'memory_intensive': True,
                'compute_intensive': True,
                'bandwidth_requirements': 'high',
                'thermal_impact': 'significant',
                'power_consumption': 'high'
            }
        else:
            return {
                'memory_intensive': False,
                'compute_intensive': 'moderate',
                'bandwidth_requirements': 'medium',
                'thermal_impact': 'minimal',
                'power_consumption': 'low'
            }
    
    def _get_optimization_profile(self, is_gpu: bool) -> str:
        """
        ✅ HELPER: Get optimization profile for process type.
        
        :param is_gpu: Process type indicator.
        :return: Optimization profile string.
        """
        return 'gpu_compute_optimized' if is_gpu else 'cpu_general_purpose'
    
    def _calculate_resource_limits(self, is_gpu: bool) -> Dict[str, Any]:
        """
        ✅ HELPER: Calculate appropriate resource limits.
        
        :param is_gpu: Process type indicator.
        :return: Resource limits dictionary.
        """
        if is_gpu:
            return {
                'cpu_limit_percent': 80,  # Allow high CPU for GPU processes
                'memory_limit_mb': 4096,  # Higher memory limit
                'nice_priority': -5,      # Higher priority
                'oom_score_adj': -500     # Lower OOM score
            }
        else:
            return {
                'cpu_limit_percent': 60,  # More conservative CPU limit
                'memory_limit_mb': 2048,  # Lower memory limit
                'nice_priority': 10,      # Lower priority
                'oom_score_adj': 0        # Default OOM score
            }
    
    def _fallback_classification_check(self) -> Dict[str, Any]:
        """
        ✅ HELPER: Fallback classification dựa trên process name.
        
        :return: Fallback classification results.
        """
        gpu_keywords = ['inference-cuda', 'gpu', 'cuda', 'nvidia']
        name_based_gpu = any(keyword in self.name.lower() for keyword in gpu_keywords)
        
        return {
            'name_based_classification': 'GPU' if name_based_gpu else 'CPU',
            'matches_explicit': name_based_gpu == self._is_gpu,
            'confidence': 0.8 if name_based_gpu else 0.6
        }

    def get_gpu_usage(self) -> float:
        """
        (CPU-only) Luôn trả về 0.0 vì mã GPU đã được loại bỏ.
        """
        return 0.0

    def update_resource_usage(self) -> None:
        """
        Cập nhật CPU usage, Memory usage, Disk I/O, Network I/O, GPU usage (nếu có).
        Đồng bộ, không sử dụng async/await.
        """
        try:
            proc = psutil.Process(self.pid)

            # Lấy % CPU (interval=0.1 giây)
            self.cpu_usage = proc.cpu_percent(interval=0.1)
            self.memory_usage = proc.memory_percent()

            io_counters = proc.io_counters()
            self.disk_io = max((io_counters.read_bytes + io_counters.write_bytes) / (1024 * 1024), 0.0)

            net_io_all = psutil.net_io_counters(pernic=True)
            if self.network_interface in net_io_all:
                current_bytes_sent = net_io_all[self.network_interface].bytes_sent
                current_bytes_recv = net_io_all[self.network_interface].bytes_recv

                if self._prev_bytes_sent is not None and self._prev_bytes_recv is not None:
                    sent_diff = max(current_bytes_sent - self._prev_bytes_sent, 0)
                    recv_diff = max(current_bytes_recv - self._prev_bytes_recv, 0)
                    self.network_io = (sent_diff + recv_diff) / (1024 * 1024)
                else:
                    self.network_io = 0.0

                self._prev_bytes_sent = current_bytes_sent
                self._prev_bytes_recv = current_bytes_recv
            else:
                self.logger.warning(
                    f"Giao diện mạng '{self.network_interface}' không tìm thấy cho PID={self.pid}."
                )
                self.network_io = 0.0

            # (CPU-only) Không còn đo GPU – luôn 0.0
            self.gpu_usage = 0.0

            self.logger.debug(
                f"[MiningProcess update] {self.name} (PID={self.pid}): "
                f"CPU={self.cpu_usage}%, GPU={self.gpu_usage}%, RAM={self.memory_usage}%, "
                f"DiskIO={self.disk_io}MB, NetIO={self.network_io}MB."
            )
        except psutil.NoSuchProcess:
            self.logger.error(f"Tiến trình {self.name} (PID={self.pid}) không tồn tại.")
            self.cpu_usage = self.memory_usage = self.disk_io = self.network_io = self.gpu_usage = 0.0
        except Exception as e:
            self.logger.error(f"Lỗi update_resource_usage PID={self.pid}: {e}")
            self.cpu_usage = self.memory_usage = self.disk_io = self.network_io = self.gpu_usage = 0.0

    def reset_network_io(self) -> None:
        """
        Reset thống kê về Network I/O (bytes_sent, bytes_recv).
        """
        self._prev_bytes_sent = None
        self._prev_bytes_recv = None
        self.network_io = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """
        Trả về dict chứa thông tin resource usage và trạng thái tiến trình.

        :return: Từ điển thông tin (Dict[str, Any]).
        """
        try:
            return {
                'pid': self.pid,
                'name': self.name,
                'priority': int(self.priority) if isinstance(self.priority, int) else 1,
                'cpu_usage_percent': float(self.cpu_usage),
                'memory_usage_percent': float(self.memory_usage),
                'gpu_usage_percent': float(self.gpu_usage),
                'disk_io_mb': float(self.disk_io),
                'network_bandwidth_mb': float(self.network_io),
                'mark': self.mark,
                'network_interface': self.network_interface,
                'is_cloaked': self.is_cloaked
            }
        except Exception as e:
            self.logger.error(f"Lỗi to_dict PID={self.pid}: {e}")
            return {}
