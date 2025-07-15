"""
audit_integration.py

Comprehensive Integration Framework cho CPU Optimization & Cloaking Audit.
Tích hợp optimization_logger, debug_support, và original functions để tạo complete audit system.

Author: Claude AI Audit Framework
Purpose: Complete integration của audit logging cho optimization và cloaking systems
"""

import os
import sys
import time
import threading
import logging
import json
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from datetime import datetime

# Import audit components
from .optimization_logger import OptimizationLogger, get_optimization_logger
from .debug_support import DebugSupportSystem, get_debug_system, debug_decorator

# Import original systems để enhance
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class AuditIntegrationManager:
    """
    Manager để integrate audit capabilities với existing optimization và cloaking systems.
    Coordinates optimization logging, debug support, và performance monitoring.
    """
    
    def __init__(self, system_name: str, audit_level: str = "INFO"):
        """
        Initialize AuditIntegrationManager.
        
        Args:
            system_name: Name của system được audit
            audit_level: Audit level (DEBUG, INFO, WARN, ERROR)
        """
        self.system_name = system_name
        self.audit_level = audit_level
        
        # Initialize audit components
        self.optimization_logger = get_optimization_logger(system_name)
        self.debug_system = get_debug_system(system_name, audit_level)
        
        # Audit session tracking
        self.session_id = f"audit_{system_name}_{int(time.time())}"
        self.session_start = time.time()
        self.audit_events: List[Dict[str, Any]] = []
        
        # Integration status
        self.integration_status = {
            'optimization_logging': True,
            'debug_support': True,
            'performance_monitoring': True,
            'error_tracking': True
        }
        
        # Setup audit logging
        self.logger = self._setup_audit_logger()
        self._log_initialization()
    
    def _setup_audit_logger(self) -> logging.Logger:
        """Setup audit logger."""
        logger = logging.getLogger(f"audit.{self.system_name}")
        logger.setLevel(getattr(logging, self.audit_level))
        
        # Audit file handler
        audit_dir = Path("/tmp/audit_logs")
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        audit_handler = logging.FileHandler(
            audit_dir / f"{self.system_name}_audit.log",
            mode='a',
            encoding='utf-8'
        )
        audit_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s [AUDIT] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        audit_handler.setFormatter(formatter)
        logger.addHandler(audit_handler)
        
        return logger
    
    def _log_initialization(self):
        """Log audit system initialization."""
        init_info = {
            'session_id': self.session_id,
            'system_name': self.system_name,
            'audit_level': self.audit_level,
            'integration_status': self.integration_status,
            'initialization_time': datetime.now().isoformat()
        }
        
        self.optimization_logger.log_activation_status(
            "audit_integration",
            "ENABLED",
            init_info
        )
        
        self.logger.info(f"🔍 Audit Integration initialized for {self.system_name}")
    
    def create_audit_decorator(self, component_name: str = None):
        """
        Create comprehensive audit decorator combining optimization logging và debug support.
        
        Args:
            component_name: Name của component (optional)
            
        Returns:
            Comprehensive audit decorator
        """
        def audit_decorator(func: Callable) -> Callable:
            @debug_decorator(self.debug_system)
            def wrapper(*args, **kwargs):
                func_name = func.__name__
                comp_name = component_name or func_name
                
                # Log audit event start
                audit_event = {
                    'event_id': f"{self.session_id}_{len(self.audit_events)}",
                    'component': comp_name,
                    'function': func_name,
                    'event_type': 'function_execution',
                    'start_time': time.time(),
                    'thread_id': threading.current_thread().ident,
                    'args_count': len(args) if args else 0,
                    'kwargs_keys': list(kwargs.keys()) if kwargs else []
                }
                
                try:
                    # Execute function với optimization logging
                    self.optimization_logger.log_function_entry(func_name, args, kwargs)
                    
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Log successful completion
                    self.optimization_logger.log_function_exit(func_name, result, True)
                    self.optimization_logger.log_performance_metrics(func_name, {
                        'execution_time': execution_time,
                        'success': True,
                        'component': comp_name
                    })
                    
                    # Update audit event
                    audit_event.update({
                        'end_time': time.time(),
                        'execution_time': execution_time,
                        'success': True,
                        'result_type': type(result).__name__ if result is not None else None
                    })
                    
                    return result
                    
                except Exception as e:
                    # Log error
                    execution_time = time.time() - audit_event['start_time']
                    
                    self.optimization_logger.log_error_with_context(
                        func_name, 
                        e, 
                        {'component': comp_name, 'args': args, 'kwargs': kwargs}
                    )
                    
                    # Update audit event với error info
                    audit_event.update({
                        'end_time': time.time(),
                        'execution_time': execution_time,
                        'success': False,
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    })
                    
                    raise
                    
                finally:
                    # Store audit event
                    self.audit_events.append(audit_event)
                    
                    # Log CPU metrics if PID available
                    if 'pid' in kwargs:
                        self.optimization_logger.log_cpu_metrics(kwargs['pid'], func_name)
                    elif args and isinstance(args[0], int) and args[0] > 0:
                        try:
                            self.optimization_logger.log_cpu_metrics(args[0], func_name)
                        except:
                            pass  # PID might not be valid
            
            return wrapper
        return audit_decorator
    
    def audit_activation_status(self, component: str, status: str, details: Dict[str, Any] = None):
        """
        Audit component activation status.
        
        Args:
            component: Component name
            status: Activation status
            details: Additional details
        """
        activation_event = {
            'event_type': 'activation_status',
            'component': component,
            'status': status,
            'details': details or {},
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id
        }
        
        self.audit_events.append(activation_event)
        self.optimization_logger.log_activation_status(component, status, details)
        
        status_icon = {
            "ENABLED": "🟢",
            "DISABLED": "🔴", 
            "PARTIAL": "🟡",
            "ERROR": "❌"
        }.get(status, "⚪")
        
        self.logger.info(f"{status_icon} {component}: {status}")
    
    def audit_performance_metrics(self, operation: str, metrics: Dict[str, Any], component: str = None):
        """
        Audit performance metrics.
        
        Args:
            operation: Operation name
            metrics: Performance metrics
            component: Component name (optional)
        """
        perf_event = {
            'event_type': 'performance_metrics',
            'operation': operation,
            'component': component or operation,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id
        }
        
        self.audit_events.append(perf_event)
        self.optimization_logger.log_performance_metrics(operation, metrics)
        
        # Log to audit logger
        metrics_str = " | ".join([f"{k}: {v}" for k, v in metrics.items()])
        self.logger.info(f"📊 PERF [{component or operation}]: {metrics_str}")
    
    def audit_stealth_status(self, component: str, stealth_data: Dict[str, Any]):
        """
        Audit stealth operations status.
        
        Args:
            component: Component name
            stealth_data: Stealth status data
        """
        stealth_event = {
            'event_type': 'stealth_status',
            'component': component,
            'stealth_data': stealth_data,
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id
        }
        
        self.audit_events.append(stealth_event)
        self.optimization_logger.log_stealth_status(component, stealth_data)
        
        # Enhanced stealth logging
        stealth_summary = []
        for key, value in stealth_data.items():
            if key == 'cloaked_processes':
                stealth_summary.append(f"processes: {len(value) if isinstance(value, list) else value}")
            elif key == 'threat_level':
                stealth_summary.append(f"threat: {value}")
            elif isinstance(value, bool):
                stealth_summary.append(f"{key}: {'✅' if value else '❌'}")
            else:
                stealth_summary.append(f"{key}: {value}")
        
        self.logger.info(f"🛡️ STEALTH [{component}]: {' | '.join(stealth_summary)}")
    
    def audit_cpu_metrics(self, pid: int, operation: str, component: str = None):
        """
        Audit CPU metrics cho specific process.
        
        Args:
            pid: Process ID
            operation: Operation name
            component: Component name (optional)
        """
        try:
            import psutil
            process = psutil.Process(pid)
            
            cpu_metrics = {
                'pid': pid,
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_mb': process.memory_info().rss // 1024 // 1024,
                'memory_percent': process.memory_percent(),
                'cpu_affinity': process.cpu_affinity(),
                'status': process.status(),
                'create_time': process.create_time()
            }
            
            cpu_event = {
                'event_type': 'cpu_metrics',
                'pid': pid,
                'operation': operation,
                'component': component or operation,
                'metrics': cpu_metrics,
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id
            }
            
            self.audit_events.append(cpu_event)
            self.optimization_logger.log_cpu_metrics(pid, operation)
            
            self.logger.info(f"💻 CPU [{component or operation}] PID {pid}: "
                           f"{cpu_metrics['cpu_percent']:.1f}% CPU, "
                           f"{cpu_metrics['memory_mb']}MB RAM")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to audit CPU metrics for PID {pid}: {e}")
    
    def get_audit_summary(self) -> Dict[str, Any]:
        """Get comprehensive audit summary."""
        session_duration = time.time() - self.session_start
        
        # Analyze events by type
        events_by_type = {}
        components_analyzed = set()
        
        for event in self.audit_events:
            event_type = event.get('event_type', 'unknown')
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
            
            if 'component' in event:
                components_analyzed.add(event['component'])
        
        # Get optimization and debug reports
        optimization_summary = self.optimization_logger.get_performance_summary()
        debug_report = self.debug_system.get_comprehensive_debug_report()
        
        return {
            'audit_session': {
                'session_id': self.session_id,
                'system_name': self.system_name,
                'audit_level': self.audit_level,
                'session_duration': session_duration,
                'total_events': len(self.audit_events)
            },
            'events_analysis': {
                'events_by_type': events_by_type,
                'components_analyzed': list(components_analyzed),
                'event_rate': len(self.audit_events) / session_duration if session_duration > 0 else 0
            },
            'optimization_summary': optimization_summary,
            'debug_summary': {
                'total_debug_events': debug_report['total_events'],
                'thread_report': debug_report['thread_report'],
                'deadlocks_detected': len(debug_report['deadlock_analysis'])
            },
            'integration_status': self.integration_status,
            'report_timestamp': datetime.now().isoformat()
        }
    
    def export_comprehensive_audit_report(self, output_dir: Optional[str] = None):
        """
        Export comprehensive audit report với all components.
        
        Args:
            output_dir: Output directory (optional)
        """
        if output_dir is None:
            output_dir = f"/tmp/audit_reports/{self.system_name}"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(time.time())
        
        try:
            # Export main audit report
            audit_report = {
                'audit_summary': self.get_audit_summary(),
                'audit_events': self.audit_events,
                'session_details': {
                    'session_id': self.session_id,
                    'system_name': self.system_name,
                    'start_time': self.session_start,
                    'export_time': time.time()
                }
            }
            
            with open(output_path / f"audit_report_{timestamp}.json", 'w', encoding='utf-8') as f:
                json.dump(audit_report, f, indent=2, ensure_ascii=False)
            
            # Export optimization metrics
            self.optimization_logger.export_metrics(output_path / f"optimization_metrics_{timestamp}.json")
            
            # Export debug report
            self.debug_system.export_debug_report(output_path / f"debug_report_{timestamp}.json")
            
            # Create summary report
            summary = self.get_audit_summary()
            with open(output_path / f"audit_summary_{timestamp}.txt", 'w', encoding='utf-8') as f:
                f.write(f"🔍 AUDIT SUMMARY REPORT - {self.system_name}\\n")
                f.write(f"{'='*60}\\n")
                f.write(f"Session ID: {self.session_id}\\n")
                f.write(f"Duration: {summary['audit_session']['session_duration']:.2f} seconds\\n")
                f.write(f"Total Events: {summary['audit_session']['total_events']}\\n")
                f.write(f"Components: {', '.join(summary['events_analysis']['components_analyzed'])}\\n")
                f.write(f"Event Rate: {summary['events_analysis']['event_rate']:.2f} events/sec\\n")
                f.write(f"\\nEvents by Type:\\n")
                for event_type, count in summary['events_analysis']['events_by_type'].items():
                    f.write(f"  {event_type}: {count}\\n")
                f.write(f"\\nOptimization Operations: {summary['optimization_summary']['total_operations']}\\n")
                f.write(f"Debug Events: {summary['debug_summary']['total_debug_events']}\\n")
                f.write(f"Deadlocks Detected: {summary['debug_summary']['deadlocks_detected']}\\n")
                f.write(f"\\nReport generated: {datetime.now().isoformat()}\\n")
            
            self.logger.info(f"📁 Comprehensive audit report exported to: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to export audit report: {e}")
            return None
    
    def cleanup_audit_session(self):
        """Cleanup audit session resources."""
        try:
            # Export final report
            export_path = self.export_comprehensive_audit_report()
            
            # Clear event history
            self.audit_events.clear()
            
            # Log session completion
            session_duration = time.time() - self.session_start
            self.logger.info(f"🏁 Audit session completed: {session_duration:.2f}s, exported to {export_path}")
            
        except Exception as e:
            self.logger.error(f"❌ Error during audit cleanup: {e}")


