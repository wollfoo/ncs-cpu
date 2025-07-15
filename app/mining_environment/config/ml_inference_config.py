"""
ml_inference_config.py - STUB

STUB chuyển tiếp cho tương thích ngược.
Mã nguồn thực đã được di chuyển sang mining_environment/cpu_plugins/config/inference_config.py
"""

# Import toàn bộ từ vị trí mới
from mining_environment.cpu_plugins.config.inference_config import (
    InferenceConfigService as MLInferenceConfig,
    get_inference_config as get_ml_inference_config
)

# Tái xuất các API cho tương thích ngược
__all__ = ['MLInferenceConfig', 'get_ml_inference_config']