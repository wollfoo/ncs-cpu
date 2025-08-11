"""
workload_distributor.py

Intelligent Workload Distribution for Optimal CPU Utilization
Provides advanced task partitioning và load balancing cho 8-core systems.

Author: Claude AI Optimization Framework
Target: Maximize CPU efficiency across cores
Goal: Even load distribution với adaptive performance tuning
"""

import time
import logging
import threading
import queue
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import statistics
import psutil


@dataclass
class CorePerformanceProfile:
    """Performance characteristics của một CPU core"""
    core_id: int
    base_performance: float = 1.0
    current_load: float = 0.0
    average_task_time: float = 0.0
    tasks_completed: int = 0
    success_rate: float = 1.0
    thermal_status: str = "normal"  # normal, warm, hot
    last_update: float = field(default_factory=time.time)


@dataclass
class TaskProfile:
    """Đặc điểm của một loại task"""
    task_type: str
    estimated_complexity: float  # 1.0 = baseline
    preferred_cores: List[int] = field(default_factory=list)
    memory_requirement: int = 0  # MB
    cache_sensitivity: float = 1.0  # Higher = more cache sensitive
    parallel_efficiency: float = 1.0  # How well it scales across cores


class AdaptiveLoadBalancer:
    """
    Advanced load balancer với real-time performance adaptation
    """
    
    def __init__(self, cores: int = 8, logger: Optional[logging.Logger] = None):
        self.cores = cores
        self.logger = logger or logging.getLogger(__name__)
        
        # Core performance tracking
        self.core_profiles = {
            i: CorePerformanceProfile(core_id=i) 
            for i in range(cores)
        }
        
        # Load balancing strategies
        self.balancing_strategy = "adaptive"  # adaptive, round_robin, performance_based
        self.adaptation_enabled = True
        self.rebalance_threshold = 0.15  # 15% imbalance triggers rebalancing
        
        # Performance monitoring
        self.monitoring_thread = None
        self.monitoring_active = False
        self.monitoring_interval = 1.0  # seconds
        
        # Task distribution history
        self.distribution_history = []
        self.max_history_size = 100
        
        self.logger.info(f"AdaptiveLoadBalancer initialized for {cores} cores")
    
    def start_monitoring(self):
        """Start background performance monitoring"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="LoadBalancer-Monitor"
        )
        self.monitoring_thread.start()
        self.logger.info("Giám sát hiệu năng (performance monitoring) đã khởi động")
    
    def stop_monitoring(self):
        """Stop background performance monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5.0)
        self.logger.info("Giám sát hiệu năng (performance monitoring) đã dừng")
    
    def _monitoring_loop(self):
        """Background thread for monitoring core performance"""
        while self.monitoring_active:
            try:
                self._update_core_performance()
                self._detect_thermal_issues()
                self._adapt_strategy_if_needed()
                time.sleep(self.monitoring_interval)
            except Exception as e:
                self.logger.error(f"Lỗi trong vòng lặp giám sát (monitoring loop): {e}")
                time.sleep(5.0)
    
    def _update_core_performance(self):
        """Update performance metrics for all cores"""
        try:
            # Get system-wide CPU usage per core
            cpu_percents = psutil.cpu_percent(percpu=True, interval=0.1)
            
            for core_id in range(min(len(cpu_percents), self.cores)):
                profile = self.core_profiles[core_id]
                
                # Update current load
                profile.current_load = cpu_percents[core_id] / 100.0
                profile.last_update = time.time()
                
                # Calculate performance factor based on load vs expected
                if profile.tasks_completed > 0:
                    expected_load = 0.8  # Expect 80% utilization for good performance
                    if profile.current_load > 0:
                        performance_ratio = expected_load / profile.current_load
                        profile.base_performance = (
                            0.8 * profile.base_performance + 
                            0.2 * performance_ratio
                        )
                
        except Exception as e:
            self.logger.error(f"**[error]** (lỗi) updating core performance: {e}")
    
    def _detect_thermal_issues(self):
        """Detect and respond to thermal throttling"""
        try:
            # Get CPU temperatures if available
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                for i, temp_info in enumerate(temps['coretemp']):
                    if i < self.cores and 'core' in temp_info.label.lower():
                        core_id = i
                        temp = temp_info.current
                        
                        profile = self.core_profiles[core_id]
                        
                        if temp > 85:  # Hot
                            profile.thermal_status = "hot"
                            profile.base_performance *= 0.9  # Reduce performance expectation
                        elif temp > 75:  # Warm
                            profile.thermal_status = "warm"
                            profile.base_performance *= 0.95
                        else:
                            profile.thermal_status = "normal"
                            
        except Exception as e:
            self.logger.debug(f"Thermal monitoring not available: {e}")
    
    def _adapt_strategy_if_needed(self):
        """Adapt load balancing strategy based on performance"""
        if not self.adaptation_enabled:
            return
            
        try:
            # Calculate load imbalance
            loads = [profile.current_load for profile in self.core_profiles.values()]
            if loads:
                load_std = statistics.stdev(loads) if len(loads) > 1 else 0
                load_mean = statistics.mean(loads)
                
                if load_mean > 0:
                    coefficient_of_variation = load_std / load_mean
                    
                    if coefficient_of_variation > self.rebalance_threshold:
                        self.logger.info(f"Load imbalance detected: CV={coefficient_of_variation:.3f}, rebalancing...")
                        self._rebalance_cores()
                        
        except Exception as e:
            self.logger.error(f"Strategy adaptation **[error]** (lỗi): {e}")
    
    def _rebalance_cores(self):
        """Rebalance load across cores"""
        # For now, log rebalancing action
        # Full implementation would involve task migration
        overloaded_cores = [
            core_id for core_id, profile in self.core_profiles.items()
            if profile.current_load > 0.9
        ]
        underloaded_cores = [
            core_id for core_id, profile in self.core_profiles.items()
            if profile.current_load < 0.5
        ]
        
        if overloaded_cores and underloaded_cores:
            self.logger.info(f"Rebalancing: Overloaded cores {overloaded_cores}, Underloaded {underloaded_cores}")


