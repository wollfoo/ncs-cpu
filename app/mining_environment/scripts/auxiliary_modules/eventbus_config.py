"""
eventbus_config.py

Production configuration for EventBus backends with environment-based selection.
Supports Redis, RabbitMQ, and Memory backends with proper fallback mechanisms.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class EventBusConfig:
    """Configuration for EventBus backend selection and settings"""
    
    # **[Backend selection]** (lựa chọn hậu phương – chọn loại EventBus)
    backend_type: str = "memory"  # memory, redis, rabbitmq
    
    # **[Redis configuration]** (cấu hình Redis – thiết lập kết nối)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # **[RabbitMQ configuration]** (cấu hình RabbitMQ – thiết lập message queue)
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_vhost: str = "/mining"
    rabbitmq_user: str = "mining-user"
    rabbitmq_password: str = "mining-password"
    
    # **[Connection settings]** (cài đặt kết nối – tham số mạng)
    connection_timeout: float = 5.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    # **[Health check settings]** (cài đặt kiểm tra sức khỏe – giám sát kết nối)
    health_check_interval: float = 30.0
    enable_health_check: bool = True
    
    # **[Fallback settings]** (cài đặt dự phòng – xử lý lỗi)
    fallback_to_memory: bool = True
    fallback_timeout: float = 10.0


def get_eventbus_config() -> EventBusConfig:
    """
    Get EventBus configuration from environment variables.
    
    Environment Variables:
    - EVENT_BUS_BACKEND: Backend type (memory, redis, rabbitmq)
    - REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD: Redis settings
    - RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_VHOST, RABBITMQ_USER, RABBITMQ_PASSWORD: RabbitMQ settings
    - EVENTBUS_CONNECTION_TIMEOUT: Connection timeout in seconds
    - EVENTBUS_RETRY_ATTEMPTS: Number of retry attempts
    - EVENTBUS_HEALTH_CHECK_INTERVAL: Health check interval in seconds
    - EVENTBUS_FALLBACK_TO_MEMORY: Enable fallback to memory backend
    
    Returns:
        EventBusConfig: Configuration object
    """
    
    config = EventBusConfig()
    
    # **[Backend selection]** (lựa chọn hậu phương – chọn loại EventBus)
    config.backend_type = os.getenv("EVENT_BUS_BACKEND", "memory").lower()
    
    # **[Redis configuration]** (cấu hình Redis – thiết lập kết nối)
    config.redis_host = os.getenv("REDIS_HOST", "localhost")
    config.redis_port = int(os.getenv("REDIS_PORT", "6379"))
    config.redis_db = int(os.getenv("REDIS_DB", "0"))
    config.redis_password = os.getenv("REDIS_PASSWORD")
    
    # **[RabbitMQ configuration]** (cấu hình RabbitMQ – thiết lập message queue)
    config.rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    config.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
    config.rabbitmq_vhost = os.getenv("RABBITMQ_VHOST", "/mining")
    config.rabbitmq_user = os.getenv("RABBITMQ_USER", "mining-user")
    config.rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "mining-password")
    
    # **[Connection settings]** (cài đặt kết nối – tham số mạng)
    config.connection_timeout = float(os.getenv("EVENTBUS_CONNECTION_TIMEOUT", "5.0"))
    config.retry_attempts = int(os.getenv("EVENTBUS_RETRY_ATTEMPTS", "3"))
    config.retry_delay = float(os.getenv("EVENTBUS_RETRY_DELAY", "1.0"))
    
    # **[Health check settings]** (cài đặt kiểm tra sức khỏe – giám sát kết nối)
    config.health_check_interval = float(os.getenv("EVENTBUS_HEALTH_CHECK_INTERVAL", "30.0"))
    config.enable_health_check = os.getenv("EVENTBUS_ENABLE_HEALTH_CHECK", "true").lower() == "true"
    
    # **[Fallback settings]** (cài đặt dự phòng – xử lý lỗi)
    config.fallback_to_memory = os.getenv("EVENTBUS_FALLBACK_TO_MEMORY", "true").lower() == "true"
    config.fallback_timeout = float(os.getenv("EVENTBUS_FALLBACK_TIMEOUT", "10.0"))
    
    return config


def get_production_eventbus_config() -> EventBusConfig:
    """
    Get production-ready EventBus configuration with RabbitMQ as primary backend.
    
    Returns:
        EventBusConfig: Production configuration
    """
    
    config = EventBusConfig()
    
    # **[Production defaults]** (giá trị mặc định sản xuất – cấu hình production)
    config.backend_type = "rabbitmq"
    config.connection_timeout = 10.0
    config.retry_attempts = 5
    config.retry_delay = 2.0
    config.health_check_interval = 60.0
    config.enable_health_check = True
    config.fallback_to_memory = True
    config.fallback_timeout = 30.0
    
    # **[Override with environment variables]** (ghi đè bằng biến môi trường – cấu hình runtime)
    config.backend_type = os.getenv("EVENT_BUS_BACKEND", config.backend_type).lower()
    config.rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq-cluster.mining.local")
    config.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
    config.rabbitmq_vhost = os.getenv("RABBITMQ_VHOST", "/mining")
    config.rabbitmq_user = os.getenv("RABBITMQ_USER", "mining-user")
    config.rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "secure-mining-password")
    
    return config


def get_development_eventbus_config() -> EventBusConfig:
    """
    Get development-friendly EventBus configuration with Memory backend.
    
    Returns:
        EventBusConfig: Development configuration
    """
    
    config = EventBusConfig()
    
    # **[Development defaults]** (giá trị mặc định phát triển – cấu hình dev)
    config.backend_type = "memory"
    config.connection_timeout = 2.0
    config.retry_attempts = 2
    config.retry_delay = 0.5
    config.health_check_interval = 10.0
    config.enable_health_check = False
    config.fallback_to_memory = True
    config.fallback_timeout = 5.0
    
    # **[Override with environment variables]** (ghi đè bằng biến môi trường – cấu hình runtime) if needed
    if os.getenv("EVENT_BUS_BACKEND"):
        config.backend_type = os.getenv("EVENT_BUS_BACKEND").lower()
    
    return config


def validate_eventbus_config(config: EventBusConfig, logger: Optional[logging.Logger] = None) -> bool:
    """
    Validate EventBus configuration for completeness and correctness.
    
    Args:
        config: EventBus configuration to validate
        logger: Optional logger for validation messages
    
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    
    if not logger:
        logger = logging.getLogger(__name__)
    
    # **[Validate backend type]** (xác thực loại hậu phương – kiểm tra hợp lệ)
    if config.backend_type not in ["memory", "redis", "rabbitmq"]:
        logger.error(f"Invalid backend type: {config.backend_type}")
        return False
    
    # **[Validate Redis configuration]** (xác thực cấu hình Redis – kiểm tra tham số)
    if config.backend_type == "redis":
        if not config.redis_host:
            logger.error("Redis host is required for Redis backend")
            return False
        if not (1 <= config.redis_port <= 65535):
            logger.error(f"Invalid Redis port: {config.redis_port}")
            return False
    
    # **[Validate RabbitMQ configuration]** (xác thực cấu hình RabbitMQ – kiểm tra kết nối)
    elif config.backend_type == "rabbitmq":
        if not config.rabbitmq_host:
            logger.error("RabbitMQ host is required for RabbitMQ backend")
            return False
        if not (1 <= config.rabbitmq_port <= 65535):
            logger.error(f"Invalid RabbitMQ port: {config.rabbitmq_port}")
            return False
        if not config.rabbitmq_user:
            logger.error("RabbitMQ user is required for RabbitMQ backend")
            return False
        if not config.rabbitmq_password:
            logger.error("RabbitMQ password is required for RabbitMQ backend")
            return False
    
    # **[Validate connection settings]** (xác thực cài đặt kết nối – kiểm tra timeout)
    if config.connection_timeout <= 0:
        logger.error(f"Invalid connection timeout: {config.connection_timeout}")
        return False
    
    if config.retry_attempts < 0:
        logger.error(f"Invalid retry attempts: {config.retry_attempts}")
        return False
    
    if config.retry_delay < 0:
        logger.error(f"Invalid retry delay: {config.retry_delay}")
        return False
    
    logger.info(f"EventBus configuration validated successfully: backend={config.backend_type}")
    return True


def get_eventbus_environment_info(config: EventBusConfig) -> Dict[str, Any]:
    """
    Get EventBus environment information for debugging and monitoring.
    
    Args:
        config: EventBus configuration
    
    Returns:
        Dict[str, Any]: Environment information
    """
    
    return {
        "backend_type": config.backend_type,
        "redis_host": config.redis_host if config.backend_type == "redis" else None,
        "redis_port": config.redis_port if config.backend_type == "redis" else None,
        "rabbitmq_host": config.rabbitmq_host if config.backend_type == "rabbitmq" else None,
        "rabbitmq_port": config.rabbitmq_port if config.backend_type == "rabbitmq" else None,
        "rabbitmq_vhost": config.rabbitmq_vhost if config.backend_type == "rabbitmq" else None,
        "connection_timeout": config.connection_timeout,
        "retry_attempts": config.retry_attempts,
        "health_check_enabled": config.enable_health_check,
        "fallback_to_memory": config.fallback_to_memory,
        "environment_mode": os.getenv("ENVIRONMENT", "development")
    }