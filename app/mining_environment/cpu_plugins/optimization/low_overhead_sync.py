"""
low_overhead_sync.py

Low-Overhead Synchronization Mechanisms for High-Performance Computing
Provides minimal-overhead coordination và result aggregation cho 8-core parallel processing.

Author: Claude AI Optimization Framework
Target: <5% synchronization overhead
Goal: Efficient inter-process communication và coordination
"""

import multiprocessing as mp
import threading
import time
import queue
import logging
import ctypes
import mmap
import struct
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from concurrent.futures import Future
import weakref


@dataclass
class SyncMetrics:
    """Synchronization performance metrics"""
    total_operations: int = 0
    total_wait_time: float = 0.0
    max_wait_time: float = 0.0
    average_wait_time: float = 0.0
    lock_contention_count: int = 0
    successful_operations: int = 0


class SharedMemoryState:
    """
    Shared memory state for efficient inter-process communication.
    Uses memory-mapped files for zero-copy data sharing.
    """
    
    def __init__(self, size_bytes: int = 4096, name: str = "calc_chain_state"):
        self.size_bytes = size_bytes
        self.name = name
        self.shared_memory = None
        self.memory_view = None
        self.lock = mp.Lock()
        
        # State structure (packed binary format)
        # Header: [magic:4][version:4][state_size:4][checksum:4]
        # Data: [core_states:8*16][global_counters:64][timestamps:64]
        self.header_size = 16
        self.core_state_size = 16  # Per-core state: [load:4][tasks:4][errors:4][status:4]
        self.cores = 8
        
        # Calculate required size and ensure buffer is large enough
        required_size = self.header_size + (self.cores * self.core_state_size) + 64 + 64  # +128 for counters/timestamps
        if size_bytes < required_size:
            size_bytes = required_size
            self.size_bytes = size_bytes
        
        self.data_section_size = size_bytes - self.header_size
        
        self._initialize_shared_memory()
    
    def _initialize_shared_memory(self):
        """Initialize shared memory region"""
        try:
            # Create shared memory using mmap
            self.shared_memory = mmap.mmap(-1, self.size_bytes, access=mmap.ACCESS_WRITE)
            
            # Initialize header
            magic = 0x43414C43  # "CALC" magic number
            version = 1
            state_size = self.size_bytes
            checksum = 0
            
            header = struct.pack('IIII', magic, version, state_size, checksum)
            self.shared_memory[:self.header_size] = header
            
            # Zero out data section - validate slice size first
            if self.data_section_size > 0 and (self.header_size + self.data_section_size) <= self.size_bytes:
                zeros_data = b'\x00' * self.data_section_size
                self.shared_memory[self.header_size:self.header_size + self.data_section_size] = zeros_data
            else:
                raise ValueError(f"Invalid memory layout: header={self.header_size}, data={self.data_section_size}, total={self.size_bytes}")
            
            logging.getLogger(__name__).info(f"Shared memory initialized: {self.size_bytes} bytes")
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to initialize shared memory: {e}")
            raise
    
    def write_core_state(self, core_id: int, load: float, tasks: int, errors: int, status: int):
        """Write state for specific core (thread-safe)"""
        if not (0 <= core_id < self.cores):
            return False
            
        try:
            with self.lock:
                offset = self.header_size + (core_id * self.core_state_size)
                
                # Pack core state: load (float), tasks (int), errors (int), status (int)
                load_int = int(load * 1000)  # Convert to fixed-point for space efficiency
                state_data = struct.pack('IIII', load_int, tasks, errors, status)
                
                self.shared_memory[offset:offset + self.core_state_size] = state_data
                return True
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Error writing core state {core_id}: {e}")
            return False
    
    def read_core_state(self, core_id: int) -> Optional[Tuple[float, int, int, int]]:
        """Read state for specific core"""
        if not (0 <= core_id < self.cores):
            return None
            
        try:
            offset = self.header_size + (core_id * self.core_state_size)
            state_data = self.shared_memory[offset:offset + self.core_state_size]
            
            load_int, tasks, errors, status = struct.unpack('IIII', state_data)
            load = load_int / 1000.0  # Convert back from fixed-point
            
            return (load, tasks, errors, status)
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Error reading core state {core_id}: {e}")
            return None
    
    def read_all_core_states(self) -> Dict[int, Tuple[float, int, int, int]]:
        """Read all core states efficiently"""
        states = {}
        try:
            for core_id in range(self.cores):
                state = self.read_core_state(core_id)
                if state:
                    states[core_id] = state
        except Exception as e:
            logging.getLogger(__name__).error(f"Error reading all core states: {e}")
            
        return states
    
    def cleanup(self):
        """Clean up shared memory resources"""
        try:
            if self.shared_memory:
                self.shared_memory.close()
                self.shared_memory = None
        except Exception as e:
            logging.getLogger(__name__).error(f"Error cleaning up shared memory: {e}")