# Global audit managers
_audit_managers: Dict[str, AuditIntegrationManager] = {}
_audit_lock = threading.Lock()


def get_audit_manager(system_name: str, audit_level: str = "INFO") -> AuditIntegrationManager:
    """
    Get or create AuditIntegrationManager instance.
    
    Args:
        system_name: System name
        audit_level: Audit level
        
    Returns:
        AuditIntegrationManager instance
    """
    with _audit_lock:
        if system_name not in _audit_managers:
            _audit_managers[system_name] = AuditIntegrationManager(system_name, audit_level)
        return _audit_managers[system_name]


def create_comprehensive_audit_decorator(system_name: str, component_name: str = None):
    """
    Create comprehensive audit decorator cho specific system và component.
    
    Args:
        system_name: System name
        component_name: Component name (optional)
        
    Returns:
        Comprehensive audit decorator
    """
    audit_manager = get_audit_manager(system_name)
    return audit_manager.create_audit_decorator(component_name)


def setup_comprehensive_audit_system(audit_level: str = "INFO") -> Dict[str, AuditIntegrationManager]:
    """
    Setup comprehensive audit system cho all major components.
    
    Args:
        audit_level: Audit level (DEBUG, INFO, WARN, ERROR)
        
    Returns:
        Dict of audit managers by component name
    """
    # Major components để audit
    components = [
        'cloaking_lib',
        'cpu_optimization',
        'stealth_execution', 
        'randomx_optimizer',
        'system_integration',
        'cloak_strategies',
        'mining_integration',
        'resource_control'
    ]
    
    audit_managers = {}
    
    for component in components:
        audit_manager = get_audit_manager(component, audit_level)
        audit_managers[component] = audit_manager
        
        # Log audit system setup
        audit_manager.audit_activation_status(
            component,
            "ENABLED",
            {
                'audit_level': audit_level,
                'session_id': audit_manager.session_id,
                'setup_time': datetime.now().isoformat()
            }
        )
    
    print(f"🔍 Comprehensive audit system setup complete for {len(components)} components")
    print(f"📊 Audit level: {audit_level}")
    print(f"📁 Reports will be saved to: /tmp/audit_reports/")
    
    return audit_managers


