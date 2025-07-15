"""cpu_plugins.core.interfaces

Định nghĩa giao diện plugin cho cpu_plugins.
"""
from __future__ import annotations

from typing import Protocol, Dict, Any, runtime_checkable


@runtime_checkable
class ICpuTechnique(Protocol):
    """Giao diện tối thiểu cho các plugin CPU."""

    # Tên duy nhất, dễ đọc (ví dụ: "adaptive_cloak")
    name: str
    
    # Giá trị thấp hơn => ưu tiên cao hơn (0 = critical)
    priority: int

    def init(self, engine: Any, config: Dict[str, Any] | None = None) -> bool:
        """Được gọi một lần sau khi đối tượng plugin được tạo."""
        ...

    def apply(self, pid: int) -> bool:
        """Áp dụng kỹ thuật cho một PID cụ thể."""
        ...

    def stop(self) -> bool:
        """Giải phóng tài nguyên khi engine dừng."""
        ... 