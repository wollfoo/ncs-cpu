"""
**[System Facade]** (giao diện hệ thống - giao diện quản lý hệ thống thống nhất)
Cung cấp **[Simplified Interface]** (giao diện đơn giản hóa) cho **[System Operations]** (thao tác hệ thống) và **[Resource Management]** (quản lý tài nguyên)
"""

import logging
import time
import threading
from typing import Dict, Any, Optional
from .auxiliary_modules.event_bus import EventBus
from .auxiliary_modules.models import ConfigModel
from .resource_manager import ResourceManager


class SystemFacade:
    """
    **[Unified System Management Facade]** (facade quản lý hệ thống thống nhất)
    Cung cấp **[Simplified Interface]** (giao diện đơn giản hóa) cho **[System Operations]** (thao tác hệ thống) và **[Resource Management]** (quản lý tài nguyên)
    """
    
    def __init__(self, config: ConfigModel, event_bus: EventBus, resource_logger: logging.Logger):
        """
        Khởi tạo **[SystemFacade]** (facade hệ thống) với **[Configuration]** (cấu hình) và **[Event Bus]** (bus sự kiện)
        
        Args:
            config: **[System Configuration Model]** (mô hình cấu hình hệ thống)
            event_bus: **[Event Bus]** (bus sự kiện) cho **[System-wide Communication]** (giao tiếp toàn hệ thống)
            resource_logger: **[Logger]** (bộ ghi log) cho **[Resource Management]** (quản lý tài nguyên)
        """
        self.config = config
        self.event_bus = event_bus
        self.resource_logger = resource_logger
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # **[System State Tracking]** (theo dõi trạng thái hệ thống)
        self.system_state = {
            'initialized': False,
            'status': 'starting',
            'resources': {},
            'performance': {}
        }
        
        # Khởi tạo **[ResourceManager Instance]** (thực thể ResourceManager)
        self.resource_manager = None
        self.resource_manager_thread = None
        
        self.logger.info("**[SystemFacade]** (facade hệ thống) đã được khởi tạo")
    
    def initialize_system(self) -> bool:
        """
        Khởi tạo **[System Components]** (thành phần hệ thống) bao gồm **[ResourceManager]** (trình quản lý tài nguyên)
        
        Returns:
            bool: True nếu khởi tạo thành công
        """
        try:
            self.logger.info("🔧 Đang khởi tạo **[System Components]** (thành phần hệ thống)...")
            
            # Khởi tạo **[ResourceManager]** (trình quản lý tài nguyên)
            init_msg = "🚀 Initializing ResourceManager through SystemFacade..."
            self.logger.info(init_msg)
            self.resource_logger.info(init_msg)
            
            # Tạo **[ResourceManager Instance]** (thực thể ResourceManager)
            progress_msg = "📋 Step 1/4: Creating ResourceManager instance..."
            self.logger.info(progress_msg)
            self.resource_logger.info(progress_msg)
            self.resource_manager = ResourceManager(self.config, self.event_bus, self.resource_logger)
            
            # Khởi động **[ResourceManager]** trong **[Separate Thread]** (luồng riêng biệt - không chặn)
            progress_msg = "📋 Step 2/4: Starting ResourceManager thread..."
            self.logger.info(progress_msg)
            self.resource_logger.info(progress_msg)
            self.resource_manager_thread = threading.Thread(
                target=self.resource_manager.start,
                daemon=True,
                name="ResourceManagerThread"
            )
            self.resource_manager_thread.start()
            
            # Chờ với **[Progress Updates]** (cập nhật tiến độ) để **[ResourceManager]** khởi tạo
            progress_msg = "📋 Step 3/4: Waiting for ResourceManager initialization..."
            self.logger.info(progress_msg)
            self.resource_logger.info(progress_msg)
            
            # Chờ với **[Progress Logging]** (ghi log tiến độ - tối đa 35 giây với cập nhật tiến độ)
            max_wait_time = 35
            check_interval = 5
            waited_time = 0
            
            while waited_time < max_wait_time:
                time.sleep(check_interval)
                waited_time += check_interval
                
                if self.resource_manager_thread.is_alive():
                    progress_msg = f"⏳ ResourceManager initialization progress: {waited_time}/{max_wait_time}s elapsed..."
                    self.logger.info(progress_msg)
                    self.resource_logger.info(progress_msg)
                else:
                    break
            
            # Xác minh **[ResourceManager]** đang chạy
            progress_msg = "📋 Step 4/4: Verifying ResourceManager status..."
            self.logger.info(progress_msg)
            self.resource_logger.info(progress_msg)
            
            if self.resource_manager_thread.is_alive():
                success_msg = "✅ ResourceManager started successfully in background thread"
                self.logger.info(success_msg)
                self.resource_logger.info(success_msg)
            else:
                raise RuntimeError("ResourceManager thread failed to start")
            
            # Khởi tạo **[System State]** (trạng thái hệ thống)
            self.system_state['initialized'] = True
            self.system_state['status'] = 'ready'
            
            # Phát **[Initialization Event]** (sự kiện khởi tạo)
            self.event_bus.publish('system.initialized', {
                'timestamp': time.time(),
                'status': 'ready',
                'resource_manager_active': True
            })
            
            self.logger.info("✅ Khởi tạo **[System]** (hệ thống) hoàn tất thành công")
            return True
            
        except Exception as e:
            error_msg = f"❌ System initialization failed: {e}"
            self.logger.error(error_msg)
            self.resource_logger.error(error_msg)
            self.system_state['status'] = 'error'
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Lấy **[Current System Status]** (trạng thái hệ thống hiện tại)
        
        Returns:
            Dict chứa **[System Status Information]** (thông tin trạng thái hệ thống)
        """
        return {
            'state': self.system_state,
            'config': self.config.to_dict() if hasattr(self.config, 'to_dict') else str(self.config),
            'timestamp': time.time()
        }
    
    def shutdown_system(self) -> bool:
        """
        Tắt **[System Components]** (thành phần hệ thống) một cách **[Gracefully]** (nhẹ nhàng) bao gồm **[ResourceManager]** (trình quản lý tài nguyên)
        
        Returns:
            bool: True nếu tắt thành công
        """
        try:
            self.logger.info("🛑 Đang tắt **[System Components]** (thành phần hệ thống)...")
            
            # Cập nhật **[System State]** (trạng thái hệ thống)
            self.system_state['status'] = 'shutting_down'
            
            # Tắt **[ResourceManager]** (trình quản lý tài nguyên)
            if self.resource_manager:
                shutdown_msg = "🛑 Shutting down ResourceManager..."
                self.logger.info(shutdown_msg)
                self.resource_logger.info(shutdown_msg)
                
                try:
                    self.resource_manager.shutdown()
                    
                    # Chờ **[ResourceManager Thread]** (luồng ResourceManager) hoàn tất
                    if self.resource_manager_thread and self.resource_manager_thread.is_alive():
                        self.resource_manager_thread.join(timeout=10)
                        
                    success_msg = "✅ ResourceManager shutdown completed"
                    self.logger.info(success_msg)
                    self.resource_logger.info(success_msg)
                    
                except Exception as e:
                    error_msg = f"❌ ResourceManager shutdown error: {e}"
                    self.logger.error(error_msg)
                    self.resource_logger.error(error_msg)
            
            # Phát **[Shutdown Event]** (sự kiện tắt)
            self.event_bus.publish('system.shutdown', {
                'timestamp': time.time(),
                'status': 'shutting_down'
            })
            
            # Dọn dẹp **[Resources]** (tài nguyên)
            self.system_state['initialized'] = False
            self.system_state['status'] = 'stopped'
            
            self.logger.info("✅ Tắt **[System]** (hệ thống) hoàn tất thành công")
            return True
            
        except Exception as e:
            error_msg = f"❌ System shutdown failed: {e}"
            self.logger.error(error_msg)
            self.resource_logger.error(error_msg)
            return False
    
    def get_resource_status(self) -> Dict[str, Any]:
        """
        Lấy **[Current Resource Utilization Status]** (trạng thái sử dụng tài nguyên hiện tại)
        
        Returns:
            Dict chứa **[Resource Status Information]** (thông tin trạng thái tài nguyên)
        """
        return {
            'resources': self.system_state.get('resources', {}),
            'performance': self.system_state.get('performance', {}),
            'timestamp': time.time()
        }
    
    def update_resource_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Cập nhật **[Resource Metrics]** (số liệu tài nguyên)
        
        Args:
            metrics: **[Resource Metrics]** (số liệu tài nguyên) cần cập nhật
        """
        if 'resources' not in self.system_state:
            self.system_state['resources'] = {}
        
        self.system_state['resources'].update(metrics)
        
        # Ghi log **[Resource Update]** (cập nhật tài nguyên)
        self.resource_logger.info(f"**[Resource Metrics]** (số liệu tài nguyên) đã cập nhật: {metrics}")
        
        # Phát **[Resource Update Event]** (sự kiện cập nhật tài nguyên)
        self.event_bus.publish('system.resource_update', {
            'metrics': metrics,
            'timestamp': time.time()
        })
    
    def start(self) -> bool:
        """
        Khởi động SystemFacade và các components
        
        Returns:
            bool: True nếu khởi động thành công
        """
        try:
            # Ghi log vào cả **[Console]** (bảng điều khiển) và **[File]** (tệp)
            start_msg = "🚀 Starting SystemFacade..."
            self.logger.info(start_msg)
            print(f"[INFO] {start_msg}")
            
            # Khởi tạo **[System Components]** (thành phần hệ thống)
            if not self.initialize_system():
                error_msg = "❌ Failed to initialize system components"
                self.logger.error(error_msg)
                print(f"[ERROR] {error_msg}")
                return False
            
            # Cập nhật **[System State]** (trạng thái hệ thống)
            self.system_state['status'] = 'running'
            
            # Phát **[Start Event]** (sự kiện khởi động)
            self.event_bus.publish('system.started', {
                'timestamp': time.time(),
                'status': 'running'
            })
            
            success_msg = "✅ SystemFacade started successfully"
            self.logger.info(success_msg)
            print(f"[INFO] {success_msg}")
            return True
            
        except Exception as e:
            error_msg = f"❌ SystemFacade start failed: {e}"
            self.logger.error(error_msg)
            print(f"[ERROR] {error_msg}")
            self.system_state['status'] = 'error'
            return False

    def stop(self) -> bool:
        """
        Dừng SystemFacade
        
        Returns:
            bool: True nếu dừng thành công
        """
        try:
            stop_msg = "🛑 Stopping SystemFacade..."
            self.logger.info(stop_msg)
            print(f"[INFO] {stop_msg}")
            
            result = self.shutdown_system()
            
            if result:
                success_msg = "✅ SystemFacade stopped successfully"
                self.logger.info(success_msg)
                print(f"[INFO] {success_msg}")
            else:
                error_msg = "❌ SystemFacade stop failed"
                self.logger.error(error_msg)
                print(f"[ERROR] {error_msg}")
            
            return result
            
        except Exception as e:
            error_msg = f"❌ SystemFacade stop error: {e}"
            self.logger.error(error_msg)
            print(f"[ERROR] {error_msg}")
            return False