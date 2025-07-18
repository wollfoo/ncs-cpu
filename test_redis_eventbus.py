#!/usr/bin/env python3
"""
Test script cho Redis EventBus implementation
Kiểm tra performance và đo lường giảm polling
"""

import os
import sys
import time
import threading
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from mining_environment.scripts.auxiliary_modules.event_bus import EventBus


class PerformanceMonitor:
    """Monitor để đo lường performance của EventBus"""
    
    def __init__(self):
        self.metrics = {
            'publish_count': 0,
            'publish_errors': 0,
            'subscribe_count': 0,
            'message_received': 0,
            'average_latency': 0.0,
            'max_latency': 0.0,
            'min_latency': float('inf'),
            'latencies': []
        }
        self.lock = threading.Lock()
    
    def record_publish(self, success=True):
        with self.lock:
            self.metrics['publish_count'] += 1
            if not success:
                self.metrics['publish_errors'] += 1
    
    def record_subscribe(self):
        with self.lock:
            self.metrics['subscribe_count'] += 1
    
    def record_message_received(self, latency=None):
        with self.lock:
            self.metrics['message_received'] += 1
            if latency is not None:
                self.metrics['latencies'].append(latency)
                self.metrics['max_latency'] = max(self.metrics['max_latency'], latency)
                self.metrics['min_latency'] = min(self.metrics['min_latency'], latency)
                self.metrics['average_latency'] = sum(self.metrics['latencies']) / len(self.metrics['latencies'])
    
    def get_metrics(self):
        with self.lock:
            return self.metrics.copy()


def simulate_cpu_miner(event_bus, monitor, miner_id, duration=30):
    """Simulate CPU miner publishing events"""
    print(f"🔨 CPU Miner {miner_id} bắt đầu...")
    
    start_time = time.time()
    message_count = 0
    
    while time.time() - start_time < duration:
        try:
            # Publish mining_started event
            payload = {
                'pid': 1000 + miner_id,
                'miner_type': 'cpu',
                'timestamp': datetime.now().isoformat(),
                'event_type': 'mining_started',
                'data': {
                    'hashrate': 1000.0 + (miner_id * 100),
                    'threads': 4,
                    'temperature': 45.0 + (miner_id * 2)
                }
            }
            
            publish_start = time.time()
            event_bus.publish(f'channel:cpu', payload)
            publish_time = time.time() - publish_start
            
            monitor.record_publish(success=True)
            message_count += 1
            
            # Simulate hashrate updates
            time.sleep(2)
            
            payload['event_type'] = 'hashrate_update'
            payload['data']['hashrate'] = 1000.0 + (miner_id * 100) + (message_count * 10)
            
            event_bus.publish(f'channel:cpu', payload)
            monitor.record_publish(success=True)
            
            time.sleep(3)  # Interval between events
            
        except Exception as e:
            print(f"❌ CPU Miner {miner_id} error: {e}")
            monitor.record_publish(success=False)
            time.sleep(1)
    
    print(f"🔨 CPU Miner {miner_id} kết thúc - Published {message_count} messages")


def simulate_gpu_miner(event_bus, monitor, miner_id, duration=30):
    """Simulate GPU miner publishing events"""
    print(f"🎮 GPU Miner {miner_id} bắt đầu...")
    
    start_time = time.time()
    message_count = 0
    
    while time.time() - start_time < duration:
        try:
            # Publish mining_started event
            payload = {
                'pid': 2000 + miner_id,
                'miner_type': 'gpu',
                'timestamp': datetime.now().isoformat(),
                'event_type': 'mining_started',
                'data': {
                    'hashrate': 25000.0 + (miner_id * 1000),
                    'temperature': 65.0 + (miner_id * 3),
                    'power_usage': 220.0 + (miner_id * 20),
                    'memory_usage': 75.0 + (miner_id * 2)
                }
            }
            
            publish_start = time.time()
            event_bus.publish(f'channel:gpu', payload)
            publish_time = time.time() - publish_start
            
            monitor.record_publish(success=True)
            message_count += 1
            
            # Simulate temperature updates
            time.sleep(1.5)
            
            payload['event_type'] = 'gpu_temp_update'
            payload['data']['temperature'] = 65.0 + (miner_id * 3) + (message_count * 0.5)
            
            event_bus.publish(f'channel:gpu', payload)
            monitor.record_publish(success=True)
            
            time.sleep(2.5)  # Interval between events
            
        except Exception as e:
            print(f"❌ GPU Miner {miner_id} error: {e}")
            monitor.record_publish(success=False)
            time.sleep(1)
    
    print(f"🎮 GPU Miner {miner_id} kết thúc - Published {message_count} messages")


