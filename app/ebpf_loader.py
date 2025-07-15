#!/usr/bin/env python3
"""
eBPF Object Loader - Load pre-compiled eBPF objects
Chỉ LOAD, KHÔNG build/compile
"""


import os
import sys
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ebpf_loader')

class eBPFLoader:
    def __init__(self):
        self.bpf_mount = "/sys/fs/bpf"
        self.objects = {
            # Chỉ quản lý GPU telemetry filtering eBPF objects
            "gpu_telemetry_filter": "/app/mining_environment/scripts/ebpf_telemetry_filter/obj/gpu_telemetry_filter.bpf.o"
        }
        
    def verify_environment(self):
        """Verify eBPF loading environment"""
        logger.info("🔍 Verifying eBPF environment...")
        
        # Check BPF filesystem mount
        if not os.path.exists(self.bpf_mount):
            logger.warning(f"BPF mount point {self.bpf_mount} doesn't exist, creating...")
            os.makedirs(self.bpf_mount, exist_ok=True)
        
        # Check if BPF filesystem is mounted
        try:
            result = subprocess.run(['mount'], capture_output=True, text=True)
            if 'bpf on /sys/fs/bpf' not in result.stdout:
                logger.info("Mounting BPF filesystem...")
                subprocess.run(['mount', '-t', 'bpf', 'bpf', self.bpf_mount], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to mount BPF filesystem: {e}")
        
        # Check bpftool availability
        try:
            result = subprocess.run(['bpftool', 'prog', 'list'], 
                                  capture_output=True, text=True, timeout=5)
            logger.info("✅ bpftool is available")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("⚠️ bpftool not available or needs privileged mode")
            return False
    
    def check_objects_exist(self):
        """Check if pre-compiled eBPF objects exist"""
        logger.info("📁 Checking eBPF objects...")
        
        missing_objects = []
        for name, path in self.objects.items():
            if os.path.exists(path):
                size = os.path.getsize(path)
                logger.info(f"✅ {name}: {path} ({size} bytes)")
            else:
                logger.error(f"❌ {name}: {path} not found")
                missing_objects.append(name)
        
        if missing_objects:
            logger.error(f"Missing eBPF objects: {missing_objects}")
            return False
        
        return True
    
    def load_with_bpftool(self, obj_path, prog_name):
        """Load eBPF object using bpftool"""
        try:
            pin_path = f"{self.bpf_mount}/{prog_name}"
            
            # Check if already loaded
            if os.path.exists(pin_path):
                logger.info(f"✅ Bỏ qua nạp lại: {prog_name} đã được ghim sẵn tại {pin_path}")
                return True
            
            # Load object
            cmd = ["bpftool", "prog", "load", obj_path, pin_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"✅ Loaded {prog_name} successfully")
                return True
            else:
                logger.error(f"❌ bpftool load failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ bpftool load timeout for {prog_name}")
            return False
        except Exception as e:
            logger.error(f"❌ Exception loading {prog_name}: {e}")
            return False
    
    def load_with_bcc(self, obj_path, prog_name):
        """Load eBPF object using BCC Python bindings"""
        try:
            import bcc  # type: ignore
            logger.info(f"🐍 Loading {prog_name} with BCC...")
            
            # Read object file
            with open(obj_path, 'rb') as f:
                obj_bytes = f.read()
            
            # Create BPF program
            b = bcc.BPF(object=obj_bytes)
            
            logger.info(f"✅ Loaded {prog_name} via BCC")
            
            # Keep reference to prevent garbage collection
            setattr(self, f"bpf_{prog_name}", b)
            return True
            
        except ImportError:
            logger.error("❌ BCC Python module not available")
            return False
        except Exception as e:
            logger.error(f"❌ BCC load failed for {prog_name}: {e}")
            return False
    
    def load_objects(self):
        """Load all eBPF objects"""
        logger.info("🚀 Starting eBPF object loading...")
        
        success_count = 0
        
        for name, path in self.objects.items():
            logger.info(f"Loading {name}...")
            
            # Try bpftool first
            if self.load_with_bpftool(path, name):
                success_count += 1
                continue
            
            # Fallback to BCC
            if self.load_with_bcc(path, name):
                success_count += 1
                continue
            
            logger.error(f"❌ Failed to load {name}")
        
        logger.info(f"📊 Loaded {success_count}/{len(self.objects)} eBPF objects")
        return success_count == len(self.objects)
    
    def list_loaded_programs(self):
        """List currently loaded eBPF programs"""
        try:
            result = subprocess.run(['bpftool', 'prog', 'list'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("📋 Currently loaded eBPF programs:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
            else:
                logger.warning("Unable to list programs with bpftool")
        except Exception:
            logger.warning("Unable to list loaded programs")

def main():
    """Main function"""
    loader = eBPFLoader()
    
    # Verify environment
    if not loader.verify_environment():
        logger.warning("⚠️ eBPF environment issues detected, continuing anyway...")
    
    # Check objects exist
    if not loader.check_objects_exist():
        logger.error("❌ Missing eBPF objects, cannot proceed")
        sys.exit(1)
    
    # Load objects
    if loader.load_objects():
        logger.info("🎉 All eBPF objects loaded successfully!")
        loader.list_loaded_programs()
        sys.exit(0)
    else:
        logger.error("❌ Failed to load some eBPF objects")
        sys.exit(1)

if __name__ == "__main__":
    main() 