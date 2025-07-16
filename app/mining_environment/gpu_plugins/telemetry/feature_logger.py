"""gpu_feature_logger.py
Bộ trợ giúp ghi nhật ký JSON một dòng cho các tính năng GPU (Optimization & Cloaking).
Tuân thủ quy định:
  • Log JSON gồm timestamp, feature, state, parameters, error_code, message.
  • Tự động tạo thư mục log `/app/mining_environment/logs` nếu cần.
  • Mức log lấy từ biến môi trường GPU_FEATURE_LOG_LEVEL (mặc định INFO).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Tên logger cố định để dễ thu thập
_LOGGER_NAME = "gpu_features"
_logger = logging.getLogger(_LOGGER_NAME)

if not _logger.handlers:
    # Thiết lập handler file + console (khi run foreground)
    log_dir = Path(os.getenv('LOGS_DIR', 'logs'))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback: thư mục hiện hành
        log_dir = Path.cwd()
    file_handler = logging.FileHandler(log_dir / "gpu_features.log")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(file_handler)

    # Console để debug nhanh
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(console_handler)

    # Cấp độ log
    level_str = os.getenv("GPU_FEATURE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    _logger.setLevel(level)


def _iso_timestamp() -> str:
    """Trả về thời gian UTC ISO-8601 (seconds precision)."""
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def log_gpu_feature(
    *,
    feature: str,
    state: str,
    parameters: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    message: str = "",
) -> None:
    """Ghi một bản ghi JSON cho sự kiện GPU.

    Args:
        feature: "gpu_optimization" | "gpu_cloaking".
        state: "enabled" | "disabled" | "updated" | "error".
        parameters: Dict tham số vận hành.
        error_code: Mã lỗi (None nếu thành công).
        message: Chuỗi mô tả ngắn tiếng Việt.
    """
    record = {
        "timestamp": _iso_timestamp(),
        "feature": feature,
        "state": state,
        "parameters": parameters or {},
        "error_code": error_code,
        "message": message,
    }
    _logger.info(json.dumps(record, ensure_ascii=False)) 