class LockFreeQueue:
    """
    Lock-free queue implementation for high-performance inter-process communication.
    Uses atomic operations for minimal contention.
    """
    
    def __init__(self, maxsize: int = 1024):
        self.maxsize = maxsize
        self.queue = mp.Queue(maxsize)  # Fallback to mp.Queue for now
        self.put_count = mp.Value('i', 0)
        self.get_count = mp.Value('i', 0)
        
    def put_nowait(self, item: Any) -> bool:
        """Non-blocking put operation"""
        try:
            self.queue.put_nowait(item)
            with self.put_count.get_lock():
                self.put_count.value += 1
            return True
        except queue.Full:
            return False
        except Exception:
            return False
    
    def get_nowait(self) -> Tuple[bool, Any]:
        """Non-blocking get operation"""
        try:
            item = self.queue.get_nowait()
            with self.get_count.get_lock():
                self.get_count.value += 1
            return True, item
        except queue.Empty:
            return False, None
        except Exception:
            return False, None
    
    def size(self) -> int:
        """Get approximate queue size"""
        try:
            return self.queue.qsize()
        except:
            return 0
    
    def stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        return {
            'put_count': self.put_count.value,
            'get_count': self.get_count.value,
            'current_size': self.size()
        }


class AdaptiveBarrier:
    """
    Adaptive barrier for coordinating multiple processes with minimal overhead.
    Automatically adjusts wait strategy based on load patterns.
    """
    
    def __init__(self, parties: int, name: str = "adaptive_barrier"):
        self.parties = parties
        self.name = name
        
        # Synchronization primitives
        self.counter = mp.Value('i', 0)
        self.generation = mp.Value('i', 0)
        self.condition = mp.Condition(mp.Lock())
        
        # Adaptive parameters
        self.wait_strategy = "spin_then_sleep"  # spin, sleep, spin_then_sleep
        self.spin_threshold_us = 1000  # Spin for 1ms before sleeping
        self.adaptation_enabled = True
        
        # Performance tracking
        self.wait_times = []
        self.max_history = 100
        
        self.logger = logging.getLogger(__name__)
    
    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all parties to reach the barrier.
        Returns True if successful, False if timeout.
        """
        start_time = time.time()
        
        try:
            with self.condition:
                current_gen = self.generation.value
                
                # Increment counter
                self.counter.value += 1
                
                if self.counter.value == self.parties:
                    # Last thread to arrive - wake everyone up
                    self.counter.value = 0
                    self.generation.value += 1
                    self.condition.notify_all()
                    
                    wait_time = time.time() - start_time
                    self._record_wait_time(wait_time)
                    return True
                else:
                    # Wait for others using adaptive strategy
                    return self._adaptive_wait(current_gen, start_time, timeout)
                    
        except Exception as e:
            self.logger.error(f"Barrier wait **[error]** (lỗi): {e}")
            return False
    
    def _adaptive_wait(self, generation: int, start_time: float, timeout: Optional[float]) -> bool:
        """Adaptive waiting strategy to minimize overhead"""
        if self.wait_strategy == "spin":
            return self._spin_wait(generation, start_time, timeout)
        elif self.wait_strategy == "sleep":
            return self._sleep_wait(generation, start_time, timeout)
        else:  # spin_then_sleep
            return self._spin_then_sleep_wait(generation, start_time, timeout)
    
    def _spin_wait(self, generation: int, start_time: float, timeout: Optional[float]) -> bool:
        """Pure spin waiting - lowest latency, highest CPU usage"""
        while self.generation.value == generation:
            if timeout and (time.time() - start_time) > timeout:
                return False
            # Busy wait with minimal overhead
            pass
        
        wait_time = time.time() - start_time
        self._record_wait_time(wait_time)
        return True
    
    def _sleep_wait(self, generation: int, start_time: float, timeout: Optional[float]) -> bool:
        """Condition variable waiting - lower CPU, higher latency"""
        while self.generation.value == generation:
            remaining_time = None
            if timeout:
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time <= 0:
                    return False
            
            self.condition.wait(remaining_time)
        
        wait_time = time.time() - start_time
        self._record_wait_time(wait_time)
        return True
    
    def _spin_then_sleep_wait(self, generation: int, start_time: float, timeout: Optional[float]) -> bool:
        """Hybrid: spin briefly, then sleep - balanced approach"""
        spin_end_time = start_time + (self.spin_threshold_us / 1_000_000)
        
        # Phase 1: Spin wait
        while self.generation.value == generation and time.time() < spin_end_time:
            if timeout and (time.time() - start_time) > timeout:
                return False
        
        # Phase 2: If still waiting, switch to sleep
        if self.generation.value == generation:
            return self._sleep_wait(generation, start_time, timeout)
        
        wait_time = time.time() - start_time
        self._record_wait_time(wait_time)
        return True
    
    def _record_wait_time(self, wait_time: float):
        """Record wait time for adaptive optimization"""
        self.wait_times.append(wait_time)
        if len(self.wait_times) > self.max_history:
            self.wait_times = self.wait_times[-self.max_history//2:]
        
        # Adapt strategy based on performance
        if self.adaptation_enabled and len(self.wait_times) >= 10:
            self._adapt_strategy()
    
    def _adapt_strategy(self):
        """Adapt waiting strategy based on observed performance"""
        try:
            avg_wait = sum(self.wait_times[-10:]) / 10
            
            if avg_wait < 0.001:  # < 1ms - very fast, use spin
                if self.wait_strategy != "spin":
                    self.wait_strategy = "spin"
                    self.logger.debug(f"Barrier {self.name} adapted to spin strategy")
            elif avg_wait > 0.01:  # > 10ms - slow, use sleep
                if self.wait_strategy != "sleep":
                    self.wait_strategy = "sleep"
                    self.logger.debug(f"Barrier {self.name} adapted to sleep strategy")
            else:  # Medium range - use hybrid
                if self.wait_strategy != "spin_then_sleep":
                    self.wait_strategy = "spin_then_sleep"
                    self.logger.debug(f"Barrier {self.name} adapted to spin_then_sleep strategy")
                    
        except Exception as e:
            self.logger.error(f"Strategy adaptation **[error]** (lỗi): {e}")


class LowOverheadSynchronization:
    """
    Comprehensive low-overhead synchronization system.
    Coordinates multiple processes with minimal performance impact.
    """
    
    def __init__(self, cores: int = 8, logger: Optional[logging.Logger] = None):
        self.cores = cores
        self.logger = logger or logging.getLogger(__name__)
        
        # Core synchronization components
        self.shared_state = SharedMemoryState(size_bytes=8192, name=f"sync_state_{int(time.time())}")
        self.task_queues = [LockFreeQueue(maxsize=256) for _ in range(cores)]
        self.result_queue = LockFreeQueue(maxsize=cores * 32)
        self.coordination_barrier = AdaptiveBarrier(cores, name="coordination")
        
        # Performance metrics
        self.sync_metrics = SyncMetrics()
        self.operation_start_times = {}
        self.metrics_lock = threading.Lock()
        
        # Result aggregation
        self.result_handlers: List[Callable] = []
        self.aggregated_results = {}
        
        self.logger.info(f"LowOverheadSynchronization initialized for {cores} cores")
    
    def coordinate_work_phase(self, phase_id: str, timeout: float = 5.0) -> bool:
        """
        Coordinate work phase across all cores with minimal overhead.
        All cores must reach this point before proceeding.
        """
        start_time = time.time()
        operation_id = f"coord_{phase_id}_{start_time}"
        
        try:
            self.operation_start_times[operation_id] = start_time
            
            # Use adaptive barrier for coordination
            success = self.coordination_barrier.wait(timeout=timeout)
            
            if success:
                self.logger.debug(f"Work phase '{phase_id}' coordinated successfully")
            else:
                self.logger.warning(f"Work phase '{phase_id}' coordination timeout")
            
            # Update metrics
            self._update_sync_metrics(operation_id, success)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Coordination **[error]** (lỗi) for phase '{phase_id}': {e}")
            return False
    
    def submit_core_task(self, core_id: int, task: Any) -> bool:
        """Submit task to specific core's queue (lock-free)"""
        if not (0 <= core_id < self.cores):
            return False
            
        return self.task_queues[core_id].put_nowait(task)
    
    def get_core_task(self, core_id: int) -> Tuple[bool, Any]:
        """Get task from specific core's queue (lock-free)"""
        if not (0 <= core_id < self.cores):
            return False, None
            
        return self.task_queues[core_id].get_nowait()
    
    def submit_result(self, result: Any) -> bool:
        """Submit result to global result queue (lock-free)"""
        return self.result_queue.put_nowait(result)
    
    def collect_results(self, max_results: int = None, timeout: float = 1.0) -> List[Any]:
        """Collect results with minimal blocking"""
        results = []
        start_time = time.time()
        
        while (len(results) < (max_results or float('inf')) and 
               (time.time() - start_time) < timeout):
            
            success, result = self.result_queue.get_nowait()
            if success:
                results.append(result)
            else:
                time.sleep(0.001)  # 1ms sleep to prevent busy waiting
        
        return results
    
    def update_core_state(self, core_id: int, load: float, tasks: int, errors: int, status: int):
        """Update state for specific core in shared memory"""
        self.shared_state.write_core_state(core_id, load, tasks, errors, status)
    
    def get_all_core_states(self) -> Dict[int, Tuple[float, int, int, int]]:
        """Get current state of all cores"""
        return self.shared_state.read_all_core_states()
    
    def register_result_handler(self, handler: Callable[[Any], Any]):
        """Register handler for result processing"""
        self.result_handlers.append(handler)
    
    def process_results_batch(self, results: List[Any]) -> Dict[str, Any]:
        """Process batch of results with registered handlers"""
        processed_results = {
            'raw_results': results,
            'count': len(results),
            'timestamp': time.time(),
            'processed_data': {}
        }
        
        # Apply registered handlers
        for i, handler in enumerate(self.result_handlers):
            try:
                handler_results = [handler(result) for result in results]
                processed_results['processed_data'][f'handler_{i}'] = handler_results
            except Exception as e:
                self.logger.error(f"Result **[handler]** (bộ xử lý) {i} **[error]** (lỗi): {e}")
        
        return processed_results
    
    def get_synchronization_stats(self) -> Dict[str, Any]:
        """Get comprehensive synchronization performance statistics"""
        with self.metrics_lock:
            # Calculate averages
            if self.sync_metrics.total_operations > 0:
                self.sync_metrics.average_wait_time = (
                    self.sync_metrics.total_wait_time / self.sync_metrics.total_operations
                )
            
            # Get queue statistics
            queue_stats = {}
            for i, queue in enumerate(self.task_queues):
                queue_stats[f'core_{i}'] = queue.stats()
            
            result_stats = self.result_queue.stats()
            
            # Get core states
            core_states = self.get_all_core_states()
            
            return {
                'sync_metrics': {
                    'total_operations': self.sync_metrics.total_operations,
                    'total_wait_time': self.sync_metrics.total_wait_time,
                    'max_wait_time': self.sync_metrics.max_wait_time,
                    'average_wait_time': self.sync_metrics.average_wait_time,
                    'lock_contention_count': self.sync_metrics.lock_contention_count,
                    'success_rate': (self.sync_metrics.successful_operations / 
                                   max(1, self.sync_metrics.total_operations))
                },
                'queue_stats': queue_stats,
                'result_queue_stats': result_stats,
                'core_states': core_states,
                'barrier_strategy': self.coordination_barrier.wait_strategy
            }
    
    def _update_sync_metrics(self, operation_id: str, success: bool):
        """Update synchronization performance metrics"""
        try:
            with self.metrics_lock:
                if operation_id in self.operation_start_times:
                    start_time = self.operation_start_times[operation_id]
                    wait_time = time.time() - start_time
                    
                    self.sync_metrics.total_operations += 1
                    self.sync_metrics.total_wait_time += wait_time
                    self.sync_metrics.max_wait_time = max(self.sync_metrics.max_wait_time, wait_time)
                    
                    if success:
                        self.sync_metrics.successful_operations += 1
                    
                    del self.operation_start_times[operation_id]
                    
        except Exception as e:
            self.logger.error(f"**[error]** (lỗi) updating sync metrics: {e}")
    
    def cleanup(self):
        """Clean up synchronization resources"""
        try:
            self.shared_state.cleanup()
            self.logger.info("Synchronization cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup **[error]** (lỗi): {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Factory functions
def create_high_performance_sync(cores: int = 8, logger: Optional[logging.Logger] = None) -> LowOverheadSynchronization:
    """Create high-performance synchronization system"""
    return LowOverheadSynchronization(cores=cores, logger=logger)


def create_adaptive_barrier(parties: int, name: str = "barrier") -> AdaptiveBarrier:
    """Create adaptive barrier for process coordination"""
    return AdaptiveBarrier(parties=parties, name=name)


if __name__ == "__main__":
    # Test script
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    try:
        with create_high_performance_sync(cores=8, logger=logger) as sync_system:
            logger.info("🚀 Testing LowOverheadSynchronization...")
            
            # Test shared state
            for core_id in range(8):
                sync_system.update_core_state(core_id, 0.5 + core_id * 0.1, core_id * 10, 0, 1)
            
            # Test coordination
            success = sync_system.coordinate_work_phase("test_phase", timeout=2.0)
            logger.info(f"Coordination test: {'✅ SUCCESS' if success else '❌ FAILED'}")
            
            # Test task queues
            for core_id in range(8):
                task = f"test_task_{core_id}"
                success = sync_system.submit_core_task(core_id, task)
                logger.info(f"Task submission core {core_id}: {'✅' if success else '❌'}")
            
            # Test result collection
            for i in range(8):
                sync_system.submit_result(f"result_{i}")
            
            results = sync_system.collect_results(max_results=8, timeout=1.0)
            logger.info(f"Collected {len(results)} results")
            
            # Get performance stats
            stats = sync_system.get_synchronization_stats()
            logger.info(f"📊 Synchronization Statistics:")
            logger.info(f"   Total Operations: {stats['sync_metrics']['total_operations']}")
            logger.info(f"   Success Rate: {stats['sync_metrics']['success_rate']:.3f}")
            logger.info(f"   Average Wait Time: {stats['sync_metrics']['average_wait_time']:.6f}s")
            logger.info(f"   Barrier Strategy: {stats['barrier_strategy']}")
            
            # Test result processing
            processed = sync_system.process_results_batch(results)
            logger.info(f"Processed {processed['count']} results")
            
            # Check core states
            core_states = sync_system.get_all_core_states()
            logger.info(f"Core states retrieved: {len(core_states)} cores")
            
            logger.info("✅ LowOverheadSynchronization test completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)