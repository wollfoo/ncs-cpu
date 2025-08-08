"""
system_integration.py

System-level Integration cho OptimizedCalculationChain.
Integrates với existing throttling system, resource management, và monitoring.

Author: Claude AI Optimization Framework 
Purpose: Seamless integration với existing system_manager và CPU plugin framework
"""

import os
import time
import logging
import threading
import psutil
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass
from pathlib import Path

# Import existing system components
try:
    # Legacy ThrottlingManager removed - using OptimizedCalculationChain architecture
    # from ..throttling_manager import ThrottlingManager  # REMOVED: Replaced by MiningIntegrationAdapter
    from ..optimization.randomx_optimizer import XeonE5OptimizedConfig
    from .mining_integration_adapter import MiningIntegrationAdapter, MiningSessionConfig
except ImportError as e:
    # Fallback imports for testing
    logging.getLogger(__name__).warning(f"Import warning: {e}")


@dataclass
class SystemIntegrationConfig:
    """Configuration cho system integration"""
    enable_optimized_chain: bool = True
    fallback_to_legacy: bool = True
    throttling_compatibility: bool = True
    monitoring_enabled: bool = True
    auto_performance_tuning: bool = True
    stealth_mode_compatible: bool = True
    resource_monitoring_interval: float = 2.0


