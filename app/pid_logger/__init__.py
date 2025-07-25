"""pid_logger package (relocated vào app)

Enhanced PID Logger với Real Process Output Monitor.

API:
    - start_worker(): khởi động enhanced worker threads.
    - log_pid(pid, is_cpu): ghi một PID (legacy API).
    - register_process(pid, process_type, process_obj, process_name): đăng ký process để monitor runtime output.
"""

from .worker import start_worker, log_pid, register_process
