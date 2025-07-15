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
        """Load danh sách hash từ manifest file"""
        if not self.manifest_path.exists():
            self.logger.warning(f"Hash manifest not found at {self.manifest_path}")
            return {}
        
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)
            self.logger.info(f"Loaded {len(manifest)} file hashes from manifest")
            return manifest
        except Exception as e:
            self.logger.error(f"Failed to load hash manifest: {e}")
            return {}
    
    def calculate_file_hash(self, filepath: Path) -> str:
        """Tính SHA256 hash của file"""
        sha256_hash = hashlib.sha256()
        
        try:
            with open(filepath, "rb") as f:
                # Read file in chunks để xử lý file lớn
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            return sha256_hash.hexdigest()
        
        except Exception as e:
            self.logger.error(f"Failed to calculate hash for {filepath}: {e}")
            raise
    
    def verify_file(self, filepath: Path) -> Tuple[bool, str]:
        """
        Xác thực file với hash trong manifest
        Returns: (is_valid, message)
        """
        filepath = Path(filepath)
        
        # Check cache first
        if str(filepath) in self.verification_cache:
            cached_result = self.verification_cache[str(filepath)]
            if cached_result['timestamp'] > datetime.now().timestamp() - 3600:  # 1 hour cache
                return cached_result['valid'], cached_result['message']
        
        # Get expected hash
        expected_hash = self.manifest.get(str(filepath))
        if not expected_hash:
            message = f"No hash found in manifest for {filepath}"
            self.logger.warning(message)
            return False, message
        
        # Calculate actual hash
        try:
            actual_hash = self.calculate_file_hash(filepath)
        except Exception as e:
            message = f"Failed to calculate hash: {str(e)}"
            return False, message
        
        # Compare hashes
        is_valid = actual_hash == expected_hash
        
        if is_valid:
            message = f"File {filepath} verified successfully"
            self.logger.info(message)
        else:
            message = f"Hash mismatch for {filepath}: expected {expected_hash}, got {actual_hash}"
            self.logger.error(message)
        
        # Cache result
        self.verification_cache[str(filepath)] = {
            'valid': is_valid,
            'message': message,
            'timestamp': datetime.now().timestamp()
        }
        
        return is_valid, message
    
    def verify_critical_files(self) -> Dict[str, bool]:
        """Xác thực tất cả critical files"""
        critical_files = [
            # CPU throttle eBPF has been removed
            "/app/mining_environment/cpu_plugins/csrc/libcloak.so",
            "/app/mining_environment/cuda/libgpuhook.so"
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
                    self.logger.critical(f"SECURITY: Critical file failed verification: {filepath}")
            else:
                results[filepath] = False
                self.logger.warning(f"Critical file not found: {filepath}")
        
        if not all_valid:
            self.logger.critical("SECURITY ALERT: One or more critical files failed integrity check!")
        
        return results
    
    def generate_manifest(self, directories: List[str], output_path: Optional[str] = None) -> Dict[str, str]:
        """
        Generate hash manifest cho các file trong directories
        Dùng để tạo manifest ban đầu hoặc update
        """
        manifest = {}
        
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                self.logger.warning(f"Directory not found: {directory}")
                continue
            
            # Find all .so, .o, and .py files
            for pattern in ['*.so', '*.o', '*.py']:
                for filepath in dir_path.rglob(pattern):
                    try:
                        file_hash = self.calculate_file_hash(filepath)
                        manifest[str(filepath)] = file_hash
                        self.logger.info(f"Hashed {filepath}: {file_hash}")
                    except Exception as e:
                        self.logger.error(f"Failed to hash {filepath}: {e}")
        
        # Save manifest if output path provided
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(manifest, f, indent=2, sort_keys=True)
            self.logger.info(f"Manifest saved to {output_path}")
        
        return manifest

# Helper function để verify trước khi load
def verify_before_load(filepath: str, checker: FileIntegrityChecker) -> bool:
    """
    Verify file integrity trước khi load
    Throw exception nếu verification fail
    """
    is_valid, message = checker.verify_file(Path(filepath))
    
    if not is_valid:
        raise SecurityError(f"File integrity check failed: {message}")
    
    return True

class SecurityError(Exception):
    """Custom exception cho security violations"""
    pass

# Script để generate hash manifest
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python integrity_check.py generate [output_path]")
        sys.exit(1)
    
    if sys.argv[1] == "generate":
        checker = FileIntegrityChecker()
        directories = [
            "/app/mining_environment/cpu_plugins",
            "/opt/ebpf",
            "/app/mining_environment/cuda"
        ]
        
        output_path = sys.argv[2] if len(sys.argv) > 2 else "file_hashes.json"
        manifest = checker.generate_manifest(directories, output_path)
        print(f"Generated manifest with {len(manifest)} file hashes") 