if __name__ == "__main__":
    # Test comprehensive audit system
    print("🔍 Testing Comprehensive Audit Integration...")
    
    # Setup audit system
    audit_managers = setup_comprehensive_audit_system("DEBUG")
    
    # Test cloaking_lib audit
    cloaking_audit = audit_managers['cloaking_lib']
    
    @create_comprehensive_audit_decorator('cloaking_lib', 'test_component')
    def test_cloaking_function(pid: int, operation: str = "test") -> bool:
        """Test function với comprehensive audit."""
        time.sleep(0.1)  # Simulate work
        
        # Simulate some metrics
        cloaking_audit.audit_performance_metrics(
            "test_operation",
            {
                'execution_time': 0.1,
                'success': True,
                'pid': pid
            },
            'test_component'
        )
        
        return True
    
    # Test function execution
    result = test_cloaking_function(12345, "cloaking_test")
    print(f"Test result: {result}")
    
    # Test stealth status audit
    cloaking_audit.audit_stealth_status(
        'test_component',
        {
            'cloaked_processes': [12345, 67890],
            'threat_level': 'LOW',
            'library_available': True,
            'active_cloaking': True
        }
    )
    
    # Get audit summary
    summary = cloaking_audit.get_audit_summary()
    print(f"\\n📊 Audit Summary:")
    print(f"  Total Events: {summary['audit_session']['total_events']}")
    print(f"  Components: {summary['events_analysis']['components_analyzed']}")
    print(f"  Event Rate: {summary['events_analysis']['event_rate']:.2f}/sec")
    
    # Export comprehensive report
    export_path = cloaking_audit.export_comprehensive_audit_report()
    print(f"\\n📁 Comprehensive audit report exported to: {export_path}")
    
    # Cleanup
    cloaking_audit.cleanup_audit_session()
    
    print("\\n✅ Comprehensive audit integration test completed!")