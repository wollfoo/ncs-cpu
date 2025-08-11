"""cpu_plugins.utils.hardware

Tiện ích phát hiện phần cứng, đơn giản hóa từ hardware_detector.py.
"""
import platform
import subprocess
import logging
import re
from typing import Dict, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass


class CPUVendor(Enum):
    """Nhà sản xuất CPU."""
    INTEL = "intel"
    AMD = "amd"
    ARM = "arm"
    UNKNOWN = "unknown"


class GPUVendor(Enum):
    """Nhà sản xuất GPU."""
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    UNKNOWN = "unknown"


@dataclass
class CPUInfo:
    """Thông tin CPU được phát hiện."""
    vendor: CPUVendor
    model: str
    cores: int
    threads: int
    features: Dict[str, bool]
    supports_rdt: bool = False
    supports_cat: bool = False


@dataclass
class GPUInfo:
    """Thông tin GPU được phát hiện."""
    vendor: GPUVendor
    model: str
    count: int = 0
    driver_version: Optional[str] = None


class HardwareDetector:
    """
    Phát hiện phần cứng và cung cấp thông tin về CPU/GPU.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Khởi tạo HardwareDetector."""
        self.logger = logger or logging.getLogger(__name__)
        self._cpu_cache = None
        self._gpu_cache = None
    
    def detect_cpu(self) -> CPUInfo:
        """Phát hiện thông tin CPU."""
        if self._cpu_cache:
            return self._cpu_cache
            
        try:
            # Phát hiện nhà sản xuất
            vendor = self._detect_cpu_vendor()
            
            # Lấy thông tin model
            model = self._get_cpu_model()
            
            # Đếm cores/threads
            cores = self._get_physical_cores()
            threads = self._get_logical_cores()
            
            # Phát hiện tính năng
            features = self._detect_cpu_features()
            
            # Tính năng đặc biệt của Intel
            supports_rdt = vendor == CPUVendor.INTEL and self._check_intel_rdt()
            supports_cat = supports_rdt and self._check_intel_cat()
            
            cpu_info = CPUInfo(
                vendor=vendor,
                model=model,
                cores=cores,
                threads=threads,
                features=features,
                supports_rdt=supports_rdt,
                supports_cat=supports_cat
            )
            
            self._cpu_cache = cpu_info
            self.logger.info(f"**[CPU]** (bộ xử lý trung tâm) detected: {vendor.value} {model}, {cores}C/{threads}T")
            
            return cpu_info
            
        except Exception as e:
            self.logger.error(f"**[CPU]** (bộ xử lý trung tâm) detection failed: {e}")
            # Trả về thông tin tối thiểu
            return CPUInfo(
                vendor=CPUVendor.UNKNOWN,
                model="Unknown",
                cores=1,
                threads=1,
                features={}
            )
    
    def detect_gpu(self) -> GPUInfo:
        """Phát hiện thông tin GPU."""
        if self._gpu_cache:
            return self._gpu_cache
            
        try:
            # Thử NVIDIA trước
            nvidia_info = self._detect_nvidia_gpu()
            if nvidia_info:
                self._gpu_cache = nvidia_info
                return nvidia_info
            
            # Thử AMD
            amd_info = self._detect_amd_gpu()
            if amd_info:
                self._gpu_cache = amd_info
                return amd_info
            
            # Fallback - không có GPU
            gpu_info = GPUInfo(
                vendor=GPUVendor.UNKNOWN,
                model="None"
            )
            
            self._gpu_cache = gpu_info
            return gpu_info
            
        except Exception as e:
            self.logger.error(f"**[GPU]** (bộ xử lý đồ họa) detection failed: {e}")
            return GPUInfo(
                vendor=GPUVendor.UNKNOWN,
                model="Unknown"
            )
    
    def _detect_cpu_vendor(self) -> CPUVendor:
        """Phát hiện nhà sản xuất CPU."""
        try:
            # Phương pháp Linux
            if platform.system() == "Linux":
                with open('/proc/cpuinfo', 'r') as f:
                    content = f.read().lower()
                    if 'genuineintel' in content:
                        return CPUVendor.INTEL
                    elif 'authenticamd' in content:
                        return CPUVendor.AMD
                    elif 'arm' in content:
                        return CPUVendor.ARM
            
            # Fallback dựa trên platform
            machine = platform.machine().lower()
            if 'arm' in machine or 'aarch64' in machine:
                return CPUVendor.ARM
                
        except Exception:
            pass
        
        return CPUVendor.UNKNOWN
    
    def _get_cpu_model(self) -> str:
        """Lấy model CPU."""
        try:
            if platform.system() == "Linux":
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            return line.split(':', 1)[1].strip()
        except Exception:
            pass
        
        return platform.processor() or "Unknown"
    
    def _get_physical_cores(self) -> int:
        """Đếm số physical cores."""
        try:
            import psutil
            return psutil.cpu_count(logical=False) or 1
        except Exception:
            return 1
    
    def _get_logical_cores(self) -> int:
        """Đếm số logical cores."""
        try:
            import psutil
            return psutil.cpu_count(logical=True) or 1
        except Exception:
            return 1
    
    def _detect_cpu_features(self) -> Dict[str, bool]:
        """Phát hiện CPU features."""
        features = {
            'avx': False,
            'avx2': False,
            'avx512': False,
            'aes': False,
            'fma': False,
            'sse4_1': False,
            'sse4_2': False
        }
        
        try:
            if platform.system() == "Linux":
                with open('/proc/cpuinfo', 'r') as f:
                    flags_line = None
                    for line in f:
                        if line.startswith('flags'):
                            flags_line = line.lower()
                            break
                    
                    if flags_line:
                        for feature in features.keys():
                            features[feature] = feature in flags_line
        
        except Exception:
            pass
        
        return features
    
    def _check_intel_rdt(self) -> bool:
        """Kiểm tra Intel RDT support."""
        try:
            # Kiểm tra thư mục resctrl
            return platform.system() == "Linux" and (
                subprocess.run(
                    ["mount", "-l", "-t", "resctrl"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                ).returncode == 0 or
                subprocess.run(
                    ["ls", "/sys/fs/resctrl"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                ).returncode == 0
            )
        except Exception:
            return False
    
    def _check_intel_cat(self) -> bool:
        """Kiểm tra Intel CAT support."""
        try:
            # Kiểm tra thư mục resctrl/info/L3_MON
            return platform.system() == "Linux" and subprocess.run(
                ["ls", "/sys/fs/resctrl/info/L3"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            ).returncode == 0
        except Exception:
            return False
    
    def _detect_nvidia_gpu(self) -> Optional[GPUInfo]:
        """Phát hiện NVIDIA GPU."""
        try:
            # Kiểm tra nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,count", "--format=csv,noheader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                return None
                
            output = result.stdout.strip()
            if not output:
                return None
                
            # Parse output
            parts = output.split(',')
            model = parts[0].strip()
            count = int(parts[1].strip()) if len(parts) > 1 else 1
            
            # Lấy phiên bản driver
            driver_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            driver_version = None
            if driver_result.returncode == 0:
                driver_version = driver_result.stdout.strip().split('\n')[0]
            
            return GPUInfo(
                vendor=GPUVendor.NVIDIA,
                model=model,
                count=count,
                driver_version=driver_version
            )
            
        except Exception:
            return None
    
    def _detect_amd_gpu(self) -> Optional[GPUInfo]:
        """Phát hiện AMD GPU."""
        try:
            # Kiểm tra rocm-smi
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                # Thử lsmod | grep amdgpu
                result = subprocess.run(
                    "lspci | grep -i amd | grep -i vga",
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode != 0 or not result.stdout.strip():
                    return None
                    
                # Parse lspci output
                output = result.stdout.strip()
                match = re.search(r'\[AMD/ATI\] (.+?)(?:\s*\[|$)', output)
                gpu_name = "AMD GPU"
                if match:
                    gpu_name = match.group(1).strip()
                
                return GPUInfo(
                    vendor=GPUVendor.AMD,
                    model=gpu_name,
                    count=1
                )
            
            # Parse rocm-smi output
            output = result.stdout.strip()
            model = "AMD GPU"
            count = 1
            
            match = re.search(r'GPU\[(\d+)\].*?:\s+(.+)', output)
            if match:
                count = int(match.group(1)) + 1
                model = match.group(2).strip()
            
            return GPUInfo(
                vendor=GPUVendor.AMD,
                model=model,
                count=count
            )
            
        except Exception:
            return None 