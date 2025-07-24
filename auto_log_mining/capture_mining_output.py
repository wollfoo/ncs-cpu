#!/usr/bin/env python3
"""
🎯 Capture Actual Mining Output to Log Files
Capture real stdout from mining processes and write to cpu_miner.log & gpu_miner.log
"""

import subprocess
import psutil
import time
import sys
import os
import threading
import signal
sys.path.append('.')

from mining_environment.scripts.logging_config import setup_logging

def capture_stdout_to_log(pid, process_name, logger):
    """
    Capture actual stdout from mining process and log to file
    """
    try:
        # Use cat to read from stdout pipe
        cmd = f"timeout 300s cat /proc/{pid}/fd/1"
        
        logger.info(f"📊 Starting stdout capture for {process_name} PID {pid}")
        
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        line_count = 0
        start_time = time.time()
        runtime = 0
        
        for line in process.stdout:
            if line.strip():
                line_count += 1
                runtime = time.time() - start_time
                
                # Clean ANSI color codes for log file
                clean_line = ''.join(char for char in line if ord(char) < 127 or char in ['\n', '\t'])
                clean_line = clean_line.replace('\x1b[', '').replace('[0m', '').replace('[1;32m', '').replace('[1;37m', '')
                clean_line = clean_line.replace('[1;36m', '').replace('[1;30m', '').replace('[44;1m', '').replace('[46;1m', '')
                clean_line = clean_line.replace('[45;1m', '').replace('[44m', '').replace('[1;31m', '').replace('[0;36m', '')
                
                # Log the actual mining output
                logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] {clean_line.strip()}")
                
                # Highlight important mining metrics
                if any(keyword in clean_line.lower() for keyword in ['height', 'h/s', 'difficulty', 'task progress']):
                    logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] 🎯 MINING METRICS: {clean_line.strip()}")
                
                if line_count > 200:  # Limit output
                    break
        
        process.terminate()
        logger.info(f"📊 Stdout capture completed for {process_name} - captured {line_count} lines in {runtime:.1f}s")
        return line_count
        
    except Exception as e:
        logger.error(f"❌ Failed to capture stdout for {process_name}: {e}")
        return 0

def monitor_mining_output():
    """Monitor and log actual mining output"""
    
    # Setup loggers
    cpu_logger = setup_logging('cpu_miner_capture', './mining_environment/logs/cpu_miner.log', 'INFO')
    gpu_logger = setup_logging('gpu_miner_capture', './mining_environment/logs/gpu_miner.log', 'INFO')
    
    print("🎯 Starting mining output capture to log files...")
    cpu_logger.info("📊 Mining output capture started for CPU processes")
    gpu_logger.info("📊 Mining output capture started for GPU processes")
    
    try:
        # Find mining processes
        cpu_processes = []
        gpu_processes = []
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ml-inference' in proc.info['name']:
                    cpu_processes.append(proc.info['pid'])
                    cpu_logger.info(f"📊 Found CPU mining process: PID {proc.info['pid']}")
                elif 'inference-cuda' in proc.info['name']:
                    gpu_processes.append(proc.info['pid'])
                    gpu_logger.info(f"📊 Found GPU mining process: PID {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        print(f"Found {len(cpu_processes)} CPU processes, {len(gpu_processes)} GPU processes")
        
        # Start capture threads
        threads = []
        
        # Capture CPU processes (limit to first 2)
        for pid in cpu_processes[:2]:
            thread = threading.Thread(
                target=capture_stdout_to_log,
                args=(pid, "CPU", cpu_logger),
                daemon=True,
                name=f"CPUCapture-{pid}"
            )
            thread.start()
            threads.append(thread)
        
        # Capture GPU processes (limit to first 1)
        for pid in gpu_processes[:1]:
            thread = threading.Thread(
                target=capture_stdout_to_log,
                args=(pid, "GPU", gpu_logger),
                daemon=True,
                name=f"GPUCapture-{pid}"
            )
            thread.start()
            threads.append(thread)
        
        # Wait for completion with timeout
        for thread in threads:
            thread.join(timeout=330)  # 5.5 minutes max per thread
        
        cpu_logger.info("📊 Mining output capture completed for CPU")
        gpu_logger.info("📊 Mining output capture completed for GPU")
        print("✅ Mining output capture completed successfully")
        
    except KeyboardInterrupt:
        print("\n⚠️ Capture interrupted by user")
    except Exception as e:
        cpu_logger.error(f"❌ Mining output capture error: {e}")
        gpu_logger.error(f"❌ Mining output capture error: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    monitor_mining_output()