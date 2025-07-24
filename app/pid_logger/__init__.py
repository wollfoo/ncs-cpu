"""pid_logger package (relocated vào app)

API:
    - start_worker(): khởi động worker thread ghi PID.
    - log_pid(pid, is_cpu): ghi một PID.
"""

from .worker import start_worker, log_pid
