#!/usr/bin/env python3
"""
Test script để verify DEBUG logs hoạt động sau khi cập nhật
"""

import sys
import os
sys.path.insert(0, '/app/mining_environment/scripts')

from cloak_strategies import cloak_logger as cloak_strategies_logger
from resource_control import resource_logger as resource_control_logger

def test_logger_levels():
    """Test logger levels của các module"""
    print("🔍 Testing logger levels...")
    
    # Test cloak_strategies logger
    print(f"🎭 Cloak strategies logger level: {cloak_strategies_logger.level}")
    print(f"🎭 Cloak strategies logger name: {cloak_strategies_logger.name}")
    print(f"🎭 Cloak strategies isEnabledFor DEBUG: {cloak_strategies_logger.isEnabledFor(10)}")
    
    # Test resource_control logger  
    print(f"⚙️ Resource control logger level: {resource_control_logger.level}")
    print(f"⚙️ Resource control logger name: {resource_control_logger.name}")
    print(f"⚙️ Resource control isEnabledFor DEBUG: {resource_control_logger.isEnabledFor(10)}")
    
    # Test actual logging
    print("\n📝 Testing actual DEBUG logging...")
    cloak_strategies_logger.debug("🔍 DEBUG: Test message from cloak_strategies")
    resource_control_logger.debug("🔍 DEBUG: Test message from resource_control")
    
    print("✅ Test completed - check log files for DEBUG messages")

if __name__ == "__main__":
    test_logger_levels()