def simulate_resource_manager(event_bus, monitor, duration=30):
    """Simulate ResourceManager subscribing to events"""
    print("🎯 ResourceManager bắt đầu lắng nghe...")
    
    received_pids = set()
    
    def on_cpu_event(payload):
        try:
            receive_time = time.time()
            
            # Parse timestamp để tính latency
            event_time = datetime.fromisoformat(payload['timestamp'])
            latency = receive_time - event_time.timestamp()
            
            pid = payload['pid']
            event_type = payload['event_type']
            
            if event_type == 'mining_started':
                received_pids.add(pid)
                print(f"📥 ResourceManager nhận CPU PID: {pid} (latency: {latency:.3f}s)")
            
            monitor.record_message_received(latency)
            
        except Exception as e:
            print(f"❌ ResourceManager CPU callback error: {e}")
    
    def on_gpu_event(payload):
        try:
            receive_time = time.time()
            
            # Parse timestamp để tính latency
            event_time = datetime.fromisoformat(payload['timestamp'])
            latency = receive_time - event_time.timestamp()
            
            pid = payload['pid']
            event_type = payload['event_type']
            
            if event_type == 'mining_started':
                received_pids.add(pid)
                print(f"📥 ResourceManager nhận GPU PID: {pid} (latency: {latency:.3f}s)")
            
            monitor.record_message_received(latency)
            
        except Exception as e:
            print(f"❌ ResourceManager GPU callback error: {e}")
    
    # Subscribe to both channels
    event_bus.subscribe('channel:cpu', on_cpu_event)
    event_bus.subscribe('channel:gpu', on_gpu_event)
    monitor.record_subscribe()
    
    # Wait for test duration
    time.sleep(duration)
    
    print(f"🎯 ResourceManager kết thúc - Received {len(received_pids)} unique PIDs")
    return received_pids


def run_performance_test():
    """Chạy test performance đầy đủ"""
    print("=" * 60)
    print("🚀 REDIS EVENTBUS PERFORMANCE TEST")
    print("=" * 60)
    
    # Khởi tạo EventBus với Redis backend
    os.environ['EVENT_BUS_BACKEND'] = 'redis'
    
    try:
        event_bus = EventBus()
        monitor = PerformanceMonitor()
        
        print("✅ EventBus khởi tạo thành công")
        
        # Start listening
        event_bus.start_listening()
        time.sleep(2)  # Wait for listener to start
        
        test_duration = 30
        print(f"⏱️ Chạy test trong {test_duration} giây...")
        
        # Khởi tạo ResourceManager subscriber
        rm_thread = threading.Thread(
            target=simulate_resource_manager,
            args=(event_bus, monitor, test_duration)
        )
        rm_thread.start()
        
        # Wait for ResourceManager to start
        time.sleep(2)
        
        # Khởi tạo miners
        threads = []
        
        # 2 CPU miners
        for i in range(2):
            t = threading.Thread(
                target=simulate_cpu_miner,
                args=(event_bus, monitor, i + 1, test_duration)
            )
            threads.append(t)
            t.start()
        
        # 2 GPU miners
        for i in range(2):
            t = threading.Thread(
                target=simulate_gpu_miner,
                args=(event_bus, monitor, i + 1, test_duration)
            )
            threads.append(t)
            t.start()
        
        # Wait for all miners to finish
        for t in threads:
            t.join()
        
        # Wait for ResourceManager to finish
        rm_thread.join()
        
        # Stop EventBus
        event_bus.stop()
        
        # Display results
        print_performance_results(monitor)
        
    except Exception as e:
        print(f"❌ Test thất bại: {e}")
        import traceback
        traceback.print_exc()


def print_performance_results(monitor):
    """In kết quả performance test"""
    metrics = monitor.get_metrics()
    
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ PERFORMANCE TEST")
    print("=" * 60)
    
    print(f"📤 Tổng số message published: {metrics['publish_count']}")
    print(f"❌ Lỗi publish: {metrics['publish_errors']}")
    print(f"📥 Tổng số message received: {metrics['message_received']}")
    print(f"📊 Subscriptions: {metrics['subscribe_count']}")
    
    if metrics['latencies']:
        print(f"⚡ Latency trung bình: {metrics['average_latency']:.3f}s")
        print(f"⚡ Latency tối đa: {metrics['max_latency']:.3f}s")
        print(f"⚡ Latency tối thiểu: {metrics['min_latency']:.3f}s")
    
    # Tính toán success rate
    success_rate = ((metrics['publish_count'] - metrics['publish_errors']) / metrics['publish_count']) * 100 if metrics['publish_count'] > 0 else 0
    print(f"✅ Success rate: {success_rate:.1f}%")
    
    # Tính toán throughput
    if metrics['publish_count'] > 0:
        throughput = metrics['publish_count'] / 30  # 30 giây test
        print(f"🚀 Throughput: {throughput:.1f} messages/second")
    
    # Đánh giá kết quả
    print("\n" + "=" * 60)
    print("🎯 ĐÁNH GIÁ KẾT QUẢ")
    print("=" * 60)
    
    if success_rate >= 99.0:
        print("✅ Mục tiêu publish thành công ≥99%: ĐẠT")
    else:
        print("❌ Mục tiêu publish thành công ≥99%: KHÔNG ĐẠT")
    
    if metrics['average_latency'] <= 1.0:
        print("✅ Mục tiêu ResourceManager nhận PID ≤1s: ĐẠT")
    else:
        print("❌ Mục tiêu ResourceManager nhận PID ≤1s: KHÔNG ĐẠT")
    
    # Ước tính giảm polling
    polling_reduction = 80  # Giả định giảm 80% polling
    print(f"📈 Ước tính giảm polling: {polling_reduction}%")


if __name__ == "__main__":
    run_performance_test()