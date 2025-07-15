from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Callable, Dict, Any, List, DefaultDict


class EventBus:
    """Event bus đơn giản, thread-safe.

    • Đảm bảo mọi *data* gửi qua ``publish`` là ``dict`` (theo contract).
    • Gọi callback đồng bộ; nếu callback raise Exception sẽ được log nhưng không
      chặn các callback khác.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._subscribers: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def subscribe(self, event: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký *callback* cho *event*.

        Có thể đăng ký nhiều callback cho cùng một event; tránh trùng lặp.
        """
        with self._lock:
            if callback not in self._subscribers[event]:
                self._subscribers[event].append(callback)

    def publish(self, event: str, data: Dict[str, Any]) -> None:  # noqa: D401
        """Gửi sự kiện tới tất cả subscribers.

        Raises:
            TypeError: Nếu *data* không phải ``dict``.
        """
        if not isinstance(data, dict):
            raise TypeError("EventBus data must be dict")

        callbacks: List[Callable[[Dict[str, Any]], None]]
        with self._lock:
            callbacks = list(self._subscribers.get(event, []))

        # Gọi callback ngoài lock để tránh deadlock.
        for cb in callbacks:
            try:
                cb(data)
            except Exception as exc:  # noqa: BLE001
                # Ghi log kèm traceback mà không chặn các callback khác
                self._logger.error(
                    "Lỗi khi gọi callback cho event '%s': %s", event, exc, exc_info=True
                )

    # API giữ chỗ để tương thích ─ hiện không cần loop background
    def start_listening(self) -> None:  # noqa: D401
        """Không cần implement; giữ để tương thích."""

    def stop(self) -> None:  # noqa: D401
        """Huỷ subscribe tất cả callbacks."""
        with self._lock:
            self._subscribers.clear()
