"""
File Integrity Check - Kiểm tra tính toàn vẹn của file
Xác thực hash SHA256 trước khi load eBPF programs và native libraries
"""

import hashlib
import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class FileIntegrityChecker:
    """
    Kiểm tra tính toàn vẹn file bằng SHA256 hash
    Ngăn chặn tampering và unauthorized modifications
    """
    
    def __init__(self, 
                 manifest_path: str = "/app/security/file_hashes.json",
                 logger: Optional[logging.Logger] = None):
        self.manifest_path = Path(manifest_path)
        self.logger = logger or logging.getLogger(__name__)
        self.manifest = self._load_manifest()
        self.verification_cache = {}
        
    def _load_manifest(self) -> Dict[str, str]:
        """**Load** (tải) danh sách **hash** (mã băm) từ **manifest file** (tệp kê khai)"""
        if not self.manifest_path.exists():
            self.logger.warning(f"**Hash manifest** (tệp kê khai mã băm) not found at {self.manifest_path}")
            return {}
        
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)
            self.logger.info(f"**Loaded** (đã tải) {len(manifest)} **file hashes** (mã băm tệp) từ **manifest** (tệp kê khai)")
            return manifest
        except Exception as e:
            self.logger.error(f"**Failed to load** (không thể tải) **hash manifest** (tệp kê khai mã băm): {e}")
            return {}
    
    def calculate_file_hash(self, filepath: Path) -> str:
        """Tính **SHA256 hash** (mã băm SHA256) của **file** (tệp)"""
        sha256_hash = hashlib.sha256()
        
        try:
            with open(filepath, "rb") as f:
                # **Read file in chunks** (đọc tệp theo khối) để xử lý **large files** (tệp lớn)
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            return sha256_hash.hexdigest()
        
        except Exception as e:
            self.logger.error(f"**Failed to calculate hash** (không thể tính mã băm) cho {filepath}: {e}")
            raise
    
    def verify_file(self, filepath: Path) -> Tuple[bool, str]:
        """
        **Verify file** (xác thực tệp) với **hash** (mã băm) trong **manifest** (tệp kê khai)
        **Returns** (trả về): (is_valid, message)
        """
        filepath = Path(filepath)
        
        # Kiểm tra **cache** (bộ nhớ đệm) trước tiên
        if str(filepath) in self.verification_cache:
            cached_result = self.verification_cache[str(filepath)]
            if cached_result['timestamp'] > datetime.now().timestamp() - 3600:  # **1 hour cache** (bộ nhớ đệm 1 giờ)
                return cached_result['valid'], cached_result['message']
        
        # Lấy **expected hash** (mã băm dự kiến)
        expected_hash = self.manifest.get(str(filepath))
        if not expected_hash:
            message = f"Không tìm thấy **hash** (mã băm) trong **manifest** (tệp kê khai) cho {filepath}"
            self.logger.warning(message)
            return False, message
        
        # Tính **actual hash** (mã băm thực tế)
        try:
            actual_hash = self.calculate_file_hash(filepath)
        except Exception as e:
            message = f"**Failed to calculate hash** (không thể tính mã băm): {str(e)}"
            return False, message
        
        # So sánh **hashes** (mã băm)
        is_valid = actual_hash == expected_hash
        
        if is_valid:
            message = f"**File** (tệp) {filepath} **verified successfully** (xác thực thành công)"
            self.logger.info(message)
        else:
            message = f"**Hash mismatch** (mã băm không khớp) cho {filepath}: **expected** (dự kiến) {expected_hash}, **got** (nhận được) {actual_hash}"
            self.logger.error(message)
        
        # **Cache result** (lưu kết quả vào bộ nhớ đệm)
        self.verification_cache[str(filepath)] = {
            'valid': is_valid,
            'message': message,
            'timestamp': datetime.now().timestamp()
        }
        
        return is_valid, message
    
    def verify_critical_files(self) -> Dict[str, bool]:
        """**Verify** (xác thực) tất cả **critical files** (tệp quan trọng)"""
        critical_files = [
            # **CPU throttle eBPF** (eBPF điều chỉnh CPU) đã bị loại bỏ
            "../cpu_plugins/cloaking_lib/libcloak.so",
            "../cuda/libgpuhook.so"
        ]
        
        results = {}
        all_valid = True
        
        for filepath in critical_files:
            path = Path(filepath)
            if path.exists():
                is_valid, message = self.verify_file(path)
                results[filepath] = is_valid
                if not is_valid:
                    all_valid = False
                    self.logger.critical(f"**SECURITY** (bảo mật): **Critical file** (tệp quan trọng) **failed verification** (xác thực thất bại): {filepath}")
            else:
                results[filepath] = False
                self.logger.warning(f"**Critical file** (tệp quan trọng) **not found** (không tìm thấy): {filepath}")
        
        if not all_valid:
            self.logger.critical("**SECURITY ALERT** (cảnh báo bảo mật): Một hoặc nhiều **critical files** (tệp quan trọng) **failed integrity check** (kiểm tra tính toàn vẹn thất bại)!")
        
        return results
    
    def generate_manifest(self, directories: List[str], output_path: Optional[str] = None) -> Dict[str, str]:
        """
        **Generate hash manifest** (tạo tệp kê khai mã băm) cho các **files** (tệp) trong **directories** (thư mục)
        Dùng để tạo **manifest** (tệp kê khai) ban đầu hoặc **update** (cập nhật)
        """
        manifest = {}
        
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                self.logger.warning(f"**Directory** (thư mục) **not found** (không tìm thấy): {directory}")
                continue
            
            # Tìm tất cả **files** (tệp) **.so, .o, và .py**
            for pattern in ['*.so', '*.o', '*.py']:
                for filepath in dir_path.rglob(pattern):
                    try:
                        file_hash = self.calculate_file_hash(filepath)
                        manifest[str(filepath)] = file_hash
                        self.logger.info(f"**Hashed** (đã tạo mã băm) {filepath}: {file_hash}")
                    except Exception as e:
                        self.logger.error(f"**Failed to hash** (không thể tạo mã băm) {filepath}: {e}")
        
        # **Save manifest** (lưu tệp kê khai) nếu **output path** (đường dẫn đầu ra) được cung cấp
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(manifest, f, indent=2, sort_keys=True)
            self.logger.info(f"**Manifest** (tệp kê khai) **saved** (đã lưu) vào {output_path}")
        
        return manifest

