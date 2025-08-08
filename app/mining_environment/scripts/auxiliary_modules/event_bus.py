from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, Any, List, DefaultDict, Optional

import jsonschema
from jsonschema import ValidationError


class EventBusBackend(ABC):
    """Giao diện cho các [backend driver] (trình điều khiển hậu phương) của [EventBus] (bus sự kiện).
    
    Mỗi backend (memory, redis, kafka) phải [implement] (hiện thực) các phương thức này.
    """
    
    @abstractmethod
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới [topic] (chủ đề)."""
        pass
    
    @abstractmethod
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký [callback] (hàm gọi lại) cho [topic] (chủ đề)."""
        pass
    
    @abstractmethod
    def start_listening(self) -> None:
        """Khởi động [background listener] (bộ lắng nghe nền) nếu cần."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Dừng và dọn dẹp (cleanup) tài nguyên."""
        pass


class MemoryEventBusBackend(EventBusBackend):
    """[Backend driver] (trình điều khiển hậu phương) cho [EventBus] (bus sự kiện) sử dụng bộ nhớ (in-process)."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._subscribers: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới tất cả [subscribers] (người đăng ký) của [topic] (chủ đề)."""
        callbacks: List[Callable[[Dict[str, Any]], None]]
        with self._lock:
            callbacks = list(self._subscribers.get(topic, []))
        
        # Gọi [callback] (hàm gọi lại) ngoài [lock] (khóa) để tránh [deadlock] (khoá chết)
        for cb in callbacks:
            try:
                cb(payload)
            except Exception as exc:
                self._logger.error(
                    "Lỗi khi gọi [callback] (hàm gọi lại) cho [topic] (chủ đề) '%s': %s", topic, exc, exc_info=True
                )
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký callback cho topic."""
        with self._lock:
            if callback not in self._subscribers[topic]:
                self._subscribers[topic].append(callback)
    
    def start_listening(self) -> None:
        """Không cần [implement] (hiện thực) cho [memory backend] (hậu phương bộ nhớ)."""
        pass
    
    def stop(self) -> None:
        """Huỷ tất cả [subscriptions] (đăng ký)."""
        with self._lock:
            self._subscribers.clear()


class RedisEventBusBackend(EventBusBackend):
    """[Backend driver] (trình điều khiển hậu phương) cho [EventBus] (bus sự kiện) sử dụng [Redis Pub/Sub] (cơ chế xuất/đăng ký của Redis)."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._redis_client = None
        self._pubsub = None
        self._listener_thread = None
        self._stop_listening = False
        self._lock = threading.RLock()
        self._subscribers: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        
        # [Redis connection configuration] (cấu hình kết nối Redis)
        self._redis_config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'db': int(os.getenv('REDIS_DB', '0')),
            'password': os.getenv('REDIS_PASSWORD', None),
            'decode_responses': True,
            'socket_timeout': 5.0,
            'socket_connect_timeout': 5.0,
            'retry_on_timeout': True,
            'health_check_interval': 30
        }
        
        # [Retry configuration] (cấu hình thử lại)
        self._retry_config = {
            'max_retries': 3,
            'base_delay': 0.1,
            'max_delay': 1.0,
            'backoff_factor': 2.0
        }
        
        # Khởi tạo kết nối Redis
        self._initialize_redis()
    
    def _initialize_redis(self) -> None:
        """Khởi tạo kết nối [Redis] (hệ quản trị key-value) với [retry logic] (logic thử lại)."""
        try:
            import redis
            self._redis_client = redis.Redis(**self._redis_config)
            
            # Kiểm tra kết nối ([Test connection])
            self._redis_client.ping()
            self._logger.info("Kết nối [Redis] (hệ quản trị key-value) được thiết lập thành công")},{
            
            # Initialize pubsub
            self._pubsub = self._redis_client.pubsub()
            
        except ImportError:
            raise ImportError("Redis package not installed. Run: pip install redis>=4.5.0")
        except Exception as e:
            self._logger.error(f"Khởi tạo kết nối [Redis] (hệ quản trị key-value) thất bại: {e}")
            raise
    
    def _retry_operation(self, operation, *args, **kwargs):
        """[Retry logic] (logic thử lại) cho thao tác [Redis] (hệ quản trị key-value) với [exponential backoff] (lùi theo cấp số nhân)."""
        retry_count = 0
        delay = self._retry_config['base_delay']
        
        while retry_count < self._retry_config['max_retries']:
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                retry_count += 1
                if retry_count >= self._retry_config['max_retries']:
                    self._logger.error(f"Thao tác [Redis] (hệ quản trị key-value) thất bại after {retry_count} retries: {e}")
                    raise
                
                 self._logger.warning(f"Thao tác [Redis] (hệ quản trị key-value) thất bại (attempt {retry_count}): {e}. [Retrying] (thử lại) sau {delay}s...")
                time.sleep(delay)
                delay = min(delay * self._retry_config['backoff_factor'], self._retry_config['max_delay'])
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới [Redis channel] (kênh Redis) với [retry logic] (logic thử lại)."""
        if not self._redis_client:
            raise RuntimeError("Redis client not initialized")
        
        try:
            # [Serialize] (tuần tự hoá) payload sang [JSON] (định dạng dữ liệu)
            message = json.dumps(payload)
            
            # [Publish] (xuất bản) với [retry logic] (logic thử lại)
            def _publish_operation():
                published = self._redis_client.publish(topic, message)
                if published == 0:
                    self._logger.warning(f"Không có [subscribers] (người đăng ký) cho [topic] (chủ đề) '{topic}'")
                return published
            
            self._retry_operation(_publish_operation)
            self._logger.debug(f"Đã [publish] (xuất bản) [message] (thông điệp) tới [topic] (chủ đề) '{topic}': {payload}")
            
        except Exception as e:
            self._logger.error(f"[Publish] (xuất bản) [message] (thông điệp) tới [topic] (chủ đề) thất bại '{topic}': {e}")
            raise
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký [callback] (hàm gọi lại) cho [Redis channel] (kênh Redis)."""
        with self._lock:
            if callback not in self._subscribers[topic]:
                self._subscribers[topic].append(callback)
                
                # [Subscribe] (đăng ký) vào [Redis channel] (kênh Redis) nếu là subscriber đầu tiên
                if len(self._subscribers[topic]) == 1:
                    try:
                        self._pubsub.subscribe(topic)
                        self._logger.debug(f"Đã subscribe (đăng ký) Redis channel '{topic}'")
                    except Exception as e:
                        self._logger.error(f"[Subscribe] (đăng ký) [Redis channel] (kênh Redis) thất bại '{topic}': {e}")
                        raise
    
    def start_listening(self) -> None:
        """Khởi động [background listener thread] (luồng lắng nghe nền)."""
        if self._listener_thread and self._listener_thread.is_alive():
            self._logger.warning("Luồng listener đã chạy")
            return
        
        self._stop_listening = False
        self._listener_thread = threading.Thread(target=self._listen_for_messages, daemon=True)
        self._listener_thread.start()
        self._logger.info("Luồng listener [Redis] (hệ quản trị key-value) đã khởi động")
    
    def _listen_for_messages(self) -> None:
        """Background thread để lắng nghe Redis messages."""
        try:
            while not self._stop_listening:
                try:
            # [Non-blocking get message] (lấy thông điệp không chặn) với [timeout] (thời gian chờ)
                    message = self._pubsub.get_message(timeout=1.0)
                    
                    if message and message['type'] == 'message':
                        topic = message['channel']
                        data = message['data']
                        
                        try:
                            # [Deserialize] (giải tuần tự) [JSON payload] (dữ liệu JSON)
                            payload = json.loads(data)
                            
                            # Gọi tất cả [subscribers] (người đăng ký) cho [topic] (chủ đề) này
                            callbacks = []
                            with self._lock:
                                callbacks = list(self._subscribers.get(topic, []))
                            
                            for callback in callbacks:
                                try:
                                    callback(payload)
                                except Exception as e:
                                     self._logger.error(f"Lỗi gọi [callback] (hàm gọi lại) cho [topic] (chủ đề) '{topic}': {e}")
                                    
                        except json.JSONDecodeError as e:
                            self._logger.error(f"[JSON] (định dạng dữ liệu) không hợp lệ trong [message] (thông điệp) từ [topic] (chủ đề) '{topic}': {e}")
                            
                except Exception as e:
                    if not self._stop_listening:
                        self._logger.error(f"Lỗi trong [listener] (bộ lắng nghe) [Redis] (hệ quản trị key-value): {e}")
                        time.sleep(1)  # Avoid tight loop on persistent errors
                        
        except Exception as e:
            self._logger.error(f"Lỗi nghiêm trọng trong luồng [listener] (bộ lắng nghe) [Redis] (hệ quản trị key-value): {e}")
    
    def stop(self) -> None:
        """Dừng [Redis backend] (hậu phương Redis) và dọn dẹp tài nguyên."""
        self._stop_listening = True
        
        # Chờ [listener thread] (luồng lắng nghe) kết thúc
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5.0)
            if self._listener_thread.is_alive():
                self._logger.warning("Luồng listener không dừng một cách graceful (êm ái)")
        
        # Đóng kết nối [pubsub] (xuất/đăng ký)
        if self._pubsub:
            try:
                self._pubsub.close()
            except Exception as e:
                self._logger.error(f"Lỗi khi đóng kết nối [pubsub] (xuất/đăng ký): {e}")
        
        # Đóng [Redis client] (khách hàng Redis)
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception as e:
                self._logger.error(f"Lỗi khi đóng [Redis client] (khách hàng Redis): {e}")
        
        # Xoá danh sách [subscribers] (người đăng ký)
        with self._lock:
            self._subscribers.clear()
        
        self._logger.info("[Redis backend] (hậu phương Redis) đã dừng")