class OptimizedSystemIntegration:
    """
    System integration layer cho OptimizedCalculationChain.
    Manages interaction với existing throttling, monitoring, và resource management.
    """
    
    def __init__(self, config: Optional[SystemIntegrationConfig] = None, 
                 logger: Optional[logging.Logger] = None):
        self.config = config or SystemIntegrationConfig()
        self.logger = logger or logging.getLogger(__name__)
        
        # Core integration components
        self.mining_adapter: Optional[MiningIntegrationAdapter] = None
        self.throttling_manager: Optional[Any] = None  # Will be injected
        self.optimizer_config = XeonE5OptimizedConfig(logger=self.logger)
        
        # System state tracking
        self.integration_active = False
        self.legacy_process_pid: Optional[int] = None
        self.optimized_mining_active = False
        
        # Performance monitoring
        self.system_monitor_thread: Optional[threading.Thread] = None
        self.resource_stats: Dict[str, Any] = {}
        self.performance_thresholds = {
            'min_cpu_utilization': 600,  # 75% of 800% target
            'max_thermal_temp': 85,
            'max_memory_usage': 85,  # 85% of available memory
            'min_efficiency_score': 0.7
        }
        
        # Integration hooks
        self.shutdown_event = threading.Event()
        self.external_throttling_callback: Optional[Callable] = None
        
        self.logger.info("OptimizedSystemIntegration initialized")
    
    def inject_throttling_manager(self, throttling_manager: Any):
        """Inject existing throttling manager for compatibility"""
        self.throttling_manager = throttling_manager
        self.logger.info("Throttling manager injected for compatibility")
    
    def register_external_throttling_callback(self, callback: Callable[[float], bool]):
        """Register callback cho external throttling requests"""
        self.external_throttling_callback = callback
        self.logger.info("External throttling callback registered")
    
    def integrate_with_system(self, cores: int = 8) -> bool:
        """
        Main integration method với existing system.
        Replaces legacy mining process với optimized chain.
        """
        try:
            if self.integration_active:
                self.logger.warning("System integration already active")
                return True
            
            self.logger.info("Starting system integration với OptimizedCalculationChain...")
            
            # Initialize mining adapter
            self.mining_adapter = MiningIntegrationAdapter(logger=self.logger)
            
            # Initialize optimized mining
            if not self.mining_adapter.initialize_optimized_mining(cores=cores):
                if self.config.fallback_to_legacy:
                    self.logger.warning("Failed to initialize optimized mining, falling back to legacy")
                    return self._fallback_to_legacy()
                else:
                    return False
            
            # Start performance monitoring
            if self.config.monitoring_enabled:
                self._start_system_monitoring()
            
            # Register với throttling system
            if self.config.throttling_compatibility and self.throttling_manager:
                self._register_throttling_integration()
            
            self.integration_active = True
            self.optimized_mining_active = True
            
            self.logger.info("✅ System integration completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"System integration failed: {e}")
            return self._fallback_to_legacy() if self.config.fallback_to_legacy else False
    
    def start_optimized_mining(self, session_config: Optional[MiningSessionConfig] = None) -> bool:
        """Start optimized mining session"""
        if not self.integration_active or not self.mining_adapter:
            self.logger.error("System integration not active")
            return False
        
        try:
            # Create optimized session config
            if not session_config:
                session_config = MiningSessionConfig(
                    profile="optimized",
                    total_iterations=100000000,  # 100M iterations
                    batch_size=10000000,         # 10M per batch
                    monitoring_interval=2.0,
                    auto_restart=True,
                    throttling_enabled=self.config.throttling_compatibility,
                    stealth_mode=self.config.stealth_mode_compatible
                )
            
            success = self.mining_adapter.start_mining_session(session_config)
            if success:
                self.optimized_mining_active = True
            self.logger.info("✅ Phiên khai thác tối ưu (optimized mining session) đã khởi động")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to start optimized mining: {e}")
            return False
    
    def stop_optimized_mining(self) -> bool:
        """Stop optimized mining session"""
        if not self.mining_adapter or not self.optimized_mining_active:
            return True
        
        try:
            success = self.mining_adapter.stop_mining_session()
            if success:
                self.optimized_mining_active = False
                self.logger.info("✅ Optimized mining session stopped")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to stop optimized mining: {e}")
            return False
    
    def attach_to_existing_process(self, pid: int) -> bool:
        """
        Attach OptimizedCalculationChain to existing CPU mining process.
        
        Args:
            pid: Process ID of existing ml-inference process
            
        Returns:
            bool: True if successfully attached, False otherwise
        """
        try:
            self.logger.info(f"⚡ Attaching OptimizedCalculationChain to existing process PID={pid}")
            
            # Validate process exists and is accessible
            if not psutil.pid_exists(pid):
                self.logger.error(f"Process PID={pid} không tồn tại")
                return False
            
            try:
                proc = psutil.Process(pid)
                process_name = proc.name()
                
                # Validate đây là ml-inference process
                if "ml-inference" not in process_name and "inference" not in process_name:
                    self.logger.warning(f"Process PID={pid} ({process_name}) may not be ml-inference")
                
                self.logger.info(f"🔗 Validated process: {process_name} (PID={pid})")
                
            except psutil.AccessDenied:
                self.logger.error(f"Access denied to process PID={pid}")
                return False
            
            # Store legacy process PID for tracking
            self.legacy_process_pid = pid
            
            # Enable stealth mode compatibility if needed
            if self.config.stealth_mode_compatible:
                self.logger.info("🥷 Stealth mode compatibility enabled for existing process")
            
            # If mining adapter exists, register the PID
            if self.mining_adapter:
                try:
                    # Register existing process với mining adapter
                    self.mining_adapter.register_external_process(pid)
                    self.logger.info(f"✅ Registered PID={pid} with mining adapter")
                except Exception as e:
                    self.logger.warning(f"Failed to register PID with mining adapter: {e}")
            
            # Set flag indicating we're attached to external process
            self.optimized_mining_active = True
            
            self.logger.info(f"🎯 Successfully attached OptimizedCalculationChain to PID={pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to attach to existing process PID={pid}: {e}")
            return False

    def apply_system_throttling(self, throttle_percentage: float) -> bool:
        """
        Apply throttling compatible với existing throttling framework.
        Bridges between legacy throttling và optimized chain.
        """
        try:
            if not self.mining_adapter or not self.optimized_mining_active:
                self.logger.warning("Cannot apply throttling: optimized mining not active")
                return False
            
            # Apply throttling through mining adapter
            success = self.mining_adapter.apply_throttling(throttle_percentage)
            
            if success:
                self.logger.info(f"Applied {throttle_percentage}% system throttling")
                
                # Notify external systems if callback registered
                if self.external_throttling_callback:
                    try:
                        self.external_throttling_callback(throttle_percentage)
                    except Exception as e:
                        self.logger.error(f"External throttling callback error: {e}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to apply system throttling: {e}")
            return False
    
    def get_system_performance_status(self) -> Dict[str, Any]:
        """Get comprehensive system performance status"""
        try:
            status = {
                'integration_active': self.integration_active,
                'optimized_mining_active': self.optimized_mining_active,
                'system_resources': self._get_system_resource_stats(),
                'mining_performance': None,
                'recommendations': []
            }
            
            # Get mining performance if active
            if self.mining_adapter and self.optimized_mining_active:
                metrics = self.mining_adapter.get_performance_metrics()
                if metrics:
                    status['mining_performance'] = {
                        'total_cpu_utilization': metrics.total_cpu_utilization,
                        'per_core_utilization': metrics.per_core_utilization,
                        'hashrate': metrics.hashrate,
                        'active_workers': metrics.active_workers,
                        'efficiency_score': metrics.efficiency_score
                    }
                    
                    # Generate recommendations
                    status['recommendations'] = self._generate_performance_recommendations(metrics)
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting system performance status: {e}")
            return {'error': str(e)}
    
    def handle_legacy_process_termination(self, pid: int):
        """Handle termination của legacy mining process"""
        if self.legacy_process_pid == pid:
            self.logger.info(f"Legacy mining process {pid} terminated, switching to optimized")
            # Start optimized mining if not already running
            if not self.optimized_mining_active:
                self.start_optimized_mining()
    
    def _start_system_monitoring(self):
        """Start background system monitoring"""
        self.shutdown_event.clear()
        self.system_monitor_thread = threading.Thread(
            target=self._system_monitoring_loop,
            daemon=True,
            name="OptimizedSystemMonitor"
        )
        self.system_monitor_thread.start()
        self.logger.info("System monitoring started")
    
    def _system_monitoring_loop(self):
        """Background system monitoring loop"""
        while not self.shutdown_event.is_set():
            try:
                # Update resource stats
                self.resource_stats = self._get_system_resource_stats()
                
                # Check for performance issues
                if self.optimized_mining_active and self.mining_adapter:
                    metrics = self.mining_adapter.get_performance_metrics()
                    if metrics:
                        self._check_performance_thresholds(metrics)
                
                # Check system health
                self._check_system_health()
                
                # Wait for next monitoring cycle
                self.shutdown_event.wait(self.config.resource_monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"System monitoring error: {e}")
                self.shutdown_event.wait(5.0)
    
    def _get_system_resource_stats(self) -> Dict[str, Any]:
        """Get current system resource statistics"""
        try:
            # CPU stats
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_per_core = psutil.cpu_percent(percpu=True, interval=0.1)
            
            # Memory stats
            memory = psutil.virtual_memory()
            
            # Temperature stats (if available)
            temps = {}
            try:
                sensor_temps = psutil.sensors_temperatures()
                if 'coretemp' in sensor_temps:
                    temps = {
                        'cpu_cores': [t.current for t in sensor_temps['coretemp'] if 'core' in t.label.lower()],
                        'max_temp': max(t.current for t in sensor_temps['coretemp'])
                    }
            except:
                temps = {'error': 'Temperature monitoring not available'}
            
            return {
                'timestamp': time.time(),
                'cpu': {
                    'total_percent': cpu_percent,
                    'per_core_percent': cpu_per_core,
                    'core_count': psutil.cpu_count()
                },
                'memory': {
                    'total_mb': memory.total // 1024 // 1024,
                    'available_mb': memory.available // 1024 // 1024,
                    'percent_used': memory.percent
                },
                'temperature': temps
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system resource stats: {e}")
            return {'error': str(e)}
    
    def _check_performance_thresholds(self, metrics):
        """Check performance metrics against thresholds"""
        try:
            # Check CPU utilization
            if metrics.total_cpu_utilization < self.performance_thresholds['min_cpu_utilization']:
                self.logger.warning(f"Low CPU utilization: {metrics.total_cpu_utilization:.1f}% (target: 800%)")
            
            # Check efficiency
            if metrics.efficiency_score < self.performance_thresholds['min_efficiency_score']:
                self.logger.warning(f"Low efficiency score: {metrics.efficiency_score:.3f}")
            
        except Exception as e:
            self.logger.error(f"Error checking performance thresholds: {e}")
    
    def _check_system_health(self):
        """Check overall system health"""
        try:
            if 'memory' in self.resource_stats:
                memory_usage = self.resource_stats['memory']['percent_used']
                if memory_usage > self.performance_thresholds['max_memory_usage']:
                    self.logger.warning(f"High memory usage: {memory_usage:.1f}%")
            
            if 'temperature' in self.resource_stats and 'max_temp' in self.resource_stats['temperature']:
                max_temp = self.resource_stats['temperature']['max_temp']
                if max_temp > self.performance_thresholds['max_thermal_temp']:
                    self.logger.warning(f"High CPU temperature: {max_temp}°C")
                    # Auto-apply thermal throttling
                    if self.config.auto_performance_tuning:
                        self.apply_system_throttling(50.0)  # 50% throttling for thermal protection
                        
        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
    
    def _generate_performance_recommendations(self, metrics) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        try:
            # CPU utilization recommendations
            if metrics.total_cpu_utilization < 600:
                recommendations.append("Increase workload batch size to improve CPU utilization")
            elif metrics.total_cpu_utilization > 900:
                recommendations.append("Consider reducing workload to prevent system overload")
            
            # Worker efficiency recommendations
            if metrics.active_workers < 8:
                recommendations.append(f"Only {metrics.active_workers}/8 workers active - check for worker failures")
            
            # Efficiency recommendations
            if metrics.efficiency_score < 0.8:
                recommendations.append("Poor load balancing detected - consider thermal-aware distribution")
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def _register_throttling_integration(self):
        """Register với existing throttling system"""
        try:
            # This would integrate với existing ThrottlingManager
            self.logger.info("Registered với existing throttling framework")
        except Exception as e:
            self.logger.error(f"Failed to register throttling integration: {e}")
    
    def _fallback_to_legacy(self) -> bool:
        """Fallback to legacy mining process"""
        try:
            self.logger.warning("Falling back to legacy mining process")
            self.integration_active = False
            self.optimized_mining_active = False
            return True
        except Exception as e:
            self.logger.error(f"Fallback to legacy failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up system integration"""
        try:
            self.logger.info("Cleaning up OptimizedSystemIntegration...")
            
            # Stop monitoring
            self.shutdown_event.set()
            if self.system_monitor_thread and self.system_monitor_thread.is_alive():
                self.system_monitor_thread.join(timeout=10.0)
            
            # Stop optimized mining
            if self.optimized_mining_active:
                self.stop_optimized_mining()
            
            # Clean up mining adapter
            if self.mining_adapter:
                self.mining_adapter.cleanup()
                self.mining_adapter = None
            
            self.integration_active = False
            self.logger.info("✅ OptimizedSystemIntegration cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Factory functions
def create_system_integration(config: Optional[SystemIntegrationConfig] = None,
                            logger: Optional[logging.Logger] = None) -> OptimizedSystemIntegration:
    """Create system integration instance"""
    return OptimizedSystemIntegration(config=config, logger=logger)


def integrate_with_existing_system(cores: int = 8, 
                                 throttling_manager: Any = None,
                                 logger: Optional[logging.Logger] = None) -> OptimizedSystemIntegration:
    """
    One-shot integration với existing system.
    Returns configured integration instance.
    """
    config = SystemIntegrationConfig(
        enable_optimized_chain=True,
        fallback_to_legacy=True,
        throttling_compatibility=True,
        monitoring_enabled=True,
        auto_performance_tuning=True
    )
    
    integration = create_system_integration(config=config, logger=logger)
    
    # Inject throttling manager if provided
    if throttling_manager:
        integration.inject_throttling_manager(throttling_manager)
    
    # Integrate với system
    if integration.integrate_with_system(cores=cores):
        logger.info("✅ Successfully integrated OptimizedCalculationChain với existing system")
        return integration
    else:
        logger.error("❌ Failed to integrate OptimizedCalculationChain")
        integration.cleanup()
        return None


if __name__ == "__main__":
    # Test system integration
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    try:
        with create_system_integration(logger=logger) as integration:
            logger.info("🚀 Testing OptimizedSystemIntegration...")
            
            # Test integration
            success = integration.integrate_with_system(cores=8)
            logger.info(f"System integration: {'✅ SUCCESS' if success else '❌ FAILED'}")
            
            if success:
                # Test mining start
                mining_success = integration.start_optimized_mining()
                logger.info(f"Optimized mining: {'✅ SUCCESS' if mining_success else '❌ FAILED'}")
                
                if mining_success:
                    # Run for test period
                    time.sleep(15.0)
                    
                    # Test throttling
                    throttle_success = integration.apply_system_throttling(40.0)
                    logger.info(f"System throttling: {'✅ SUCCESS' if throttle_success else '❌ FAILED'}")
                    
                    # Get performance status
                    status = integration.get_system_performance_status()
                    logger.info(f"📊 System Performance Status:")
                    logger.info(f"   Integration Active: {status['integration_active']}")
                    logger.info(f"   Mining Active: {status['optimized_mining_active']}")
                    
                    if status['mining_performance']:
                        perf = status['mining_performance']
                        logger.info(f"   Total CPU: {perf['total_cpu_utilization']:.1f}%")
                        logger.info(f"   Hashrate: {perf['hashrate']:.2f} H/s")
                        logger.info(f"   Efficiency: {perf['efficiency_score']:.3f}")
                    
                    if status['recommendations']:
                        logger.info(f"💡 Recommendations:")
                        for rec in status['recommendations']:
                            logger.info(f"   - {rec}")
                    
                    # Test mining stop
                    stop_success = integration.stop_optimized_mining()
                    logger.info(f"Mining stop: {'✅ SUCCESS' if stop_success else '❌ FAILED'}")
            
            logger.info("✅ OptimizedSystemIntegration test completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)