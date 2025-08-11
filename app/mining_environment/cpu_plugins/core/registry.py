"""cpu_plugins.core.registry

Quản lý đăng ký và khám phá plugin.
"""
from __future__ import annotations

import logging
import threading
from typing import List, Dict, Any, Type, Optional

from .interfaces import ICpuTechnique
from .config import CpuPluginConfig, PluginConfig


# **Registry** (sổ đăng ký) lưu trữ trong **memory** (bộ nhớ) - thay thế bằng **entry-points** (điểm vào) trong tương lai
_plugin_registry: Dict[str, Type[ICpuTechnique]] = {}


class PluginRegistry:
    """
    Lớp đăng ký plugin mới, cung cấp API interface cho các plugin monitoring
    """
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, logger: Optional[logging.Logger] = None):
        # Chỉ **initialize** (khởi tạo) một lần, ngay cả khi **__new__** được gọi nhiều lần
        if getattr(self, "_initialized", False):
            return
            
        self.logger = logger or logging.getLogger(__name__)
        self._plugins: Dict[str, Any] = {}
        self._status_listeners = []
        self._initialized = True

    @classmethod
    def get_instance(cls):
        """Trả về instance hiện tại của PluginRegistry."""
        if cls._instance is None:
            return cls()
        return cls._instance

    def register(self, plugin_name: str, plugin_instance: Any) -> None:
        """Đăng ký một instance plugin vào registry."""
        self._plugins[plugin_name] = plugin_instance
        self.logger.debug(f"Plugin '{plugin_name}' đã được đăng ký.")

    def unregister(self, plugin_name: str) -> None:
        """Hủy đăng ký một plugin khỏi registry."""
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            self.logger.debug(f"Plugin '{plugin_name}' đã bị hủy đăng ký.")

    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        """Lấy instance plugin từ registry."""
        return self._plugins.get(plugin_name)

    def get_all_plugins(self) -> Dict[str, Any]:
        """Lấy tất cả các instance plugin đã đăng ký."""
        return self._plugins.copy()
        
    def add_status_listener(self, callback) -> None:
        """Thêm một callback lắng nghe sự thay đổi trạng thái plugin."""
        if callback not in self._status_listeners:
            self._status_listeners.append(callback)
            
    def notify_status_change(self, plugin_name: str, status: Dict[str, Any]) -> None:
        """Thông báo sự thay đổi trạng thái cho tất cả listeners."""
        for listener in self._status_listeners:
            try:
                listener(plugin_name, status)
            except Exception as e:
                self.logger.error(f"Lỗi khi gọi status listener cho '{plugin_name}': {e}")


def register_plugin(name: str = None):
    """Decorator để đăng ký một lớp plugin.
    
    Args:
        name: Tên tùy chọn cho plugin. Nếu không cung cấp, sẽ sử dụng tên lớp.
    """
    def decorator(cls: Type[ICpuTechnique]):
        plugin_name = name or getattr(cls, "name", cls.__name__).lower()
        _plugin_registry[plugin_name] = cls
        return cls
    return decorator


def discover_plugins(
    engine: Any,
    logger: Optional[logging.Logger] = None,
    config: Optional[CpuPluginConfig] = None
) -> List[ICpuTechnique]:
    """Khởi tạo và sắp xếp plugin theo độ ưu tiên với bộ lọc cấu hình.
    
    Args:
        engine: Engine để truyền vào phương thức init của plugin.
        logger: Logger tùy chọn.
        config: Cấu hình tùy chọn.
        
    Returns:
        Danh sách các plugin đã khởi tạo, sắp xếp theo độ ưu tiên.
    """
    logger = logger or logging.getLogger(__name__)
    config_map = {p.name: p for p in config.plugins} if config else {}
    
    instances: List[ICpuTechnique] = []
    
    for plugin_name, plugin_cls in _plugin_registry.items():
        plugin_config = config_map.get(plugin_name)
        
        # **Skip** (bỏ qua) nếu **YAML** **disabled** (vô hiệu hóa)
        if plugin_config and not plugin_config.enabled:
            logger.info(f"[**[CPU]** (bộ xử lý trung tâm)] Plugin {plugin_name} bị vô hiệu hóa qua YAML")
            continue
        
        try:
            plugin_obj = plugin_cls()
            
            # **Pass** (truyền) **config dict** (từ điển cấu hình) nếu có
            config_dict = plugin_config.config if plugin_config else None
            success = plugin_obj.init(engine, config_dict)
            
            if not success:
                logger.warning(f"[**[CPU]** (bộ xử lý trung tâm)] Khởi tạo plugin {plugin_name} không thành công")
                continue
                
            # **Update priority** (cập nhật độ ưu tiên) nếu có trong **configuration** (cấu hình)
            if plugin_config:
                plugin_obj.priority = plugin_config.priority
                
            instances.append(plugin_obj)
            logger.info(f"[**[CPU]** (bộ xử lý trung tâm)] Đã tải plugin: {plugin_obj.name} (ưu tiên={plugin_obj.priority})")
            
            # --- **Auto wrap methods** (tự động bọc phương thức) với **detailed logging** (ghi nhật ký chi tiết) ---
            try:
                from ..utils.logging_decorator import log_feature  # type: ignore

                def _wrap_method(method_name: str, category: str):
                    if hasattr(plugin_obj, method_name):
                        original = getattr(plugin_obj, method_name)
                        # tránh **double wrapping** (bọc hai lần)
                        if not getattr(original, "_is_wrapped", False):
                            wrapped = log_feature(category)(original)
                            wrapped._is_wrapped = True  # type: ignore
                            setattr(plugin_obj, method_name, wrapped)

                category = "CPU Cloaking" if ".cloaking." in plugin_cls.__module__ else "CPU Optimization"
                for m in ("init", "apply", "stop"):
                    _wrap_method(m, category)
            except Exception as _wrap_exc:
                logger.debug(f"Không thể auto-wrap **[logging]** (ghi nhật ký) cho {plugin_name}: {_wrap_exc}")
            
        except Exception as exc:
            logger.warning(f"[**[CPU]** (bộ xử lý trung tâm)] Bỏ qua plugin {plugin_name} - khởi tạo thất bại: {exc}")
    
    # **Sort** (sắp xếp) theo **priority** (độ ưu tiên) tăng dần
    instances.sort(key=lambda p: p.priority)
    return instances


def get_plugin_registry() -> Dict[str, Type[ICpuTechnique]]:
    """Trả về registry hiện tại."""
    return _plugin_registry.copy() 