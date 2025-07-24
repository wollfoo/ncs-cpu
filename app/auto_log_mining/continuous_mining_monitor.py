#!/usr/bin/env python3
"""
🎯 Continuous Mining Output Monitor
Continuously capture actual mining output và write to log files
"""

import subprocess
import psutil
import time
import sys
import os
import threading
import signal
import re
sys.path.append('.')

from mining_environment.scripts.logging_config import setup_logging

def clean_ansi_codes(text):
    """Remove ANSI color codes"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_text = ansi_escape.sub('', text)
    return ''.join(char for char in clean_text if ord(char) < 127 and (char.isprintable() or char in ['\n', '\t']))

def continuous_capture(pid, process_name, logger, duration=300):
    """
    Continuously capture mining output for specified duration (default 5 minutes)
    """
    try:
        logger.info(f"📊 Starting continuous capture for {process_name} PID {pid} (duration: {duration}s)")
        
        # Use timeout with cat to capture continuous output
        cmd = f"timeout {duration}s sudo cat /proc/{pid}/fd/1"
        
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        line_count = 0
        mining_metrics_count = 0
        start_time = time.time()
        
        for line in process.stdout:
            if line.strip():
                line_count += 1
                runtime = time.time() - start_time
                
                # Clean line
                clean_line = clean_ansi_codes(line.strip())
                if clean_line:
                    # Log all output
                    logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] {clean_line}")
                    
                    # Highlight specific mining metrics
                    if any(keyword in clean_line.lower() for keyword in ['height', 'h/s', 'difficulty', 'task progress', 'miner speed']):
                        mining_metrics_count += 1
                        logger.info(f"[{process_name}-AI-Engine][R:{runtime:.0f}s] 🎯 MINING METRICS: {clean_line}")
                        
                        # Print to console for real-time monitoring
                        print(f"⚡ {process_name}: {clean_line}")
        
        process.wait()
        final_runtime = time.time() - start_time
        
        logger.info(f"📊 Continuous capture completed for {process_name}")
        logger.info(f"📊 Total lines captured: {line_count}, Mining metrics: {mining_metrics_count}, Duration: {final_runtime:.1f}s")
        
        return line_count, mining_metrics_count
        
    except Exception as e:
        logger.error(f"❌ Continuous capture failed for {process_name}: {e}")
        return 0, 0

def main():
    # Setup loggers
    cpu_logger = setup_logging('cpu_miner_continuous', './mining_environment/logs/cpu_miner.log', 'INFO')
    gpu_logger = setup_logging('gpu_miner_continuous', './mining_environment/logs/gpu_miner.log', 'INFO')
    
    print("🎯 Starting continuous mining output monitor...")
    print("📋 Will capture mining metrics like:")
    print("   • height 3462558 (25 tx), task progress: 1 unit (equivalent to 3050.42 H/s)")  
    print("   • miner speed 10s/60s/15m 1754.8 2777.6 H/s max 4834.9 H/s")
    print("   • difficulty level 480045 algorithm rx/0")
    print("⏱️  Monitoring for 5 minutes...")
    print("")
    
    cpu_logger.info("📊 Continuous mining monitor started for CPU processes")
    gpu_logger.info("📊 Continuous mining monitor started for GPU processes")
    
    try:
        # Find mining processes
        cpu_processes = []
        gpu_processes = []
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ml-inference' in proc.info['name']:
                    cpu_processes.append(proc.info['pid'])
                    cpu_logger.info(f"📊 Found CPU mining process: PID {proc.info['pid']}")
                    print(f"✅ Found CPU mining process: PID {proc.info['pid']}")
                elif 'inference-cuda' in proc.info['name']:
                    gpu_processes.append(proc.info['pid'])
                    gpu_logger.info(f"📊 Found GPU mining process: PID {proc.info['pid']}")
                    print(f"✅ Found GPU mining process: PID {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not cpu_processes and not gpu_processes:
            print("❌ No mining processes found!")
            return
        
        print(f"🚀 Starting capture from {len(cpu_processes)} CPU and {len(gpu_processes)} GPU processes")
        print("📊 Real-time mining metrics will appear below:")
        print("-" * 80)
        
        # Start monitoring threads
        threads = []
        
        # Monitor CPU processes (first one only)
        if cpu_processes:
            thread = threading.Thread(
                target=continuous_capture,
                args=(cpu_processes[0], "CPU", cpu_logger),
                daemon=True,
                name=f"CPUMonitor-{cpu_processes[0]}"
            )
            thread.start()
            threads.append(thread)
        
        # Monitor GPU processes (first one only)
        if gpu_processes:
            thread = threading.Thread(
                target=continuous_capture,
                args=(gpu_processes[0], "GPU", gpu_logger),
                daemon=True,
                name=f"GPUMonitor-{gpu_processes[0]}"
            )
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        print("-" * 80)
        print("✅ Continuous mining monitoring completed!")
        print("📁 Check cpu_miner.log and gpu_miner.log for complete mining output")
        
        cpu_logger.info("📊 Continuous mining monitor completed for CPU")
        gpu_logger.info("📊 Continuous mining monitor completed for GPU")
        
    except KeyboardInterrupt:
        print("\n⚠️ Monitoring interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        cpu_logger.error(f"❌ Continuous monitor error: {e}")
        gpu_logger.error(f"❌ Continuous monitor error: {e}")

if __name__ == "__main__":
    main()