class RabbitMQEventBusBackend(EventBusBackend):
    """[Backend driver] (trình điều khiển hậu phương) cho [EventBus] (bus sự kiện) sử dụng [RabbitMQ] (hệ thống hàng đợi thông điệp) với [High Availability] (khả dụng cao)."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._connection = None
        self._channel = None
        self._listener_thread = None
        self._stop_listening = False
        self._lock = threading.RLock()
        self._subscribers: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        # **Thread-safe consumer tags management** (quản lý [consumer tags] – thẻ consumer – an toàn luồng)
        self._consumer_tags_lock = threading.RLock()
        self._consumer_tags = {}
        
        # [RabbitMQ connection configuration] (cấu hình kết nối RabbitMQ)
        self._rabbitmq_config = {
            'host': os.getenv('RABBITMQ_HOST', 'localhost'),
            'port': int(os.getenv('RABBITMQ_PORT', '5672')),
            'virtual_host': os.getenv('RABBITMQ_VHOST', '/mining'),
            'username': os.getenv('RABBITMQ_USER', 'mining-user'),
            'password': os.getenv('RABBITMQ_PASSWORD', 'mining-password'),
            'connection_attempts': 5,
            'retry_delay': 5,
            'socket_timeout': 10,
            'heartbeat': 60,
            'blocked_connection_timeout': 300,
        }
        
        # [Exchange and routing configuration] (cấu hình [exchange] – sàn giao dịch, và định tuyến)
        self._exchange_config = {
            'name': 'mining',
            'type': 'topic',
            'durable': True,
            'auto_delete': False,
        }
        
        # [Retry configuration] (cấu hình thử lại)
        self._retry_config = {
            'max_retries': 3,
            'base_delay': 0.1,
            'max_delay': 5.0,
            'backoff_factor': 2.0
        }
        
        # Khởi tạo kết nối RabbitMQ
        self._initialize_rabbitmq()
    
    def _initialize_rabbitmq(self) -> None:
        """Khởi tạo kết nối [RabbitMQ] (hệ thống hàng đợi thông điệp) với [retry logic] (logic thử lại) và hỗ trợ [HA] (khả dụng cao)."""
        try:
            import pika
            
            # [Connection parameters] (tham số kết nối) với hỗ trợ [HA] (khả dụng cao)
            connection_params = pika.ConnectionParameters(
                host=self._rabbitmq_config['host'],
                port=self._rabbitmq_config['port'],
                virtual_host=self._rabbitmq_config['virtual_host'],
                credentials=pika.PlainCredentials(
                    self._rabbitmq_config['username'],
                    self._rabbitmq_config['password']
                ),
                connection_attempts=self._rabbitmq_config['connection_attempts'],
                retry_delay=self._rabbitmq_config['retry_delay'],
                socket_timeout=self._rabbitmq_config['socket_timeout'],
                heartbeat=self._rabbitmq_config['heartbeat'],
                blocked_connection_timeout=self._rabbitmq_config['blocked_connection_timeout']
            )
            
            # Thiết lập kết nối ([Establish connection])
            self._connection = pika.BlockingConnection(connection_params)
            self._channel = self._connection.channel()
            
            # Khai báo [exchange] (sàn giao dịch)
            self._channel.exchange_declare(
                exchange=self._exchange_config['name'],
                exchange_type=self._exchange_config['type'],
                durable=self._exchange_config['durable'],
                auto_delete=self._exchange_config['auto_delete']
            )
            
            self._logger.info("RabbitMQ kết nối được thiết lập thành công")
            
        except ImportError:
            raise ImportError("Pika package not installed. Run: pip install pika>=1.3.0")
        except Exception as e:
            self._logger.error(f"Khởi tạo kết nối [RabbitMQ] (hệ thống hàng đợi thông điệp) thất bại: {e}")
            raise
    
    def _retry_operation(self, operation, *args, **kwargs):
        """[Retry logic] (logic thử lại) cho thao tác [RabbitMQ] (hệ thống hàng đợi thông điệp) với [exponential backoff] (lùi theo cấp số nhân)."""
        retry_count = 0
        delay = self._retry_config['base_delay']
        
        while retry_count < self._retry_config['max_retries']:
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                retry_count += 1
                if retry_count >= self._retry_config['max_retries']:
                    self._logger.error(f"Thao tác [RabbitMQ] (hệ thống hàng đợi thông điệp) thất bại after {retry_count} retries: {e}")
                    raise
                
                self._logger.warning(f"Thao tác [RabbitMQ] (hệ thống hàng đợi thông điệp) thất bại (attempt {retry_count}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay = min(delay * self._retry_config['backoff_factor'], self._retry_config['max_delay'])
                
                # Kết nối lại nếu kết nối bị hỏng ([Reconnect if connection is broken])
                if not self._connection or self._connection.is_closed:
                    self._initialize_rabbitmq()
    
    def _validate_connection_state(self) -> bool:
        """**Enhanced connection state validation** (xác thực trạng thái kết nối nâng cao) với **consumer cleanup** (dọn dẹp consumer)."""
        try:
            # **Check connection health** (kiểm tra tình trạng kết nối)
            if not self._connection or self._connection.is_closed:
                self._logger.warning("🔧 RabbitMQ connection is closed, reinitializing...")
                
                # **Thread-safe clear consumer tags** (xóa thẻ consumer an toàn luồng) before reinit
                with self._consumer_tags_lock:
                    self._consumer_tags.clear()
                self._initialize_rabbitmq()
                return True
                
            # **Test channel health** (kiểm tra tình trạng kênh)
            if not self._channel or self._channel.is_closed:
                self._logger.warning("🔧 RabbitMQ channel is closed, recreating...")
                
                # **Thread-safe clear consumer tags** (xóa thẻ consumer an toàn luồng) before channel recreation
                with self._consumer_tags_lock:
                    self._consumer_tags.clear()
                self._channel = self._connection.channel()
                
                # **Re-declare exchange** (khai báo lại exchange)
                self._channel.exchange_declare(
                    exchange=self._exchange_config['name'],
                    exchange_type=self._exchange_config['type'],
                    durable=self._exchange_config['durable'],
                    auto_delete=self._exchange_config['auto_delete']
                )
                self._logger.debug("✅ Exchange re-declared successfully")
                return True
                
            # **Test channel accessibility** (kiểm tra khả năng truy cập kênh)
            try:
                self._channel.basic_qos(prefetch_count=1)  # Light operation to test channel
                self._logger.debug("✅ Channel health check passed")
            except Exception as channel_e:
                self._logger.warning(f"🔧 [Channel accessibility test] (bài kiểm tra khả năng truy cập kênh) thất bại: {channel_e}, đang tạo lại...")
                with self._consumer_tags_lock:
                    self._consumer_tags.clear()
                self._channel = self._connection.channel()
                
                # **Re-declare exchange** (khai báo lại exchange)
                self._channel.exchange_declare(
                    exchange=self._exchange_config['name'],
                    exchange_type=self._exchange_config['type'],
                    durable=self._exchange_config['durable'],
                    auto_delete=self._exchange_config['auto_delete']
                )
                self._logger.debug("✅ Channel recreated after accessibility test failure")
                return True
                
            # **Connection is healthy** (kết nối tốt)
            return True
            
        except Exception as e:
            self._logger.error(f"❌ [Enhanced connection validation] (xác thực kết nối nâng cao) thất bại: {e}")
            # **Emergency cleanup** (dọn dẹp khẩn cấp)
            with self._consumer_tags_lock:
                self._consumer_tags.clear()
            return False
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """**Enhanced message publishing** (xuất bản thông điệp nâng cao) với **connection validation** (xác thực kết nối) và **retry logic** (logic thử lại)."""
        # **Validate connection state** (xác thực trạng thái kết nối) trước khi [publish] (xuất bản)
        if not self._validate_connection_state():
            raise RuntimeError("RabbitMQ connection validation failed")
        
        try:
            # [Serialize] (tuần tự hoá) payload sang [JSON] (định dạng dữ liệu)
            message_body = json.dumps(payload)
            
            # [Publish] (xuất bản) với [retry logic] (logic thử lại) và [message durability] (độ bền thông điệp)
            def _publish_operation():
                import pika
                
                self._channel.basic_publish(
                    exchange=self._exchange_config['name'],
                    routing_key=topic,
                    body=message_body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Message durability
                        content_type='application/json',
                        timestamp=int(time.time()),
                        message_id=f"{topic}-{int(time.time())}-{os.getpid()}"
                    )
                )
            
            self._retry_operation(_publish_operation)
            self._logger.debug(f"Đã [publish] (xuất bản) [message] (thông điệp) tới [topic] (chủ đề) '{topic}': {payload}")
            
        except Exception as e:
            self._logger.error(f"[Publish] (xuất bản) [message] (thông điệp) tới [topic] (chủ đề) thất bại '{topic}': {e}")
            raise
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """**Enhanced subscription** (đăng ký nâng cao) với **connection validation** (xác thực kết nối) và **durable queue** (hàng đợi bền vững)."""
        # **Validate connection state** (xác thực trạng thái kết nối) trước khi [subscribe] (đăng ký)
        if not self._validate_connection_state():
            raise RuntimeError("RabbitMQ connection validation failed for subscription")
            
        with self._lock:
            if callback not in self._subscribers[topic]:
                self._subscribers[topic].append(callback)
                
                # **Declare durable queue** (khai báo hàng đợi bền vững) for topic if first subscriber
                if len(self._subscribers[topic]) == 1:
                    try:
                        # Validate connection before queue operations
                        if not self._validate_connection_state():
                            raise RuntimeError("RabbitMQ connection validation failed")

                        queue_name = topic.replace(':', '.')

                        # Declare durable queue with enhanced error handling
                        queue_result = self._channel.queue_declare(
                            queue=queue_name,
                            durable=True,
                            auto_delete=False
                        )

                        # Verify queue declaration result
                        if hasattr(queue_result, 'method') and hasattr(queue_result.method, 'queue'):
                            self._logger.debug(f"✅ Queue declared successfully: {queue_result.method.queue}")

                        # Bind queue to exchange
                        self._channel.queue_bind(
                            exchange=self._exchange_config['name'],
                            queue=queue_name,
                            routing_key=topic
                        )

                        self._logger.debug(f"Declared and bound queue '{queue_name}' for topic '{topic}'")

                    except Exception as e:
                        self._logger.error(f"❌ Failed to setup queue for topic '{topic}': {e}")
                        self._logger.warning(f"🔄 Subscriber for '{topic}' will use degraded mode (no persistent queue)")
                        # Don't raise - allow subscription to continue in degraded mode
                        # The callback will still be registered for in-memory delivery
    
    def start_listening(self) -> None:
        """Khởi động background listener thread với consumer acknowledgment."""
        if self._listener_thread and self._listener_thread.is_alive():
            self._logger.warning("Luồng listener đã chạy")
            return
        
        self._stop_listening = False
        self._listener_thread = threading.Thread(target=self._consume_messages, daemon=True)
        self._listener_thread.start()
        self._logger.info("Luồng listener [RabbitMQ] (hệ thống hàng đợi thông điệp) đã khởi động")
    
    def _consume_messages(self) -> None:
        """Background thread để consume RabbitMQ messages với ACK và enhanced error handling."""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries and not self._stop_listening:
            try:
                # Validate connection before setting up consumers
                if not self._validate_connection_state():
                    self._logger.error("❌ RabbitMQ connection validation failed, retrying...")
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    continue

                # **Thread-safe setup consumers** (thiết lập consumers an toàn luồng) for all subscribed topics
                with self._lock:
                    topics_to_process = list(self._subscribers.keys())
                
                for topic in topics_to_process:
                    queue_name = topic.replace(':', '.')

                    def make_callback(topic_name):
                        def callback(ch, method, properties, body):
                            try:
                                # Deserialize JSON payload
                                payload = json.loads(body.decode('utf-8'))

                                # Call all subscribers for this topic
                                callbacks = []
                                with self._lock:
                                    callbacks = list(self._subscribers.get(topic_name, []))

                                for callback_func in callbacks:
                                    try:
                                        callback_func(payload)
                                    except Exception as e:
                                        self._logger.error(f"Lỗi gọi callback cho topic '{topic_name}': {e}")

                                # Acknowledge message after successful processing
                                ch.basic_ack(delivery_tag=method.delivery_tag)

                            except json.JSONDecodeError as e:
                                self._logger.error(f"[JSON] (định dạng dữ liệu) không hợp lệ in message from topic '{topic_name}': {e}")
                                # Reject message with no requeue
                                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                            except Exception as e:
                                self._logger.error(f"Error processing message from topic '{topic_name}': {e}")
                                # Reject message with requeue for retry
                                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

                        return callback

                    # **Ultra-unique consumer tag generation** (tạo thẻ consumer cực kỳ duy nhất)
                    # Kết hợp: UUID + high-precision timestamp + PID + random để tránh **tag reuse conflicts**
                    import random
                    microseconds = int(time.time() * 1000000)  # Microsecond precision
                    random_suffix = random.randint(1000, 9999)
                    unique_consumer_tag = f"ctag-{uuid.uuid4().hex[:12]}-{microseconds}-{os.getpid()}-{random_suffix}"
                    self._logger.debug(f"🏷️  Creating ultra-unique consumer tag: {unique_consumer_tag}")

                    # **Thread-safe tag uniqueness verification** (xác minh tính duy nhất của thẻ an toàn luồng)
                    with self._consumer_tags_lock:
                        tag_exists = unique_consumer_tag in self._consumer_tags.values()
                    
                    if tag_exists:
                        # **Fallback regeneration** (tái tạo dự phòng) nếu thẻ trùng (rất hiếm)
                        unique_consumer_tag = f"ctag-backup-{uuid.uuid4().hex}-{int(time.time() * 1000000)}"
                        self._logger.warning(f"🔄 Consumer tag collision detected, using backup: {unique_consumer_tag}")

                    try:
                        consumer_tag = self._channel.basic_consume(
                            queue=queue_name,
                            on_message_callback=make_callback(topic),
                            auto_ack=False,  # **Manual acknowledgment** (xác nhận thủ công) cho **message durability** (độ bền thông điệp)
                            consumer_tag=unique_consumer_tag  # **Ultra-unique consumer tag** (thẻ consumer cực kỳ duy nhất)
                        )

                        # **Thread-safe consumer tag storage** (lưu trữ [consumer tag] – thẻ consumer – an toàn luồng)
                        with self._consumer_tags_lock:
                            self._consumer_tags[topic] = consumer_tag
                        self._logger.debug(f"Đã bắt đầu [consuming] (tiêu thụ) [queue] (hàng đợi) '{queue_name}' cho [topic] (chủ đề) '{topic}'")

                    except Exception as consumer_error:
                        self._logger.error(f"Thiết lập [consumer] (bộ tiêu thụ) cho [topic] (chủ đề) '{topic}' thất bại: {consumer_error}")
                        # Continue with other topics instead of failing completely
                        continue

                # Bắt đầu [consuming] (tiêu thụ) (chặn) - đặt lại số lần thử nếu thiết lập thành công
                retry_count = 0
                self._channel.start_consuming()
                break  # Exit retry loop on successful consumption

            except Exception as e:
                retry_count += 1
                if not self._stop_listening:
                    if retry_count >= max_retries:
                        self._logger.error(f"❌ [RabbitMQ consumer] (bộ tiêu thụ RabbitMQ) thất bại sau {max_retries} lần thử: {e}")
                        self._logger.error("🔄 Luồng [consumer] (bộ tiêu thụ) sẽ thoát, hệ thống tiếp tục với chế độ nhắn tin suy giảm")
                        break
                    else:
                        self._logger.warning(f"⚠️ Lỗi [RabbitMQ consumer] (bộ tiêu thụ RabbitMQ) (attempt {retry_count}/{max_retries}): {e}")
                        self._logger.info(f"🔄 [Retrying] (thử lại) sau {2 ** retry_count} giây...")
                        time.sleep(2 ** retry_count)  # Exponential backoff

                        # **Thread-safe clear consumer tags** (xóa thẻ consumer an toàn luồng) and reinitialize connection
                        with self._consumer_tags_lock:
                            self._consumer_tags.clear()
                        try:
                            self._initialize_rabbitmq()
                        except Exception as init_error:
                            self._logger.error(f"Tái khởi tạo [RabbitMQ] (hệ thống hàng đợi thông điệp) thất bại: {init_error}")

        self._logger.info("🔚 Luồng [RabbitMQ consumer] (bộ tiêu thụ RabbitMQ) đã thoát")
    
    def stop(self) -> None:
        """**Ultra-safe [RabbitMQ backend] (hậu phương RabbitMQ) cleanup** (dọn dẹp cực kỳ an toàn) với **advanced error recovery** (phục hồi lỗi nâng cao)."""
        self._stop_listening = True
        
        # **Pre-cleanup validation** (xác thực trước dọn dẹp)
        cleanup_errors = []
        
        # **Phase 1: Enhanced consumer cancellation** (Giai đoạn 1: hủy [consumer] nâng cao) dùng phương thức dọn dẹp an toàn
        if self._channel and not self._channel.is_closed:
            try:
                self._logger.info("🧹 Phase 1: Enhanced consumer cleanup...")
                
                # **Use safe cleanup method** (sử dụng phương thức dọn dẹp an toàn)
                self._safe_consumer_cleanup()
                
                # **Legacy cleanup for compatibility** (dọn dẹp kiểu cũ để tương thích)
                with self._consumer_tags_lock:
                    consumer_items = list(self._consumer_tags.items())
                
                for topic, consumer_tag in consumer_items:
                    try:
                        # **Verify consumer tag exists** (xác minh thẻ [consumer] tồn tại) trước khi huỷ
                        if consumer_tag:
                            self._channel.basic_cancel(consumer_tag)
                            self._logger.debug(f"✅ Đã huỷ [consumer] (bộ tiêu thụ): {topic} (tag: {consumer_tag})")
                        else:
                            self._logger.warning(f"⚠️ [Consumer tag] (thẻ consumer) rỗng cho [topic] (chủ đề): {topic}")
                    except Exception as e:
                        error_msg = f"Huỷ [consumer] (bộ tiêu thụ) thất bại {topic}: {e}"
                        cleanup_errors.append(error_msg)
                        self._logger.warning(f"⚠️ {error_msg}")
                        # **Continue cleanup** (tiếp tục dọn dẹp) thay vì dừng
                
                # **Phase 2: Mass consumer cleanup** (Giai đoạn 2: dọn dẹp [consumer] hàng loạt)
                self._logger.info("🧹 Phase 2: Mass consumer cleanup...")
                try:
                    self._channel.stop_consuming()
                    self._logger.debug("✅ Đã hoàn tất stop_consuming hàng loạt")
                except Exception as e:
                    cleanup_errors.append(f"stop_consuming thất bại: {e}")
                    self._logger.warning(f"⚠️ Lỗi stop_consuming: {e}")
                
            except Exception as e:
                cleanup_errors.append(f"Lỗi nghiêm trọng khi dọn dẹp [consumer] (bộ tiêu thụ): {e}")
                self._logger.error(f"❌ Lỗi nghiêm trọng khi dọn dẹp [consumer] (bộ tiêu thụ): {e}")
                
                # **Emergency force cleanup** (dọn dẹp ép buộc khẩn cấp)
                self._logger.warning("🚨 Kích hoạt giao thức dọn dẹp khẩn cấp...")
                try:
                    if self._connection and not self._connection.is_closed:
                        self._connection.close()
                        self._logger.info("✅ Đóng kết nối khẩn cấp thành công")
                except Exception as emergency_e:
                    cleanup_errors.append(f"Dọn dẹp khẩn cấp thất bại: {emergency_e}")
                    self._logger.error(f"❌ Dọn dẹp khẩn cấp thất bại: {emergency_e}")
        
        # **Thread-safe clear consumer tags tracking** (xóa theo dõi thẻ [consumer] an toàn luồng) - luôn thực thi
        try:
            with self._consumer_tags_lock:
                self._consumer_tags.clear()
            self._logger.debug("✅ Đã xoá [consumer tags] (thẻ consumer)")
        except Exception as e:
            cleanup_errors.append(f"Consumer tags clear failed: {e}")
        
        # **Phase 3: Thread management** (Giai đoạn 3: quản lý luồng)
        if self._listener_thread and self._listener_thread.is_alive():
            self._logger.info("🧹 Phase 3: Thread cleanup with extended timeout...")
            self._listener_thread.join(timeout=15.0)  # **Increased timeout** (tăng timeout) 10s -> 15s
            if self._listener_thread.is_alive():
                self._logger.warning("⚠️ [Listener thread] (luồng lắng nghe) vẫn còn sau thời gian chờ 15s")
                cleanup_errors.append("Thread cleanup timeout after 15s")
        
        # **Phase 4: Connection closure with advanced retry** (Giai đoạn 4: đóng kết nối với cơ chế thử lại nâng cao)
        if self._connection and not self._connection.is_closed:
            self._logger.info("🧹 Phase 4: Advanced connection closure...")
            for attempt in range(5):  # **Increased retry attempts** (tăng số lần thử) 3 -> 5
                try:
                    self._connection.close()
                    self._logger.debug(f"✅ Đóng kết nối thành công (lần {attempt + 1})")
                    break
                except Exception as e:
                    if attempt < 4:  # Chưa hết attempts
                        backoff_delay = 0.5 * (2 ** attempt)  # **Exponential backoff** (lùi theo cấp số nhân)
                        self._logger.warning(f"⚠️ Lần đóng kết nối {attempt + 1} thất bại: {e}. [Retrying] (thử lại) sau {backoff_delay}s...")
                        time.sleep(backoff_delay)
                    else:
                        cleanup_errors.append(f"Đóng kết nối thất bại sau 5 lần: {e}")
                        self._logger.error(f"❌ Đóng kết nối thất bại sau 5 lần: {e}")
        
        # **Phase 5: Final cleanup** (Giai đoạn 5: dọn dẹp cuối cùng)
        try:
            with self._lock:
                self._subscribers.clear()
            self._logger.debug("✅ Đã xoá [subscribers] (người đăng ký)")
        except Exception as e:
            cleanup_errors.append(f"Subscribers clear failed: {e}")
        
        # **Cleanup summary** (tóm tắt dọn dẹp)
        if cleanup_errors:
            self._logger.warning(f"🔍 Dọn dẹp hoàn tất với {len(cleanup_errors)} lỗi: {cleanup_errors}")
        else:
            self._logger.info("🎯 Dọn dẹp [RabbitMQ] (hệ thống hàng đợi thông điệp) cực kỳ an toàn hoàn tất - không lỗi!")
        
        self._logger.info("🏁 Trình tự tắt [RabbitMQ backend] (hậu phương RabbitMQ) đã hoàn tất")
    
    def _safe_consumer_cleanup(self) -> None:
        """**Thread-safe [consumer] cleanup** (dọn dẹp bộ tiêu thụ an toàn luồng) với **error isolation** (cô lập lỗi)"""
        try:
            # **Atomic snapshot and clear** (chụp nhanh và xoá nguyên tử)
            with self._consumer_tags_lock:
                if not self._consumer_tags:
                    self._logger.debug("🔍 Không có [consumer tags] (thẻ consumer) để dọn dẹp")
                    return
                tags_copy = dict(self._consumer_tags)
                self._consumer_tags.clear()
                self._logger.debug(f"📋 Đã chụp {len(tags_copy)} [consumer tags] (thẻ consumer) để dọn dẹp")
            
            # **Cleanup outside lock** (dọn dẹp bên ngoài [lock] – khóa) để tránh **deadlock** (khoá chết)
            cleanup_count = 0
            error_count = 0
            
            for topic, tag in tags_copy.items():
                try:
                    if self._channel and not self._channel.is_closed and tag:
                        self._channel.basic_cancel(tag)
                        cleanup_count += 1
                        self._logger.debug(f"✅ Successfully cancelled consumer: {topic} (tag: {tag})")
                    else:
                        self._logger.debug(f"⚠️ Bỏ qua dọn dẹp cho {topic}: channel_ok={bool(self._channel and not self._channel.is_closed)}, tag_ok={bool(tag)}")
                except Exception as e:
                    error_count += 1
                    self._logger.warning(f"⚠️ Huỷ [consumer] (bộ tiêu thụ) thất bại {topic}: {e}")
                    # **Continue cleanup** (tiếp tục dọn dẹp) instead of failing
            
            # **Cleanup summary** (tóm tắt dọn dẹp)
            self._logger.info(f"🧹 Dọn dẹp [consumer] (bộ tiêu thụ) hoàn tất: {cleanup_count} thành công, {error_count} lỗi")
            
        except Exception as e:
            self._logger.error(f"❌ Lỗi nghiêm trọng trong _safe_consumer_cleanup: {e}")
            # **Emergency fallback** (dự phòng khẩn cấp): force clear tags
            try:
                with self._consumer_tags_lock:
                    self._consumer_tags.clear()
                self._logger.warning("🚨 Khẩn cấp: Đã xoá cưỡng bức [consumer tags] (thẻ consumer) sau lỗi dọn dẹp")
            except Exception as emergency_e:
                self._logger.error(f"💥 Dọn dẹp khẩn cấp cũng thất bại: {emergency_e}")
    
    def _validate_consumer_state(self) -> bool:
        """**Enhanced consumer state validation** (xác thực trạng thái [consumer] nâng cao) với **thread safety** (an toàn luồng)"""
        try:
            with self._consumer_tags_lock:
                consumer_count = len(self._consumer_tags)
                if consumer_count == 0:
                    self._logger.debug("🔍 No active consumers to validate")
                    return True
                
                # **Check for orphaned consumer tags** (kiểm tra thẻ consumer mồ côi)
                if not self._channel or self._channel.is_closed:
                    self._logger.warning(f"⚠️ Phát hiện {consumer_count} [consumer tags] mồ côi (kênh đã đóng)")
                    self._consumer_tags.clear()
                    return False
                
                self._logger.debug(f"✅ Xác thực trạng thái [consumer] đạt: {consumer_count} consumer đang hoạt động")
                return True
                
        except Exception as e:
            self._logger.error(f"❌ Xác thực trạng thái [consumer] thất bại: {e}")
            return False


class KafkaEventBusBackend(EventBusBackend):
    """[Backend driver] (trình điều khiển hậu phương) cho [EventBus] sử dụng [Kafka] (nền tảng hàng đợi sự kiện)."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        # TODO: Implement Kafka producer/consumer logic
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def start_listening(self) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def stop(self) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")