class WorkloadDistributor:
    """
    Intelligent workload distribution for optimal CPU utilization.
    Provides task partitioning và load balancing across multiple cores.
    """
    
    def __init__(self, cores: int = 8, logger: Optional[logging.Logger] = None):
        self.cores = cores
        self.logger = logger or logging.getLogger(__name__)
        
        # Load balancer
        self.load_balancer = AdaptiveLoadBalancer(cores, logger)
        
        # Task profiles và performance history
        self.task_profiles: Dict[str, TaskProfile] = {}
        self.execution_history: List[Dict[str, Any]] = []
        
        # Distribution strategies
        self.distribution_strategies = {
            "even_split": self._distribute_even_split,
            "performance_weighted": self._distribute_performance_weighted,
            "cache_aware": self._distribute_cache_aware,
            "thermal_aware": self._distribute_thermal_aware
        }
        self.current_strategy = "performance_weighted"
        
        # Workload characteristics
        self.workload_complexity_factor = 1.0
        self.cache_locality_importance = 0.7
        
        self.logger.info(f"WorkloadDistributor initialized with strategy: {self.current_strategy}")
    
    def start(self):
        """Start the workload distributor"""
        self.load_balancer.start_monitoring()
            self.logger.info("WorkloadDistributor đã khởi động")
    
    def stop(self):
        """Stop the workload distributor"""
        self.load_balancer.stop_monitoring()
            self.logger.info("WorkloadDistributor đã dừng")
    
    def register_task_profile(self, task_type: str, profile: TaskProfile):
        """Register a task profile for optimization"""
        self.task_profiles[task_type] = profile
        self.logger.info(f"Registered task profile: {task_type}")
    
    def partition_workload(self, total_work: int, task_type: str = "default") -> List[Dict[str, Any]]:
        """
        Partition workload based on core performance characteristics.
        
        Args:
            total_work: Total amount of work (iterations, tasks, etc.)
            task_type: Type of task for optimization
            
        Returns:
            List of work packages for each core
        """
        try:
            # Get task profile
            task_profile = self.task_profiles.get(task_type, TaskProfile(task_type="default"))
            
            # Use current distribution strategy
            distribution_func = self.distribution_strategies.get(
                self.current_strategy, 
                self._distribute_performance_weighted
            )
            
            work_packages = distribution_func(total_work, task_profile)
            
            # Record distribution for analysis
            self._record_distribution(total_work, task_type, work_packages)
            
            return work_packages
            
        except Exception as e:
            self.logger.error(f"**[error]** (lỗi) partitioning workload: {e}")
            # Fallback to even distribution
            return self._distribute_even_split(total_work, task_profile)
    
    def _distribute_even_split(self, total_work: int, task_profile: TaskProfile) -> List[Dict[str, Any]]:
        """Simple even distribution across all cores"""
        work_per_core = total_work // self.cores
        remainder = total_work % self.cores
        
        packages = []
        for core_id in range(self.cores):
            work_amount = work_per_core + (1 if core_id < remainder else 0)
            
            package = {
                'core_id': core_id,
                'work_amount': work_amount,
                'task_type': task_profile.task_type,
                'estimated_time': work_amount * task_profile.estimated_complexity,
                'priority': 'normal'
            }
            packages.append(package)
        
        return packages
    
    def _distribute_performance_weighted(self, total_work: int, task_profile: TaskProfile) -> List[Dict[str, Any]]:
        """Distribute based on core performance characteristics"""
        # Get core performance factors
        performance_factors = []
        total_performance = 0
        
        for core_id in range(self.cores):
            profile = self.load_balancer.core_profiles[core_id]
            
            # Calculate performance factor
            factor = profile.base_performance
            
            # Adjust for current load (lower load = can take more work)
            load_factor = max(0.1, 1.0 - profile.current_load)
            factor *= load_factor
            
            # Adjust for thermal status
            if profile.thermal_status == "hot":
                factor *= 0.7
            elif profile.thermal_status == "warm":
                factor *= 0.85
            
            performance_factors.append(factor)
            total_performance += factor
        
        # Distribute work proportionally
        packages = []
        distributed_work = 0
        
        for core_id in range(self.cores):
            if core_id == self.cores - 1:  # Last core gets remainder
                work_amount = total_work - distributed_work
            else:
                proportion = performance_factors[core_id] / total_performance
                work_amount = int(total_work * proportion)
                distributed_work += work_amount
            
            package = {
                'core_id': core_id,
                'work_amount': work_amount,
                'task_type': task_profile.task_type,
                'performance_factor': performance_factors[core_id],
                'estimated_time': work_amount * task_profile.estimated_complexity / performance_factors[core_id],
                'priority': 'high' if performance_factors[core_id] > 1.2 else 'normal'
            }
            packages.append(package)
        
        return packages
    
    def _distribute_cache_aware(self, total_work: int, task_profile: TaskProfile) -> List[Dict[str, Any]]:
        """Distribute với cache locality optimization"""
        packages = self._distribute_performance_weighted(total_work, task_profile)
        
        # Adjust for cache sensitivity
        if task_profile.cache_sensitivity > 1.0:
            # Prefer cores with less cache contention
            for package in packages:
                core_id = package['core_id']
                profile = self.load_balancer.core_profiles[core_id]
                
                # Reduce work for highly loaded cores (less cache available)
                if profile.current_load > 0.8:
                    adjustment = 0.9
                    package['work_amount'] = int(package['work_amount'] * adjustment)
                    package['cache_adjusted'] = True
        
        return packages
    
    def _distribute_thermal_aware(self, total_work: int, task_profile: TaskProfile) -> List[Dict[str, Any]]:
        """Distribute với thermal management"""
        packages = self._distribute_performance_weighted(total_work, task_profile)
        
        # Reduce load on hot cores
        hot_cores = [
            core_id for core_id, profile in self.load_balancer.core_profiles.items()
            if profile.thermal_status in ["hot", "warm"]
        ]
        
        if hot_cores:
            # Redistribute work from hot cores to cool cores
            cool_cores = [i for i in range(self.cores) if i not in hot_cores]
            
            if cool_cores:
                total_reduction = 0
                for package in packages:
                    if package['core_id'] in hot_cores:
                        reduction = int(package['work_amount'] * 0.2)  # 20% reduction
                        package['work_amount'] -= reduction
                        package['thermal_adjusted'] = True
                        total_reduction += reduction
                
                # Distribute reduced work to cool cores
                extra_per_cool_core = total_reduction // len(cool_cores)
                for package in packages:
                    if package['core_id'] in cool_cores:
                        package['work_amount'] += extra_per_cool_core
        
        return packages
    
    def _record_distribution(self, total_work: int, task_type: str, packages: List[Dict[str, Any]]):
        """Record distribution for performance analysis"""
        distribution_record = {
            'timestamp': time.time(),
            'total_work': total_work,
            'task_type': task_type,
            'strategy': self.current_strategy,
            'packages': packages,
            'core_loads': {
                core_id: profile.current_load 
                for core_id, profile in self.load_balancer.core_profiles.items()
            }
        }
        
        self.execution_history.append(distribution_record)
        
        # Limit history size
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-500:]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary and recommendations"""
        core_stats = {}
        for core_id, profile in self.load_balancer.core_profiles.items():
            core_stats[core_id] = {
                'performance': profile.base_performance,
                'current_load': profile.current_load,
                'tasks_completed': profile.tasks_completed,
                'avg_task_time': profile.average_task_time,
                'thermal_status': profile.thermal_status,
                'success_rate': profile.success_rate
            }
        
        # Calculate overall efficiency
        loads = [profile.current_load for profile in self.load_balancer.core_profiles.values()]
        avg_load = statistics.mean(loads) if loads else 0
        load_balance = 1.0 - (statistics.stdev(loads) / avg_load if avg_load > 0 and len(loads) > 1 else 0)
        
        return {
            'core_statistics': core_stats,
            'average_load': avg_load,
            'load_balance_score': load_balance,
            'current_strategy': self.current_strategy,
            'total_distributions': len(self.execution_history),
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        # Check for load imbalance
        loads = [profile.current_load for profile in self.load_balancer.core_profiles.values()]
        if loads:
            load_std = statistics.stdev(loads) if len(loads) > 1 else 0
            if load_std > 0.2:
                recommendations.append("Consider switching to adaptive load balancing")
        
        # Check for thermal issues
        hot_cores = [
            core_id for core_id, profile in self.load_balancer.core_profiles.items()
            if profile.thermal_status == "hot"
        ]
        if hot_cores:
            recommendations.append(f"Thermal throttling detected on cores {hot_cores}")
        
        # Check for underutilized cores
        underutilized = [
            core_id for core_id, profile in self.load_balancer.core_profiles.items()
            if profile.current_load < 0.3
        ]
        if len(underutilized) > 2:
            recommendations.append("Multiple cores underutilized - consider increasing workload")
        
        return recommendations
    
    def update_task_completion(self, core_id: int, task_time: float, success: bool = True):
        """Update performance metrics when task completes"""
        if 0 <= core_id < self.cores:
            profile = self.load_balancer.core_profiles[core_id]
            profile.tasks_completed += 1
            
            # Update average task time
            if profile.average_task_time == 0:
                profile.average_task_time = task_time
            else:
                profile.average_task_time = (
                    0.8 * profile.average_task_time + 0.2 * task_time
                )
            
            # Update success rate
            total_tasks = profile.tasks_completed
            current_successes = profile.success_rate * (total_tasks - 1)
            if success:
                current_successes += 1
            profile.success_rate = current_successes / total_tasks
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Factory functions
def create_balanced_distributor(cores: int = 8, logger: Optional[logging.Logger] = None) -> WorkloadDistributor:
    """Create workload distributor with balanced strategy"""
    distributor = WorkloadDistributor(cores=cores, logger=logger)
    distributor.current_strategy = "performance_weighted"
    return distributor


def create_thermal_aware_distributor(cores: int = 8, logger: Optional[logging.Logger] = None) -> WorkloadDistributor:
    """Create workload distributor with thermal awareness"""
    distributor = WorkloadDistributor(cores=cores, logger=logger)
    distributor.current_strategy = "thermal_aware"
    return distributor


if __name__ == "__main__":
    # Test script
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    try:
        with create_balanced_distributor(cores=8, logger=logger) as distributor:
            logger.info("🚀 Testing WorkloadDistributor...")
            
            # Register a task profile
            crypto_profile = TaskProfile(
                task_type="crypto_hash",
                estimated_complexity=1.2,
                cache_sensitivity=1.5,
                parallel_efficiency=0.95
            )
            distributor.register_task_profile("crypto_hash", crypto_profile)
            
            # Test workload distribution
            total_work = 10000000  # 10M iterations
            packages = distributor.partition_workload(total_work, "crypto_hash")
            
            logger.info(f"📊 Workload Distribution Results:")
            total_distributed = 0
            for package in packages:
                logger.info(f"   Core {package['core_id']}: {package['work_amount']:,} iterations "
                          f"(Est. time: {package['estimated_time']:.2f}s)")
                total_distributed += package['work_amount']
            
            logger.info(f"   Total distributed: {total_distributed:,}/{total_work:,}")
            
            # Simulate some task completions
            for i in range(8):
                distributor.update_task_completion(i, 2.5 + i * 0.3, True)
            
            # Get performance summary
            summary = distributor.get_performance_summary()
            logger.info(f"📈 Performance Summary:")
            logger.info(f"   Average Load: {summary['average_load']:.2f}")
            logger.info(f"   Load Balance Score: {summary['load_balance_score']:.3f}")
            logger.info(f"   Strategy: {summary['current_strategy']}")
            
            if summary['recommendations']:
                logger.info(f"💡 Recommendations:")
                for rec in summary['recommendations']:
                    logger.info(f"   - {rec}")
            
            logger.info("✅ WorkloadDistributor test completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)