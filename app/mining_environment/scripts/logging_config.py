# logging_config.py

import os
import sys
import logging
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Giảm cảnh báo linter: chỉ import cryptography khi kiểm tra kiểu
if TYPE_CHECKING:
    from cryptography.fernet import Fernet  # pragma: no cover
else:
    try:
        from cryptography.fernet import Fernet  # type: ignore
    except ImportError:  # Library có thể chưa cài khi static check
        Fernet = Any  # type: ignore
import random
import string
from contextvars import ContextVar
from typing import Optional


###############################################################################
#                           ĐỊNH NGHĨA CORRELATION ID                        #
###############################################################################
# Định nghĩa một ContextVar để lưu trữ Correlation ID cho mỗi ngữ cảnh (context).
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='unknown')


###############################################################################
#                           CLASS: CorrelationIdFilter                       #
###############################################################################
class CorrelationIdFilter(logging.Filter):
    """
    Bộ lọc logging để thêm Correlation ID vào mỗi bản ghi log.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Thêm Correlation ID vào bản ghi log.
        
        Args:
            record (logging.LogRecord): Bản ghi log hiện tại.
        
        Returns:
            bool: Luôn trả về True để cho phép bản ghi log được xử lý.
        """
        record.correlation_id = correlation_id.get()
        return True


###############################################################################
#             CLASS: ObfuscatedEncryptedFileHandler (có tích hợp xoá file)   #
###############################################################################
class ObfuscatedEncryptedFileHandler(logging.Handler):
    """
    Custom logging handler để mã hóa và làm rối các log trước khi ghi vào tệp.
    Đồng thời tự động xóa file log khi dung lượng vượt quá ngưỡng cho phép.
    """
    def __init__(
        self,
        filename: str,
        fernet: Any,
        level: int = logging.NOTSET,
        max_file_size: int = 50 * 1024 * 1024  # 50MB mặc định
    ):
        """
        Khởi tạo ObfuscatedEncryptedFileHandler.
        
        Args:
            filename (str): Đường dẫn đến tệp log.
            fernet (Fernet): Đối tượng Fernet để mã hóa log.
            level (int, optional): Mức độ log để xử lý. Mặc định là NOTSET.
            max_file_size (int, optional): Ngưỡng dung lượng (byte) để tự động
                                           xóa log. Mặc định là 50MB.
        """
        super().__init__(level)
        self.filename = filename
        self.fernet = fernet
        self.max_file_size = max_file_size

        # Đảm bảo thư mục cha tồn tại
        file_parent = Path(filename).parent
        file_parent.mkdir(parents=True, exist_ok=True)

        # Mở file ở chế độ 'ab' (append-binary)
        self.file = open(self.filename, 'ab')

    def emit(self, record: logging.LogRecord):
        """
        Xử lý và ghi bản ghi log vào tệp sau khi mã hóa và làm rối.
        Đồng thời kiểm tra kích thước file, nếu vượt quá max_file_size thì xóa luôn.
        
        Args:
            record (logging.LogRecord): Bản ghi log cần xử lý.
        """
        try:
            # Format message
            msg = self.format(record)
            # Thêm chuỗi ngẫu nhiên để làm rối
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            obfuscated_msg = f"{msg} {random_suffix}"

            # Mã hóa thông điệp
            encrypted_msg = self.fernet.encrypt(obfuscated_msg.encode('utf-8'))

            # Ghi vào tệp (dạng nhị phân, thêm newline)
            self.file.write(encrypted_msg + b'\n')
            self.file.flush()

            # Kiểm tra kích thước file, nếu vượt ngưỡng thì xóa file, tạo lại
            self._check_file_size()
        except Exception:
            self.handleError(record)

    def _check_file_size(self):
        """
        Kiểm tra và xóa file nếu kích thước > self.max_file_size.
        """
        current_size = self.file.tell()  # Vị trí con trỏ => kích thước file hiện tại
        if current_size > self.max_file_size:
            self.file.close()
            os.remove(self.filename)
            # Tạo lại file rỗng
            self.file = open(self.filename, 'ab')

    def close(self):
        """
        Đóng tệp log khi handler được đóng.
        """
        if not self.file.closed:
            self.file.close()
        super().close()


###############################################################################
#                           FUNCTION: setup_logging                          #
###############################################################################
# def setup_logging(module_name: str, log_file: str, log_level: str = 'INFO', **kwargs) -> Logger:
#     """
#     Thiết lập logger cho module, hỗ trợ mã hóa log bằng ObfuscatedEncryptedFileHandler
#     (có tính năng xóa file nếu vượt dung lượng) và thêm Correlation ID vào mỗi bản ghi log.
    
#     Args:
#         module_name (str): Tên module (tên logger).
#         log_file (str): Đường dẫn đến tệp log.
#         log_level (str, optional): Mức log (DEBUG, INFO, WARN, ERROR...). Mặc định là 'INFO'.
    