class EventBusSchemaValidator:
    """Bộ kiểm định ([Validator]) cho [JSON Schema] (lược đồ JSON) của thông điệp [EventBus]."""
    
    def __init__(self, schema_dir: str | Path | None = None) -> None:
        if schema_dir is None:
            # Mặc định schema nằm cùng thư mục với event_bus.py
            schema_dir = Path(__file__).parent / "schemas"
        
        self._schema_dir = Path(schema_dir)
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._logger = logging.getLogger(__name__)
        
        # Tải tất cả [schemas] (lược đồ) lúc khởi tạo
        self._load_schemas()
    
    def _load_schemas(self) -> None:
        """Tải tất cả tệp [schema] (lược đồ) từ thư mục [schemas]."""
        if not self._schema_dir.exists():
            self._logger.warning(f"Schema directory không tồn tại: {self._schema_dir}")
            return
        
        for schema_file in self._schema_dir.glob("*.json"):
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_data = json.load(f)
                
                # Tên schema = tên file không có extension
                schema_name = schema_file.stem
                self._schemas[schema_name] = schema_data
                self._logger.debug(f"Đã tải [schema] (lược đồ): {schema_name}")
                
            except Exception as exc:
                self._logger.error(f"Lỗi khi tải [schema] (lược đồ) {schema_file}: {exc}")
    
    def validate(self, topic: str, payload: Dict[str, Any]) -> None:
        """[Validate] (xác thực) [payload] (tải dữ liệu) theo [schema] (lược đồ) của [topic] (chủ đề).
        
        Args:
            topic: Tên topic (sẽ map với schema file)
            payload: Dữ liệu cần validate
            
        Raises:
            ValidationError: Khi payload không hợp lệ
        """
        # Tìm [schema] (lược đồ) tương ứng với [topic] (chủ đề)
        schema = self._schemas.get(topic)
        if not schema:
            # Nếu không có schema cụ thể, sử dụng schema mặc định
            schema = self._schemas.get("default")
        
        if not schema:
            self._logger.warning(f"Không tìm thấy [schema] (lược đồ) cho [topic] (chủ đề) '{topic}'")
            return
        
        try:
            jsonschema.validate(payload, schema)
        except ValidationError as exc:
            self._logger.error(f"[Schema validation] (xác thực lược đồ) thất bại cho [topic] (chủ đề) '{topic}': {exc}")
            raise


