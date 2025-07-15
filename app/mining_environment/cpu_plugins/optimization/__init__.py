"""cpu_plugins.optimization

Module tối ưu hóa CPU, cung cấp các kỹ thuật tối ưu hiệu năng.
"""

from .amd_optimizations import AMDOptimizationPlugin
# CpuThrottlePlugin đã được migrate sang OptimizedCalculationChain Architecture
try:
    from .optimized_calculation_chain import OptimizedCalculationChain as CpuThrottlePlugin
except ImportError:
    # Fallback for legacy compatibility
    class CpuThrottlePlugin:
        """Legacy compatibility class - redirects to OptimizedCalculationChain"""
        def __init__(self, *args, **kwargs):
            raise ImportError("CpuThrottlePlugin migrated to OptimizedCalculationChain Architecture")

__all__ = [
    'AMDOptimizationPlugin',
    'CpuThrottlePlugin',
]