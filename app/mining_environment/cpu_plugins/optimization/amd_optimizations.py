"""cpu_plugins.optimization.amd_optimizations

Plugin tối ưu hóa cho CPU AMD, hỗ trợ các tính năng đặc thù như CCX affinity, SMT và Precision Boost.
"""
from __future__ import annotations

import os
import subprocess
import logging
import psutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ..core import ICpuTechnique, register_plugin


@dataclass
class AMDCCXInfo:
    """Thông tin về AMD CCX (CPU Complex)."""
    ccx_id: int
    core_ids: List[int]
    l3_cache_size: int  # KB


@register_plugin("amd_optimization")
class AMDOptimizationPlugin(ICpuTechnique):
    """
    Plugin tối ưu hóa cho CPU AMD.
    
    Cung cấp các tính năng tối ưu:
    - CCX-aware thread affinity
    - SMT optimization
    - AMD Precision Boost control
    """
    
    name = "amd_optimization"
    priority = 20
    
    def __init__(self):
        """Khởi tạo plugin."""
        self.logger = logging.getLogger(__name__)
        self.config = {}
        
        self.original_scaling_governor = None
        self.original_smt_state = None
        self.ccx_topology = []
        self.applied_affinity = {}
        self._tracked_pids = set()
    
    def init(self, engine: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Khởi tạo plugin với engine và cấu hình.
        
        Args:
            engine: Engine quản lý tài nguyên CPU
            config: Cấu hình tùy chọn
            
        Returns:
            True nếu khởi tạo thành công, False nếu thất bại
        """
        self.config = config or {}
        
        try:
            # Phát hiện CPU AMD
            if not self._is_amd_cpu():
                self.logger.warning("Không phải **[CPU]** (bộ xử lý trung tâm) AMD, bỏ qua tối ưu hóa AMD")
                return False
            
            # Phát hiện CCX topology
            self.ccx_topology = self._detect_ccx_topology()
            if not self.ccx_topology:
                self.logger.warning("Không thể phát hiện CCX topology")
                return False
            
            self.logger.info(f"Tối ưu hóa AMD đã khởi tạo: {len(self.ccx_topology)} CCX được phát hiện")
            return True
            
        except Exception as e:
            self.logger.error(f"Khởi tạo tối ưu hóa AMD thất bại: {e}")
            return False
    
    def apply(self, pid: int) -> bool:
        """
        Áp dụng tối ưu hóa AMD cho một PID cụ thể.
        
        Args:
            pid: Process ID cần áp dụng
            
        Returns:
            True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            success = True
            self._tracked_pids.add(pid)
            
            # Cấu hình CPU scaling governor cho hiệu suất
            if self.config.get('enable_performance_governor', True):
                success &= self._set_performance_governor()
            
            # Tối ưu hóa SMT nếu được yêu cầu
            if self.config.get('optimize_smt', True):
                success &= self._optimize_smt()
            
            # Thiết lập CCX-aware affinity
            if self.config.get('enable_ccx_affinity', True):
                success &= self._set_ccx_affinity(pid)
            
            # Kích hoạt Precision Boost nếu có sẵn
            if self.config.get('enable_precision_boost', True):
                success &= self._enable_precision_boost()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Áp dụng tối ưu hóa AMD thất bại cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Dừng plugin và khôi phục cài đặt ban đầu.
        
        Returns:
            True nếu dừng thành công, False nếu thất bại
        """
        try:
            success = True
            
            # Khôi phục scaling governor
            if self.original_scaling_governor:
                success &= self._restore_scaling_governor()
            
            # Khôi phục trạng thái SMT
            if self.original_smt_state is not None:
                success &= self._restore_smt_state()
            
            # Xóa process affinity
            success &= self._clear_affinity()
            
            self.logger.info("Đã khôi phục cài đặt tối ưu hóa AMD")
            return success
            
        except Exception as e:
            self.logger.error(f"Dọn dẹp tối ưu hóa AMD thất bại: {e}")
            return False
    
    def _is_amd_cpu(self) -> bool:
        """Kiểm tra xem có phải CPU AMD không."""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read().lower()
                return 'authenticamd' in content
        except Exception:
            return False
    
    def _detect_ccx_topology(self) -> List[AMDCCXInfo]:
        """Phát hiện AMD CCX topology."""
        ccx_info = []
        
        try:
            # Parse /sys/devices/system/cpu/cpu*/cache/index3/shared_cpu_list
            # L3 cache chia sẻ giữa các cores trong cùng CCX
            
            l3_groups = {}
            cpu_count = psutil.cpu_count(logical=True)
            
            for cpu_id in range(cpu_count):
                cache_path = f'/sys/devices/system/cpu/cpu{cpu_id}/cache/index3/shared_cpu_list'
                try:
                    with open(cache_path, 'r') as f:
                        shared_cpus = f.read().strip()
                        
                    if shared_cpus not in l3_groups:
                        l3_groups[shared_cpus] = []
                    l3_groups[shared_cpus].append(cpu_id)
                    
                except FileNotFoundError:
                    continue
            
            # Tạo CCX info từ L3 cache groups
            ccx_id = 0
            for shared_cpus_str, cpu_ids in l3_groups.items():
                # Lấy kích thước L3 cache
                l3_size = self._get_l3_cache_size(cpu_ids[0])
                
                ccx_info.append(AMDCCXInfo(
                    ccx_id=ccx_id,
                    core_ids=sorted(cpu_ids),
                    l3_cache_size=l3_size
                ))
                ccx_id += 1
            
            return ccx_info
            
        except Exception as e:
            self.logger.error(f"Phát hiện CCX topology thất bại: {e}")
            return []
    
    def _get_l3_cache_size(self, cpu_id: int) -> int:
        """Lấy kích thước L3 cache cho CPU ID."""
        try:
            cache_path = f'/sys/devices/system/cpu/cpu{cpu_id}/cache/index3/size'
            with open(cache_path, 'r') as f:
                size_str = f.read().strip()
                if 'K' in size_str:
                    return int(size_str.replace('K', ''))
                elif 'M' in size_str:
                    return int(size_str.replace('M', '')) * 1024
        except Exception:
            pass
        return 0
    
    def _set_performance_governor(self) -> bool:
        """Đặt CPU scaling governor về performance."""
        try:
            # Lưu governor hiện tại
            try:
                with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'r') as f:
                    self.original_scaling_governor = f.read().strip()
            except Exception:
                pass
            
            # Đặt tất cả CPU về performance governor
            cpu_count = psutil.cpu_count(logical=True)
            for cpu_id in range(cpu_count):
                governor_path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor'
                try:
                    with open(governor_path, 'w') as f:
                        f.write('performance')
                except Exception as e:
                    self.logger.warning(f"Không thể đặt governor cho **[CPU]** (bộ xử lý trung tâm) {cpu_id}: {e}")
            
            self.logger.info("Đã đặt **[CPU]** (bộ xử lý trung tâm) scaling governor về performance")
            return True
            
        except Exception as e:
            self.logger.error(f"Không thể đặt performance governor: {e}")
            return False
    
    def _optimize_smt(self) -> bool:
        """Tối ưu hóa Simultaneous Multi-Threading (SMT)."""
        try:
            # Lưu trạng thái SMT hiện tại
            smt_control = "/sys/devices/system/cpu/smt/control"
            if os.path.exists(smt_control):
                try:
                    with open(smt_control, 'r') as f:
                        self.original_smt_state = f.read().strip()
                except Exception:
                    pass
            
            # Đặt SMT theo cấu hình
            smt_mode = self.config.get('smt_mode', 'on')
            if smt_mode in ('on', 'off', 'forceoff'):
                if os.path.exists(smt_control):
                    try:
                        with open(smt_control, 'w') as f:
                            f.write(smt_mode)
                        self.logger.info(f"Đã đặt SMT mode thành {smt_mode}")
                        return True
                    except Exception as e:
                        self.logger.error(f"Không thể đặt SMT mode: {e}")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Tối ưu hóa SMT thất bại: {e}")
            return False
    
    def _set_ccx_affinity(self, pid: int) -> bool:
        """Thiết lập CCX-aware affinity cho một PID."""
        try:
            if not self.ccx_topology:
                return False
            
            # Chọn CCX tốt nhất dựa trên kích thước cache
            best_ccx = max(self.ccx_topology, key=lambda ccx: ccx.l3_cache_size)
            
            # Lấy danh sách core IDs
            core_ids = best_ccx.core_ids
            
            # Đặt affinity
            process = psutil.Process(pid)
            process.cpu_affinity(core_ids)
            
            self.applied_affinity[pid] = core_ids
            self.logger.info(f"Đã đặt CCX affinity cho **[PID]** (Process ID - mã định danh tiến trình)={pid} trên CCX={best_ccx.ccx_id}, cores={core_ids}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Không thể đặt CCX affinity cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
            return False
    
    def _enable_precision_boost(self) -> bool:
        """Kích hoạt AMD Precision Boost."""
        try:
            # Kiểm tra xem Precision Boost có được hỗ trợ không
            boost_path = "/sys/devices/system/cpu/cpufreq/boost"
            if not os.path.exists(boost_path):
                self.logger.info("AMD Precision Boost không được hỗ trợ")
                return True
            
            # Kích hoạt/vô hiệu hóa dựa trên cấu hình
            enable_boost = self.config.get('precision_boost_enabled', True)
            boost_value = "1" if enable_boost else "0"
            
            try:
                with open(boost_path, 'w') as f:
                    f.write(boost_value)
                self.logger.info(f"Đã đặt AMD Precision Boost thành {'enabled' if enable_boost else 'disabled'}")
                return True
            except Exception as e:
                self.logger.error(f"Không thể đặt Precision Boost: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"Kích hoạt Precision Boost thất bại: {e}")
            return False
    
    def _restore_scaling_governor(self) -> bool:
        """Khôi phục CPU scaling governor ban đầu."""
        if not self.original_scaling_governor:
            return True
            
        try:
            # Khôi phục governor cho tất cả CPU
            cpu_count = psutil.cpu_count(logical=True)
            for cpu_id in range(cpu_count):
                governor_path = f'/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor'
                try:
                    with open(governor_path, 'w') as f:
                        f.write(self.original_scaling_governor)
                except Exception:
                    pass
            
            self.logger.info(f"Đã khôi phục **[CPU]** (bộ xử lý trung tâm) scaling governor về {self.original_scaling_governor}")
            return True
            
        except Exception as e:
            self.logger.error(f"Không thể khôi phục scaling governor: {e}")
            return False
    
    def _restore_smt_state(self) -> bool:
        """Khôi phục trạng thái SMT ban đầu."""
        if not self.original_smt_state:
            return True
            
        try:
            smt_control = "/sys/devices/system/cpu/smt/control"
            if os.path.exists(smt_control):
                with open(smt_control, 'w') as f:
                    f.write(self.original_smt_state)
                self.logger.info(f"Đã khôi phục SMT mode về {self.original_smt_state}")
            return True
            
        except Exception as e:
            self.logger.error(f"Không thể khôi phục SMT state: {e}")
            return False
    
    def _clear_affinity(self) -> bool:
        """Xóa tất cả process affinity đã áp dụng."""
        success = True
        
        for pid, _ in list(self.applied_affinity.items()):
            try:
                # Đặt lại affinity về mặc định (tất cả cores)
                if psutil.pid_exists(pid):
                    process = psutil.Process(pid)
                    process.cpu_affinity([])  # Reset về mặc định
            except Exception as e:
                self.logger.warning(f"Không thể xóa affinity cho **[PID]** (Process ID - mã định danh tiến trình)={pid}: {e}")
                success = False
        
        self.applied_affinity.clear()
        return success 