#     Returns:
#         Logger: Đối tượng logger đã được thiết lập.
#     """
#     logger = logging.getLogger(module_name)
#     # Lấy log_level an toàn bằng getattr
#     safe_log_level = getattr(logging, log_level.upper(), logging.INFO)
#     logger.setLevel(safe_log_level)
    
#     # Kiểm tra xem có đang trong môi trường kiểm thử hay không
#     in_test = "TESTING" in os.environ
#     if in_test:
#         logger.propagate = True
#         print("Logger propagate set to True for testing mode.")
#     else:
#         # Không propagate nếu không phải test
#         logger.propagate = False

#     # Nếu logger chưa có handler nào, ta thêm
#     if not logger.handlers:
#         if in_test:
#             print("Skip adding file handlers due to testing mode.")
#             return logger

#         # Đảm bảo thư mục log tồn tại
#         log_path = Path(log_file).parent
#         log_path.mkdir(parents=True, exist_ok=True)

#         # Lấy khóa mã hóa từ biến môi trường hoặc tự tạo mới
#         encryption_key = os.getenv('LOG_ENCRYPTION_KEY')
#         if not encryption_key:
#             encryption_key = Fernet.generate_key().decode()
#             os.environ['LOG_ENCRYPTION_KEY'] = encryption_key
#             print(f"Đã tạo khóa mã hóa mới: {encryption_key} (hãy lưu lại để sử dụng tiếp).")

#         # Khởi tạo đối tượng Fernet
#         try:
#             fernet = Fernet(encryption_key.encode())
#         except Exception as e:
#             print(f"Lỗi khi tạo Fernet với khóa mã hóa: {e}", file=sys.stderr)
#             return logger

#         # Tạo handler mã hóa (tích hợp xóa file nếu vượt 50MB)
#         # - Có thể tuỳ chỉnh max_file_size qua kwargs
#         max_file_size = kwargs.get('max_file_size', 50 * 1024 * 1024)
#         encrypted_handler = ObfuscatedEncryptedFileHandler(
#             filename=log_file,
#             fernet=fernet,
#             level=safe_log_level,
#             max_file_size=max_file_size
#         )
#         formatter = logging.Formatter(
#             '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
#         )
#         encrypted_handler.setFormatter(formatter)
#         # Thêm CorrelationIdFilter vào handler
#         encrypted_handler.addFilter(CorrelationIdFilter())
#         logger.addHandler(encrypted_handler)

#         # Thêm StreamHandler (log ra console)
#         stream_handler = logging.StreamHandler(sys.stdout)
#         stream_handler.setLevel(safe_log_level)
#         stream_formatter = logging.Formatter(
#             '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
#         )
#         stream_handler.setFormatter(stream_formatter)
#         # Thêm CorrelationIdFilter
#         stream_handler.addFilter(CorrelationIdFilter())
#         logger.addHandler(stream_handler)

#     return logger


def setup_logging(module_name: str, log_file: str, log_level: str = 'INFO', **kwargs) -> Logger:
    """
    Thiết lập logger cho module với MemoryHandler + RotatingFileHandler
    để đảm bảo flush tự động và quản lý file lâu dài.
    
    Args:
        module_name (str): Tên module (tên logger).
        log_file (str): Đường dẫn đến tệp log.
        log_level (str, optional): Mức log (DEBUG, INFO, WARN, ERROR...). Mặc định là 'INFO'.
    
    Returns:
        Logger: Đối tượng logger đã được thiết lập.
    """
    from logging.handlers import MemoryHandler, RotatingFileHandler
    
    logger = logging.getLogger(module_name)
    safe_log_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(safe_log_level)

    # Kiểm tra xem có đang trong môi trường kiểm thử hay không
    in_test = "TESTING" in os.environ
    logger.propagate = in_test

    # Nếu logger chưa có handler nào, ta thêm
    if not logger.handlers:
        # Đảm bảo thư mục log tồn tại
        log_path = Path(log_file).parent
        log_path.mkdir(parents=True, exist_ok=True)

        # RotatingFileHandler để tự động rotate file khi > 10MB
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(safe_log_level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(CorrelationIdFilter())

        # MemoryHandler để buffer và flush tự động
        memory_handler = MemoryHandler(
            capacity=1,  # Flush sau 1 bản ghi (CPU-only)
            target=file_handler,
            flushLevel=logging.INFO  # Force flush khi có INFO+ (thay vì WARNING+)
        )
        memory_handler.addFilter(CorrelationIdFilter())
        
        logger.addHandler(memory_handler)

        # StreamHandler cho console với flush tự động
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(safe_log_level)
        stream_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
        )
        stream_handler.setFormatter(stream_formatter)
        stream_handler.addFilter(CorrelationIdFilter())
        logger.addHandler(stream_handler)

    return logger




