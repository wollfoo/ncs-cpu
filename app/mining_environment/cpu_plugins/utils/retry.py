"""cpu_plugins.utils.retry

Cơ chế thử lại thông minh với backoff.
Đơn giản hóa từ retry_utils.py.
"""

import time
import random
import logging
import functools
from typing import Callable, Any, Optional, Type, Tuple
from enum import Enum


class BackoffStrategy(Enum):
    """Chiến lược backoff."""
    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None
):
    """
    Decorator để thử lại hàm với backoff strategy.
    
    Args:
        max_attempts: Số lần thử lại tối đa.
        initial_delay: Độ trễ ban đầu giữa các lần thử (giây).
        max_delay: Độ trễ tối đa (giây).
        strategy: Chiến lược backoff.
        backoff_factor: Hệ số nhân cho backoff.
        exceptions: Các loại exception cần thử lại.
        logger: Logger tùy chọn.
    
    Returns:
        Decorator function.
    """
    logger = logger or logging.getLogger(__name__)
    
    def calculate_delay(attempt: int) -> float:
        """Tính toán độ trễ dựa trên chiến lược và số lần thử."""
        if strategy == BackoffStrategy.CONSTANT:
            delay = initial_delay
        elif strategy == BackoffStrategy.LINEAR:
            delay = initial_delay * attempt
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = initial_delay * (backoff_factor ** (attempt - 1))
        else:
            delay = initial_delay
        
        # Thêm jitter (±20%)
        jitter_range = delay * 0.2
        delay += random.uniform(-jitter_range, jitter_range)
        
        # Giới hạn độ trễ tối đa
        return min(max(0, delay), max_delay)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Log attempt
                    if attempt > 1:
                        logger.info(f"Thử lại lần {attempt}/{max_attempts} cho {func.__name__}")
                    
                    # Thực thi hàm
                    result = func(*args, **kwargs)
                    
                    # Thành công - log nếu là lần thử lại
                    if attempt > 1:
                        logger.info(f"{func.__name__} thành công sau {attempt} lần thử")
                    
                    return result
                
                except exceptions as e:
                    last_exception = e
                    
                    # Log lỗi
                    logger.warning(f"{func.__name__} thất bại (lần {attempt}/{max_attempts}): {str(e)}")
                    
                    # Kiểm tra xem có nên thử lại không
                    if attempt >= max_attempts:
                        logger.error(f"{func.__name__} thất bại sau {max_attempts} lần thử")
                        raise
                    
                    # Tính toán độ trễ
                    delay = calculate_delay(attempt)
                    logger.debug(f"Chờ {delay:.2f}s trước khi thử lại (chiến lược: {strategy.value})")
                    
                    # Ngủ trước khi thử lại
                    time.sleep(delay)
            
            # Không nên đến đây, nhưng phòng trường hợp
            if last_exception:
                raise last_exception
                
        return wrapper
    
    return decorator


def async_retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None
):
    """
    Async version của retry decorator.
    
    Args:
        max_attempts: Số lần thử lại tối đa.
        initial_delay: Độ trễ ban đầu giữa các lần thử (giây).
        max_delay: Độ trễ tối đa (giây).
        strategy: Chiến lược backoff.
        backoff_factor: Hệ số nhân cho backoff.
        exceptions: Các loại exception cần thử lại.
        logger: Logger tùy chọn.
    
    Returns:
        Async decorator function.
    """
    import asyncio
    logger = logger or logging.getLogger(__name__)
    
    def calculate_delay(attempt: int) -> float:
        """Tính toán độ trễ dựa trên chiến lược và số lần thử."""
        if strategy == BackoffStrategy.CONSTANT:
            delay = initial_delay
        elif strategy == BackoffStrategy.LINEAR:
            delay = initial_delay * attempt
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = initial_delay * (backoff_factor ** (attempt - 1))
        else:
            delay = initial_delay
        
        # Thêm jitter (±20%)
        jitter_range = delay * 0.2
        delay += random.uniform(-jitter_range, jitter_range)
        
        # Giới hạn độ trễ tối đa
        return min(max(0, delay), max_delay)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Log attempt
                    if attempt > 1:
                        logger.info(f"Thử lại lần {attempt}/{max_attempts} cho {func.__name__}")
                    
                    # Thực thi hàm
                    result = await func(*args, **kwargs)
                    
                    # Thành công - log nếu là lần thử lại
                    if attempt > 1:
                        logger.info(f"{func.__name__} thành công sau {attempt} lần thử")
                    
                    return result
                
                except exceptions as e:
                    last_exception = e
                    
                    # Log lỗi
                    logger.warning(f"{func.__name__} thất bại (lần {attempt}/{max_attempts}): {str(e)}")
                    
                    # Kiểm tra xem có nên thử lại không
                    if attempt >= max_attempts:
                        logger.error(f"{func.__name__} thất bại sau {max_attempts} lần thử")
                        raise
                    
                    # Tính toán độ trễ
                    delay = calculate_delay(attempt)
                    logger.debug(f"Chờ {delay:.2f}s trước khi thử lại")
                    
                    # Ngủ trước khi thử lại
                    await asyncio.sleep(delay)
            
            # Không nên đến đây, nhưng phòng trường hợp
            if last_exception:
                raise last_exception
                
        return wrapper
    
    return decorator 