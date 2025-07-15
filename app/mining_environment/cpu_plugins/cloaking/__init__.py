"""cpu_plugins.cloaking

Module che giấu CPU, cung cấp các kỹ thuật ẩn danh và tránh phát hiện.
"""

from .stealth_exec import StealthExecution
from .stealth_plugin import StealthExecutionPlugin
from .adaptive_cloak_plugin import AdaptiveCloakPlugin
from .signature_randomizer import SignatureRandomizer

__all__ = [
    'StealthExecution',
    'StealthExecutionPlugin',
    'AdaptiveCloakPlugin',
    'SignatureRandomizer',
] 