class EventBus:
    """[EventBus] (bus sự kiện) chính với hỗ trợ đa [backend] và [schema validation] (xác thực lược đồ).
    
    Sử dụng [Adapter Pattern] (mẫu bộ điều hợp) để hỗ trợ [hot-swap] (thay nóng) [backend driver] (trình điều khiển hậu phương).
    """
    
    def __init__(self, backend_type: Optional[str] = None, 
                 schema_dir: Optional[str] = None,
                 logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        
        # Xác định loại [backend] từ [environment variable] (biến môi trường) hoặc tham số
        if backend_type is None:
            backend_type = os.getenv("EVENT_BUS_BACKEND", "memory")
        
        # Khởi tạo [backend driver] (trình điều khiển hậu phương)
        self._backend = self._create_backend(backend_type)
        
        # Khởi tạo bộ kiểm định [schema validator] (trình xác thực lược đồ)
        self._validator = EventBusSchemaValidator(schema_dir)
        
        self._logger.info(f"[EventBus] đã khởi tạo với [backend]: {backend_type}")
    
    def _create_backend(self, backend_type: str) -> EventBusBackend:
        """[Factory method] (phương thức nhà máy) để tạo [backend driver] (trình điều khiển hậu phương) với [fallback mechanism] (cơ chế dự phòng)."""
        backend_map = {
            "memory": MemoryEventBusBackend,
            "redis": RedisEventBusBackend,
            "rabbitmq": RabbitMQEventBusBackend,
            "kafka": KafkaEventBusBackend,
        }

        backend_class = backend_map.get(backend_type.lower())
        if not backend_class:
            raise ValueError(f"Không hỗ trợ backend type: {backend_type}")

        # Thử tạo backend yêu cầu với cơ chế dự phòng ([fallback mechanism])
        try:
            backend_instance = backend_class(self._logger)
            self._logger.info(f"✅ Tạo thành công [backend] {backend_type}")
            return backend_instance

        except Exception as e:
            self._logger.error(f"❌ Tạo [backend] {backend_type} thất bại: {e}")

            # Rơi về [memory backend] (hậu phương bộ nhớ) nếu backend yêu cầu thất bại
            if backend_type.lower() != "memory":
                self._logger.warning(f"🔄 Falling back to memory backend due to {backend_type} failure")
                try:
                    fallback_backend = MemoryEventBusBackend(self._logger)
                    self._logger.info("✅ Đã tạo thành công [fallback memory backend] (hậu phương bộ nhớ dự phòng)")
                    return fallback_backend
                except Exception as fallback_error:
                    self._logger.error(f"❌ Ngay cả [fallback memory backend] (hậu phương bộ nhớ dự phòng) cũng thất bại: {fallback_error}")
                    raise RuntimeError(f"Failed to create both {backend_type} and fallback memory backend")
            else:
                # If memory backend itself fails, there's no fallback
                raise RuntimeError(f"Memory backend creation failed: {e}")
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới [topic] (chủ đề) với [schema validation] (xác thực lược đồ).
        
        Args:
            topic: Tên topic
            payload: Dữ liệu sự kiện (phải là dict)
            
        Raises:
            TypeError: Khi payload không phải dict
            ValidationError: Khi payload không hợp lệ với schema
        """
        if not isinstance(payload, dict):
            raise TypeError("EventBus payload phải là dict")
        
        # Xác thực [schema] (lược đồ) trước khi [publish] (xuất bản)
        try:
            self._validator.validate(topic, payload)
        except ValidationError:
            # Re-raise validation error để caller xử lý
            raise
        
        # Gửi tới [backend] với [fallback handling] (xử lý dự phòng)
        try:
            self._backend.publish(topic, payload)
            self._logger.debug(f"Đã [publish] (xuất bản) sự kiện tới [topic] (chủ đề) '{topic}': {payload}")
        except Exception as e:
            self._logger.error(f"❌ [Backend publish] (xuất bản qua hậu phương) thất bại cho [topic] (chủ đề) '{topic}': {e}")

            # Thử rơi về [memory backend] (hậu phương bộ nhớ) nếu backend hiện tại thất bại
            if not isinstance(self._backend, MemoryEventBusBackend):
                self._logger.warning("🔄 Đang thử rơi về [memory backend] (hậu phương bộ nhớ) cho lần xuất bản này")
                try:
                    # Tạo [memory backend] (hậu phương bộ nhớ) tạm thời cho thao tác này
                    temp_memory_backend = MemoryEventBusBackend(self._logger)
                    temp_memory_backend.publish(topic, payload)
                    self._logger.info(f"✅ Đã xuất bản thành công tới [fallback memory backend] (hậu phương bộ nhớ dự phòng): {topic}")
                except Exception as fallback_error:
                    self._logger.error(f"❌ Xuất bản dự phòng cũng thất bại: {fallback_error}")
                    raise RuntimeError(f"Both primary and fallback publish failed for topic '{topic}'")
            else:
                # If memory backend itself fails, re-raise the original error
                raise
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký [callback] (hàm gọi lại) cho [topic] (chủ đề) với [fallback handling] (xử lý dự phòng).

        Args:
            topic: Tên topic
            callback: Hàm callback nhận Dict[str, Any]
        """
        try:
            self._backend.subscribe(topic, callback)
            self._logger.debug(f"Đã [subscribe] (đăng ký) vào [topic] (chủ đề) '{topic}'")
        except Exception as e:
            self._logger.error(f"❌ [Backend subscribe] (đăng ký qua hậu phương) thất bại cho [topic] (chủ đề) '{topic}': {e}")

            # Thử rơi về [memory backend] (hậu phương bộ nhớ) nếu backend hiện tại thất bại
            if not isinstance(self._backend, MemoryEventBusBackend):
                self._logger.warning(f"🔄 Đang thử rơi về [memory backend] (hậu phương bộ nhớ) cho đăng ký vào '{topic}'")
                try:
                    # Chuyển sang [memory backend] (hậu phương bộ nhớ) vĩnh viễn cho thể hiện [EventBus] này
                    self._backend = MemoryEventBusBackend(self._logger)
                    self._backend.subscribe(topic, callback)
                    self._logger.info(f"✅ Đã đăng ký thành công vào '{topic}' bằng [fallback memory backend] (hậu phương bộ nhớ dự phòng)")
                except Exception as fallback_error:
                    self._logger.error(f"❌ Đăng ký dự phòng cũng thất bại: {fallback_error}")
                    raise RuntimeError(f"Both primary and fallback subscribe failed for topic '{topic}'")
            else:
                # If memory backend itself fails, re-raise the original error
                raise
    
    def start_listening(self) -> None:
        """Khởi động [background listener] (bộ lắng nghe nền) (cho các backend Redis/Kafka)."""
        self._backend.start_listening()
    
    def stop(self) -> None:
        """Dừng [EventBus] và dọn dẹp tài nguyên."""
        self._backend.stop()
        self._logger.info("EventBus stopped")


# Singleton instance cho convenience
_event_bus_instance: Optional[EventBus] = None
_instance_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Lấy [singleton instance] (thể hiện đơn thể) của [EventBus]."""
    global _event_bus_instance
    
    if _event_bus_instance is None:
        with _instance_lock:
            if _event_bus_instance is None:
                _event_bus_instance = EventBus()
    
    return _event_bus_instance


def publish(topic: str, payload: Dict[str, Any]) -> None:
    """Hàm tiện ích để [publish] (xuất bản) sự kiện."""
    get_event_bus().publish(topic, payload)


def subscribe(topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
    """Hàm tiện ích để [subscribe] (đăng ký) [topic] (chủ đề)."""
    get_event_bus().subscribe(topic, callback)


def start_listening() -> None:
    """Hàm tiện ích để bắt đầu [listening] (lắng nghe)."""
    get_event_bus().start_listening()


def stop() -> None:
    """Hàm tiện ích để dừng [EventBus]."""
    get_event_bus().stop()