"""**[CPU Plugins Core Interfaces]** (giao diện cốt lõi plugin CPU)

Định nghĩa **[Plugin Interface]** (giao diện plugin) cho **[CPU Plugins]** (plugin CPU).
"""
from __future__ import annotations

from typing import Protocol, Dict, Any, runtime_checkable


@runtime_checkable
class ICpuTechnique(Protocol):
    """**[Minimal Interface]** (giao diện tối thiểu) cho **[CPU Plugins]** (các plugin CPU)."""

    # **[Unique Name]** (tên duy nhất), dễ đọc (ví dụ: "adaptive_cloak")
    name: str
    
    # Giá trị thấp hơn => **[Higher Priority]** (ưu tiên cao hơn) (0 = **[Critical]** (nghiêm trọng))
    priority: int

    def init(self, engine: Any, config: Dict[str, Any] | None = None) -> bool:
        """Được gọi một lần sau khi **[Plugin Object]** (đối tượng plugin) được tạo."""
        ...

    def apply(self, pid: int) -> bool:
        """Áp dụng **[Technique]** (kỹ thuật) cho một **[PID]** (ID tiến trình) cụ thể."""
        ...

    def stop(self) -> bool:
        """Giải phóng **[Resources]** (tài nguyên) khi **[Engine]** (bộ máy) dừng."""
        ... 