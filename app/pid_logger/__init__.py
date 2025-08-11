"""**pid_logger package** (gói pid_logger – được chuyển vào app)

**Enhanced PID Logger** (trình ghi PID nâng cao) với **Real Process Output Monitor** (bộ giám sát đầu ra tiến trình thực).

**API** (giao diện lập trình ứng dụng):
    - **start_worker()**: khởi động **enhanced worker threads** (các luồng worker nâng cao).
    - **log_pid(pid, is_cpu)**: ghi một **PID** (mã định danh tiến trình) (**legacy API** – giao diện lập trình cũ).
    - **register_process(pid, process_type, process_obj, process_name)**: đăng ký **process** (tiến trình) để **monitor runtime output** (giám sát đầu ra thời gian chạy).
    
**Debug API** (giao diện lập trình gỡ lỗi):
    - **debug_registry_status()**: hiển thị trạng thái **process registry** (sổ đăng ký tiến trình).
    - **force_test_output(test_pid, test_type)**: kiểm thử **output format** (định dạng đầu ra).
    - **manual_register_real_pids()**: **manual registration** (đăng ký thủ công) của **real mining PIDs** (PID khai thác thực).
"""

from .worker import start_worker, log_pid, register_process, debug_registry_status, force_test_output, manual_register_real_pids, _WORKER_STARTED, _PROCESS_REGISTRY, force_restart_worker
