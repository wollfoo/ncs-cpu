"""cpu_plugins.utils.logging_decorator

Decorator hỗ trợ ghi log chi tiết cho mỗi lần kích hoạt tính năng CPU.
Tuân thủ yêu cầu:
  • Ghi timestamp, execution context, performance metrics, stack trace
  • Sử dụng log levels phù hợp
  • Xử lý lỗi graceful degradation & rollback nếu phương thức target có thuộc tính `_rollback` hoặc object có `rollback()`

Sử dụng:

    from cpu_plugins.utils.logging_decorator import log_feature

    @log_feature(category="CPU Optimization")
    def apply(self, pid: int):
        ...

Tuy nhiên để tránh sửa hàng loạt plugin, registry sẽ tự động bọc các phương thức quan trọng
(`init`, `apply`, `stop`) khi khởi tạo plugin.
"""
from __future__ import annotations

import functools
import logging
import time
import traceback
from typing import Callable, Any, Dict

LOGGER = logging.getLogger("cpu_feature_logger")

# Thiết lập handler mặc định ghi vào app/mining_environment/logs/cpu_features.log
try:
    from pathlib import Path

    LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = LOG_DIR / "cpu_features.log"

    if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == str(log_file_path) for h in LOGGER.handlers):
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)

    # Luôn log ra console ở mức INFO để tiện debug nhanh
    if not any(isinstance(h, logging.StreamHandler) for h in LOGGER.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        LOGGER.addHandler(console_handler)
    LOGGER.setLevel(logging.DEBUG)
except Exception as _init_exc:  # noqa: BLE001
    # Nếu có lỗi khi thiết lập file handler, ghi ra stderr
    logging.basicConfig(level=logging.DEBUG)
    LOGGER.error(f"Không thể thiết lập file handler cho cpu_feature_logger: {_init_exc}")


def _build_context(func: Callable, args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Tạo execution context thân thiện JSON."""
    context: Dict[str, Any] = {
        "function": func.__name__,
        "args": args[:4],  # tránh log quá dài
        "kwargs": {k: kwargs[k] for k in list(kwargs)[:4]},
    }
    try:
        # Nếu self có thuộc tính name/priority ⇒ plugin
        if args and hasattr(args[0], "name"):
            context["plugin"] = getattr(args[0], "name", type(args[0]).__name__)
    except Exception:
        pass
    return context


def log_feature(category: str):
    """Decorator factory bọc phương thức với logging & error-handling.

    Args:
        category: "CPU Optimization" | "CPU Cloaking" ...
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            timestamp = time.time()
            ctx = _build_context(func, args, kwargs)
            LOGGER.debug(f"[{category}] BẮT ĐẦU {func.__name__} – ctx={ctx} – ts={timestamp}")
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000.0  # ms
                LOGGER.info(
                    f"[{category}] HOÀN THÀNH {func.__name__} – {duration:.2f} ms – ctx={ctx}")
                return result
            except Exception as exc:  # noqa: BLE001
                duration = (time.perf_counter() - start) * 1000.0
                LOGGER.error(
                    f"[{category}] LỖI {func.__name__} – {duration:.2f} ms – ctx={ctx} – err={exc}")
                LOGGER.debug("STACKTRACE:\n" + traceback.format_exc())
                # Graceful degradation / rollback
                target_obj = args[0] if args else None
                if target_obj is not None:
                    rollback_fn = getattr(target_obj, "rollback", None)
                    if callable(rollback_fn):
                        try:
                            rollback_fn()
                            LOGGER.warning(f"[{category}] ĐÃ ROLLBACK sau lỗi {func.__name__}")
                        except Exception as rb_exc:  # noqa: BLE001
                            LOGGER.error(f"Rollback thất bại: {rb_exc}")
                # Trả về False nếu hàm gốc có kiểu trả về bool, ngược lại raise lại
                if hasattr(func, "__annotations__") and func.__annotations__.get("return") == bool:
                    return False
                raise
        return wrapper

    return decorator 