# **Helper function** (hàm hỗ trợ) để **verify** (xác thực) trước khi **load** (tải)
def verify_before_load(filepath: str, checker: FileIntegrityChecker) -> bool:
    """
    **Verify file integrity** (xác thực tính toàn vẹn tệp) trước khi **load** (tải)
    **Throw exception** (ném ngoại lệ) nếu **verification fail** (xác thực thất bại)
    """
    is_valid, message = checker.verify_file(Path(filepath))
    
    if not is_valid:
        raise SecurityError(f"**File integrity check** (kiểm tra tính toàn vẹn tệp) **failed** (thất bại): {message}")
    
    return True

class SecurityError(Exception):
    """**Custom exception** (ngoại lệ tùy chỉnh) cho **security violations** (vi phạm bảo mật)"""
    pass

# **Script** (kịch bản) để **generate hash manifest** (tạo tệp kê khai mã băm)
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python integrity_check.py generate [output_path]")
        sys.exit(1)
    
    if sys.argv[1] == "generate":
        checker = FileIntegrityChecker()
        directories = [
            "../cpu_plugins",
            "/opt/ebpf",
            "../cuda"
        ]
        
        output_path = sys.argv[2] if len(sys.argv) > 2 else "file_hashes.json"
        manifest = checker.generate_manifest(directories, output_path)
        print(f"**Generated manifest** (đã tạo tệp kê khai) với {len(manifest)} **file hashes** (mã băm tệp)") 