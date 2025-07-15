"""
Module facade.py

Cung cấp lớp SystemFacade để quản lý khởi động/dừng đồng bộ (synchronous)
các module chính của hệ thống: ResourceManager.
Loại bỏ hoàn toàn async/await và đảm bảo tương thích với resource_manager.py.
"""

import logging
import threading
from .resource_manager import ResourceManager
from .auxiliary_modules.event_bus import EventBus
from .auxiliary_modules.models import ConfigModel


class SystemFacade:
    """
    Lớp facade chịu trách nhiệm quản lý vòng đời (khởi động, dừng, khởi động lại)
    các module chính của hệ thống, gồm:
      - ResourceManager.

    Hoạt động theo mô hình đồng bộ (không dùng asyncio).
    """

    def __init__(self,
                 config: ConfigModel,
                 event_bus: EventBus,
                 resource_logger: logging.Logger):
        """
        Khởi tạo SystemFacade với các cấu hình và logger tương ứng.

        :param config: Đối tượng ConfigModel chứa cấu hình hệ thống.
        :param event_bus: Đối tượng EventBus để giao tiếp giữa các module.
        :param resource_logger: Logger cho ResourceManager.
        :raises RuntimeError: Nếu khởi tạo ResourceManager thất bại.
        """
        self.config = config
        self.event_bus = event_bus
        self.resource_logger = resource_logger

        # Khởi tạo ResourceManager (đồng bộ)
        try:
            self.resource_manager = ResourceManager(config, event_bus, self.resource_logger)
            if not self.resource_manager:
                raise RuntimeError("ResourceManager khởi tạo không thành công (None).")
            self.resource_logger.info("ResourceManager được khởi tạo thành công.")
        except Exception as e:
            self.resource_logger.error(f"Lỗi khi khởi tạo ResourceManager: {e}")
            raise RuntimeError("Không thể khởi tạo ResourceManager.") from e

    def start(self) -> None:
        """
        Khởi động đồng bộ các module trong hệ thống: ResourceManager.
        """
        self.resource_logger.info("Bắt đầu khởi động các module trong SystemFacade...")

        # ResourceManager
        try:
            self.resource_manager.start()
            self.resource_logger.info("ResourceManager đã khởi động thành công (đồng bộ).")
        except Exception as e:
            self.resource_logger.error(f"Lỗi khi khởi động ResourceManager: {e}")

    def stop(self) -> None:
        """
        Dừng đồng bộ tất cả các module: ResourceManager.
        """
        self.resource_logger.info("Dừng các module trong SystemFacade...")

        # ResourceManager
        try:
            self.resource_manager.shutdown()
            self.resource_logger.info("ResourceManager đã được dừng (đồng bộ), "
                                  "đảm bảo tất cả cloaking task đã xử lý xong.")
        except Exception as e:
            self.resource_logger.error(f"Lỗi khi dừng ResourceManager: {e}")

    def handle_shutdown(self) -> None:
        """
        Xử lý sự kiện shutdown: dừng tất cả các module.
        """
        self.resource_logger.info("Nhận sự kiện shutdown, đang dừng các module...")
        self.stop()

    def restart(self) -> None:
        """
        Khởi động lại (dừng + start) các module trong hệ thống (đồng bộ).
        """
        self.resource_logger.info("Đang khởi động lại các module (đồng bộ)...")
        self.stop()
        self.start()

    def register_shutdown_event(self) -> None:
        """
        Đăng ký sự kiện 'shutdown' từ EventBus => gọi handle_shutdown() (đồng bộ).
        """
        def shutdown_handler(data):
            try:
                self.handle_shutdown()
            except Exception as e:
                self.resource_logger.error(f"Lỗi khi xử lý sự kiện shutdown: {e}")

        try:
            self.event_bus.subscribe('shutdown', shutdown_handler)
            self.resource_logger.info("Đã đăng ký sự kiện shutdown (đồng bộ).")
        except Exception as e:
            self.resource_logger.error(f"Lỗi khi đăng ký sự kiện shutdown: {e}")
