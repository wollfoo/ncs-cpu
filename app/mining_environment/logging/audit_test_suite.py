"""
audit_test_suite.py

Comprehensive Test Suite cho CPU Optimization & Cloaking Audit System.
Tests activation scenarios, performance impact, logging functionality, và integration.

Author: Claude AI Audit Framework
Purpose: Comprehensive testing của audit logging system
"""

import os
import sys
import time
import threading
import logging
import json
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import unittest
from unittest.mock import Mock, patch, MagicMock

# Import audit components
from .optimization_logger import OptimizationLogger, get_optimization_logger, optimization_logger
from .debug_support import DebugSupportSystem, get_debug_system, debug_decorator
from .audit_integration import AuditIntegrationManager, get_audit_manager, create_comprehensive_audit_decorator


class AuditTestSuite:
    """
    Comprehensive Test Suite cho audit system.
    Tests logging functionality, performance impact, integration, và activation scenarios.
    """
    
    def __init__(self, test_name: str = "audit_test"):
        """
        Initialize AuditTestSuite.
        
        Args:
            test_name: Name của test suite
        """
        self.test_name = test_name
        self.test_start_time = time.time()
        self.test_results: List[Dict[str, Any]] = []
        self.temp_dir = tempfile.mkdtemp(prefix=f"audit_test_{test_name}_")
        
        # Setup test logging
        self.test_logger = self._setup_test_logger()
        
        # Test metrics
        self.performance_metrics = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'total_execution_time': 0,
            'average_test_time': 0
        }
        
        self.test_logger.info(f"🧪 Audit Test Suite initialized: {test_name}")
        self.test_logger.info(f"📁 Test temp directory: {self.temp_dir}")
    
    def _setup_test_logger(self) -> logging.Logger:
        """Setup test logger."""
        logger = logging.getLogger(f"audit_test.{self.test_name}")
        logger.setLevel(logging.DEBUG)
        
        # Test log handler
        test_handler = logging.FileHandler(
            os.path.join(self.temp_dir, f"{self.test_name}_test.log"),
            mode='w',
            encoding='utf-8'
        )
        test_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s [TEST] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        test_handler.setFormatter(formatter)
        logger.addHandler(test_handler)
        
        return logger
    
    def run_test(self, test_name: str, test_func: callable, *args, **kwargs) -> Dict[str, Any]:
        """
        Run individual test với comprehensive logging.
        
        Args:
            test_name: Test name
            test_func: Test function
            *args: Test function arguments
            **kwargs: Test function keyword arguments
            
        Returns:
            Test result dictionary
        """
        test_start = time.time()
        self.test_logger.info(f"🔬 Starting test: {test_name}")
        
        test_result = {
            'test_name': test_name,
            'start_time': test_start,
            'end_time': None,
            'execution_time': None,
            'status': 'RUNNING',
            'error': None,
            'details': {},
            'performance_impact': {}
        }
        
        try:
            # Run test function
            result = test_func(*args, **kwargs)
            
            # Test passed
            test_result['status'] = 'PASSED'
            test_result['details'] = result if isinstance(result, dict) else {'result': result}
            
            self.performance_metrics['passed_tests'] += 1
            self.test_logger.info(f"✅ Test passed: {test_name}")
            
        except Exception as e:
            # Test failed
            test_result['status'] = 'FAILED'
            test_result['error'] = {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': self._get_traceback()
            }
            
            self.performance_metrics['failed_tests'] += 1
            self.test_logger.error(f"❌ Test failed: {test_name} - {str(e)}")
            
        finally:
            # Update test metrics
            test_end = time.time()
            execution_time = test_end - test_start
            
            test_result['end_time'] = test_end
            test_result['execution_time'] = execution_time
            
            self.performance_metrics['total_tests'] += 1
            self.performance_metrics['total_execution_time'] += execution_time
            
            # Store test result
            self.test_results.append(test_result)
            
            self.test_logger.info(f"⏱️ Test completed: {test_name} ({execution_time:.3f}s)")
        
        return test_result
    
    def _get_traceback(self) -> str:
        """Get current traceback as string."""
        import traceback
        return traceback.format_exc()
    
    def test_optimization_logger_functionality(self) -> Dict[str, Any]:
        """Test OptimizationLogger functionality."""
        self.test_logger.info("🔬 Testing OptimizationLogger functionality...")
        
        # Create test logger
        test_logger = OptimizationLogger("test_optimization", self.temp_dir)
        
        results = {
            'logger_created': True,
            'function_logging': False,
            'performance_logging': False,
            'error_logging': False,
            'cpu_metrics': False,
            'stealth_logging': False,
            'metrics_export': False
        }
        
        # Test function logging
        test_logger.log_function_entry("test_function", (1, 2), {"param": "value"})
        test_logger.log_function_exit("test_function", "result", True)
        results['function_logging'] = True
        
        # Test performance logging
        test_logger.log_performance_metrics("test_operation", {
            'execution_time': 0.1,
            'success': True,
            'memory_usage': 1024
        })
        results['performance_logging'] = True
        
        # Test error logging
        test_error = Exception("Test error")
        test_logger.log_error_with_context("test_function", test_error, {"context": "test"})
        results['error_logging'] = True
        
        # Test CPU metrics (mock)
        with patch('psutil.Process') as mock_process:
            mock_proc = Mock()
            mock_proc.cpu_percent.return_value = 50.0
            mock_proc.memory_info.return_value = Mock(rss=1024*1024*100)  # 100MB
            mock_proc.memory_percent.return_value = 5.0
            mock_proc.cpu_affinity.return_value = [0, 1]
            mock_proc.num_threads.return_value = 4
            mock_process.return_value = mock_proc
            
            test_logger.log_cpu_metrics(12345, "test_operation")
            results['cpu_metrics'] = True
        
        # Test stealth logging
        test_logger.log_stealth_status("test_component", {
            'cloaked_processes': [12345, 67890],
            'threat_level': 'LOW',
            'library_available': True
        })
        results['stealth_logging'] = True
        
        # Test metrics export
        export_path = os.path.join(self.temp_dir, "test_metrics.json")
        test_logger.export_metrics(export_path)
        results['metrics_export'] = os.path.exists(export_path)
        
        # Verify log files created
        debug_log = Path(self.temp_dir) / "test_optimization_debug.log"
        ops_log = Path(self.temp_dir) / "test_optimization_operations.log"
        
        results['log_files_created'] = debug_log.exists() and ops_log.exists()
        
        return results
    
    def test_debug_support_functionality(self) -> Dict[str, Any]:
        """Test DebugSupportSystem functionality."""
        self.test_logger.info("🔬 Testing DebugSupportSystem functionality...")
        
        # Create test debug system
        debug_system = DebugSupportSystem("test_debug", "DEBUG")
        
        results = {
            'debug_system_created': True,
            'function_debugging': False,
            'error_debugging': False,
            'performance_debugging': False,
            'thread_tracking': False,
            'stack_trace_collection': False,
            'profiling': False,
            'report_generation': False
        }
        
        # Test function debugging
        debug_system.debug_function_call("test_function", (1, 2), {"param": "value"})
        debug_system.debug_function_exit("test_function", "result", 0.1)
        results['function_debugging'] = True
        
        # Test error debugging
        test_error = Exception("Test debug error")
        debug_system.debug_error("test_function", test_error, {"context": "test"})
        results['error_debugging'] = True
        
        # Test performance debugging
        debug_system.debug_performance_metric("test_operation", {
            'execution_time': 0.1,
            'memory_usage': 1024
        })
        results['performance_debugging'] = True
        
        # Test thread tracking
        debug_system.thread_tracker.register_thread("test_thread")
        debug_system.thread_tracker.update_thread_activity()
        thread_report = debug_system.thread_tracker.get_thread_report()
        results['thread_tracking'] = thread_report['total_threads'] > 0
        
        # Test stack trace collection
        debug_system.stack_collector.collect_stack_trace("test_context")
        stack_report = debug_system.stack_collector.get_stack_trace_report()
        results['stack_trace_collection'] = stack_report['total_traces'] > 0
        
        # Test profiling
        with debug_system.profiler.profile_operation("test_operation"):
            time.sleep(0.01)  # Simulate work
        results['profiling'] = len(debug_system.profiler.profiles) > 0
        
        # Test report generation
        report = debug_system.get_comprehensive_debug_report()
        results['report_generation'] = 'debug_system' in report
        
        return results
    
    def test_audit_integration_functionality(self) -> Dict[str, Any]:
        """Test AuditIntegrationManager functionality."""
        self.test_logger.info("🔬 Testing AuditIntegrationManager functionality...")
        
        # Create test audit manager
        audit_manager = AuditIntegrationManager("test_audit", "DEBUG")
        
        results = {
            'audit_manager_created': True,
            'decorator_creation': False,
            'activation_audit': False,
            'performance_audit': False,
            'stealth_audit': False,
            'cpu_audit': False,
            'comprehensive_report': False
        }
        
        # Test decorator creation
        audit_decorator = audit_manager.create_audit_decorator("test_component")
        results['decorator_creation'] = audit_decorator is not None
        
        # Test activation audit
        audit_manager.audit_activation_status("test_component", "ENABLED", {
            'details': 'test activation'
        })
        results['activation_audit'] = True
        
        # Test performance audit
        audit_manager.audit_performance_metrics("test_operation", {
            'execution_time': 0.1,
            'success': True
        }, "test_component")
        results['performance_audit'] = True
        
        # Test stealth audit
        audit_manager.audit_stealth_status("test_component", {
            'cloaked_processes': [12345],
            'threat_level': 'LOW'
        })
        results['stealth_audit'] = True
        
        # Test CPU audit (mock)
        with patch('psutil.Process') as mock_process:
            mock_proc = Mock()
            mock_proc.cpu_percent.return_value = 50.0
            mock_proc.memory_info.return_value = Mock(rss=1024*1024*100)
            mock_proc.memory_percent.return_value = 5.0
            mock_proc.cpu_affinity.return_value = [0, 1]
            mock_proc.status.return_value = 'running'
            mock_proc.create_time.return_value = time.time()
            mock_process.return_value = mock_proc
            
            audit_manager.audit_cpu_metrics(12345, "test_operation", "test_component")
            results['cpu_audit'] = True
        
        # Test comprehensive report
        summary = audit_manager.get_audit_summary()
        results['comprehensive_report'] = 'audit_session' in summary
        
        return results
    
    def test_decorator_integration(self) -> Dict[str, Any]:
        """Test decorator integration và functionality."""
        self.test_logger.info("🔬 Testing decorator integration...")
        
        results = {
            'optimization_decorator': False,
            'debug_decorator': False,
            'comprehensive_decorator': False,
            'error_handling': False,
            'performance_tracking': False
        }
        
        # Test optimization decorator
        test_opt_logger = get_optimization_logger("test_decorator")
        
        @optimization_logger("test_decorator")
        def test_opt_function(x: int, y: int = 10) -> int:
            return x * y
        
        result = test_opt_function(5, y=20)
        results['optimization_decorator'] = result == 100
        
        # Test debug decorator
        test_debug_system = get_debug_system("test_decorator", "DEBUG")
        
        @debug_decorator(test_debug_system)
        def test_debug_function(x: int) -> int:
            if x < 0:
                raise ValueError("x must be positive")
            return x * 2
        
        result = test_debug_function(5)
        results['debug_decorator'] = result == 10
        
        # Test comprehensive decorator
        @create_comprehensive_audit_decorator("test_decorator", "test_component")
        def test_comprehensive_function(x: int, operation: str = "test") -> Dict[str, Any]:
            time.sleep(0.01)  # Simulate work
            return {'result': x * 2, 'operation': operation}
        
        result = test_comprehensive_function(5, operation="multiply")
        results['comprehensive_decorator'] = result['result'] == 10
        
        # Test error handling
        try:
            test_debug_function(-1)
            results['error_handling'] = False
        except ValueError:
            results['error_handling'] = True
        
        # Test performance tracking
        performance_summary = test_opt_logger.get_performance_summary()
        results['performance_tracking'] = performance_summary['total_operations'] > 0
        
        return results
    
    def test_activation_scenarios(self) -> Dict[str, Any]:
        """Test different activation scenarios."""
        self.test_logger.info("🔬 Testing activation scenarios...")
        
        results = {
            'stealth_mode_enabled': False,
            'stealth_mode_disabled': False,
            'library_available': False,
            'library_unavailable': False,
            'threat_level_low': False,
            'threat_level_high': False
        }
        
        # Test stealth mode enabled scenario
        with patch.dict(os.environ, {'ENABLE_STEALTH_MODE': '1'}):
            stealth_enabled = os.getenv('ENABLE_STEALTH_MODE', '0') == '1'
            results['stealth_mode_enabled'] = stealth_enabled
        
        # Test stealth mode disabled scenario
        with patch.dict(os.environ, {'ENABLE_STEALTH_MODE': '0'}):
            stealth_disabled = os.getenv('ENABLE_STEALTH_MODE', '1') == '0'
            results['stealth_mode_disabled'] = stealth_disabled
        
        # Test library availability scenarios
        with patch('os.path.exists') as mock_exists:
            # Library available
            mock_exists.return_value = True
            results['library_available'] = True
            
            # Library unavailable
            mock_exists.return_value = False
            results['library_unavailable'] = True
        
        # Test threat level scenarios
        test_audit = get_audit_manager("test_activation")
        
        # Low threat level
        test_audit.audit_stealth_status("test_component", {
            'threat_level': 'LOW',
            'cloaked_processes': [12345]
        })
        results['threat_level_low'] = True
        
        # High threat level
        test_audit.audit_stealth_status("test_component", {
            'threat_level': 'HIGH',
            'cloaked_processes': [12345, 67890]
        })
        results['threat_level_high'] = True
        
        return results
    
    def test_performance_impact(self) -> Dict[str, Any]:
        """Test performance impact của audit system."""
        self.test_logger.info("🔬 Testing performance impact...")
        
        results = {
            'baseline_performance': 0,
            'with_optimization_logging': 0,
            'with_debug_support': 0,
            'with_comprehensive_audit': 0,
            'performance_overhead': {},
            'memory_impact': {}
        }
        
        # Baseline performance test
        def baseline_function(iterations: int = 1000) -> int:
            total = 0
            for i in range(iterations):
                total += i * 2
            return total
        
        # Test baseline
        start_time = time.time()
        baseline_result = baseline_function()
        baseline_time = time.time() - start_time
        results['baseline_performance'] = baseline_time
        
        # Test with optimization logging
        @optimization_logger("performance_test")
        def logged_function(iterations: int = 1000) -> int:
            total = 0
            for i in range(iterations):
                total += i * 2
            return total
        
        start_time = time.time()
        logged_result = logged_function()
        logged_time = time.time() - start_time
        results['with_optimization_logging'] = logged_time
        
        # Test with debug support
        debug_system = get_debug_system("performance_test", "INFO")
        
        @debug_decorator(debug_system)
        def debug_function(iterations: int = 1000) -> int:
            total = 0
            for i in range(iterations):
                total += i * 2
            return total
        
        start_time = time.time()
        debug_result = debug_function()
        debug_time = time.time() - start_time
        results['with_debug_support'] = debug_time
        
        # Test with comprehensive audit
        @create_comprehensive_audit_decorator("performance_test", "test_component")
        def audit_function(iterations: int = 1000) -> int:
            total = 0
            for i in range(iterations):
                total += i * 2
            return total
        
        start_time = time.time()
        audit_result = audit_function()
        audit_time = time.time() - start_time
        results['with_comprehensive_audit'] = audit_time
        
        # Calculate overhead
        results['performance_overhead'] = {
            'optimization_logging': ((logged_time - baseline_time) / baseline_time) * 100,
            'debug_support': ((debug_time - baseline_time) / baseline_time) * 100,
            'comprehensive_audit': ((audit_time - baseline_time) / baseline_time) * 100
        }
        
        # Memory impact test
        import psutil
        process = psutil.Process()
        
        results['memory_impact'] = {
            'baseline_memory': process.memory_info().rss // 1024 // 1024,  # MB
            'audit_active_memory': process.memory_info().rss // 1024 // 1024  # MB
        }
        
        return results
    
    def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """Run complete test suite."""
        self.test_logger.info("🧪 Running comprehensive audit test suite...")
        
        # Run all tests
        test_functions = [
            ("optimization_logger", self.test_optimization_logger_functionality),
            ("debug_support", self.test_debug_support_functionality),
            ("audit_integration", self.test_audit_integration_functionality),
            ("decorator_integration", self.test_decorator_integration),
            ("activation_scenarios", self.test_activation_scenarios),
            ("performance_impact", self.test_performance_impact)
        ]
        
        for test_name, test_func in test_functions:
            self.run_test(test_name, test_func)
        
        # Calculate final metrics
        total_time = time.time() - self.test_start_time
        self.performance_metrics['total_execution_time'] = total_time
        
        if self.performance_metrics['total_tests'] > 0:
            self.performance_metrics['average_test_time'] = (
                self.performance_metrics['total_execution_time'] / 
                self.performance_metrics['total_tests']
            )
        
        # Generate comprehensive report
        test_report = {
            'test_suite_name': self.test_name,
            'execution_summary': self.performance_metrics,
            'test_results': self.test_results,
            'temp_directory': self.temp_dir,
            'start_time': self.test_start_time,
            'end_time': time.time(),
            'total_duration': total_time
        }
        
        # Export test report
        report_path = os.path.join(self.temp_dir, f"{self.test_name}_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(test_report, f, indent=2, ensure_ascii=False)
        
        self.test_logger.info(f"✅ Test suite completed: {self.performance_metrics['passed_tests']}/{self.performance_metrics['total_tests']} passed")
        self.test_logger.info(f"📁 Test report saved to: {report_path}")
        
        return test_report
    
    def cleanup(self):
        """Cleanup test resources."""
        try:
            # Keep test results for analysis
            self.test_logger.info(f"🧹 Test temp directory preserved: {self.temp_dir}")
            self.test_logger.info("ℹ️ To cleanup manually: shutil.rmtree(temp_dir)")
        except Exception as e:
            self.test_logger.error(f"❌ Error during cleanup: {e}")
    
    def print_test_summary(self):
        """Print test summary to console."""
        print(f"\\n🧪 AUDIT TEST SUITE SUMMARY - {self.test_name}")
        print("="*60)
        print(f"Total Tests: {self.performance_metrics['total_tests']}")
        print(f"Passed: {self.performance_metrics['passed_tests']} ✅")
        print(f"Failed: {self.performance_metrics['failed_tests']} ❌")
        print(f"Skipped: {self.performance_metrics['skipped_tests']} ⏭️")
        print(f"Total Time: {self.performance_metrics['total_execution_time']:.2f}s")
        print(f"Average Test Time: {self.performance_metrics['average_test_time']:.3f}s")
        print(f"Success Rate: {(self.performance_metrics['passed_tests'] / self.performance_metrics['total_tests'] * 100):.1f}%")
        print(f"\\n📁 Test Directory: {self.temp_dir}")
        
        # Print failed tests
        failed_tests = [r for r in self.test_results if r['status'] == 'FAILED']
        if failed_tests:
            print(f"\\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test_name']}: {test['error']['message']}")
        
        print("="*60)


def run_audit_verification_suite():
    """Run comprehensive audit verification suite."""
    print("🧪 Starting Comprehensive Audit Verification Suite...")
    
    # Create test suite
    test_suite = AuditTestSuite("comprehensive_audit_verification")
    
    try:
        # Run comprehensive tests
        test_report = test_suite.run_comprehensive_test_suite()
        
        # Print summary
        test_suite.print_test_summary()
        
        # Analyze performance impact
        performance_tests = [r for r in test_suite.test_results if r['test_name'] == 'performance_impact']
        if performance_tests:
            perf_data = performance_tests[0]['details']
            print(f"\\n📊 PERFORMANCE IMPACT ANALYSIS:")
            print(f"Baseline: {perf_data['baseline_performance']:.6f}s")
            print(f"With Optimization Logging: {perf_data['performance_overhead']['optimization_logging']:.1f}% overhead")
            print(f"With Debug Support: {perf_data['performance_overhead']['debug_support']:.1f}% overhead")
            print(f"With Comprehensive Audit: {perf_data['performance_overhead']['comprehensive_audit']:.1f}% overhead")
        
        return test_report
        
    finally:
        # Cleanup
        test_suite.cleanup()


if __name__ == "__main__":
    # Run verification suite
    report = run_audit_verification_suite()
    
    print(f"\\n✅ Audit verification suite completed!")
    print(f"📊 Results: {report['execution_summary']['passed_tests']}/{report['execution_summary']['total_tests']} tests passed")
    
    # Check if all tests passed
    if report['execution_summary']['failed_tests'] == 0:
        print("🎉 ALL TESTS PASSED! Audit system is ready for production use.")
    else:
        print(f"⚠️ {report['execution_summary']['failed_tests']} tests failed. Review test results before deployment.")