#!/usr/bin/env python3
"""
🔧 Start Mining Monitor Integration Patch
Patch để tích hợp auto mining monitor vào start_mining.py

HƯỚNG DẪN SỬ DỤNG:
1. Thêm import statement vào đầu start_mining.py
2. Thêm activation call vào cuối main() function
"""

# ========================================
# 1️⃣ THÊM VÀO PHẦN IMPORT của start_mining.py
# ========================================

IMPORT_PATCH = '''
# 🔄 **Auto Mining Monitor Integration** (tích hợp giám sát khai thác tự động)
from mining_environment.scripts.auto_monitor_integration import auto_activate_mining_monitor
'''

# ========================================  
# 2️⃣ THÊM VÀO CUỐI main() FUNCTION
# ========================================

MAIN_FUNCTION_PATCH = '''
    # ------------------------------------------------------------------
    # 🔄 AUTO MINING MONITOR ACTIVATION (Kích hoạt giám sát tự động)
    # ------------------------------------------------------------------
    try:
        logger.info("🔄 Activating auto mining monitor...")
        monitor_integration = auto_activate_mining_monitor(logger, delay=45)
        logger.info("✅ Auto mining monitor integration completed")
        
        # Register cleanup on exit
        import atexit
        def cleanup_monitor():
            try:
                monitor_integration.stop_monitoring()
                logger.info("🔚 Mining monitor cleanup completed")
            except:
                pass
        atexit.register(cleanup_monitor)
        
    except Exception as e:
        logger.warning(f"⚠️ Auto mining monitor activation failed: {e}")
        logger.info("💡 Mining will continue without automatic output monitoring")
'''

def show_integration_instructions():
    """**Show Integration Instructions** (hiển thị hướng dẫn tích hợp)"""
    print("🔧 START MINING MONITOR INTEGRATION PATCH")
    print("=" * 60)
    
    print("\n1️⃣ THÊM IMPORT VÀO ĐẦU start_mining.py:")
    print("-" * 40)
    print(IMPORT_PATCH)
    
    print("\n2️⃣ THÊM VÀO CUỐI main() FUNCTION:")
    print("-" * 40) 
    print(MAIN_FUNCTION_PATCH)
    
    print("\n📋 HOẶC SỬ DỤNG AUTO-PATCH:")
    print("-" * 40)
    print("python3 start_mining_monitor_patch.py --apply")

def apply_patch():
    """**Apply patch automatically** (áp dụng patch tự động)"""
    import re
    
    try:
        # Read start_mining.py
        with open('start_mining.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if already patched
        if 'auto_activate_mining_monitor' in content:
            print("✅ start_mining.py already has monitor integration")
            return True
        
        # Add import after existing imports
        import_pattern = r'(from\s+mining_environment\.scripts\.auxiliary_modules\.event_bus\s+import\s+EventBus\s*\n)'
        if re.search(import_pattern, content):
            content = re.sub(
                import_pattern,
                r'\1' + IMPORT_PATCH + '\n',
                content
            )
            print("✅ Added import statement")
        else:
            print("⚠️ Could not find import insertion point")
            return False
        
        # Add activation code before final logger.info in main()
        main_pattern = r'(\s+logger\.info\("🚀 MULTI-THREADING ARCHITECTURE STARTUP COMPLETED"\))'
        if re.search(main_pattern, content):
            content = re.sub(
                main_pattern,
                MAIN_FUNCTION_PATCH + r'\1',
                content
            )
            print("✅ Added monitor activation code")
        else:
            print("⚠️ Could not find main() function insertion point")
            return False
        
        # Write patched file
        with open('start_mining.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("🎯 start_mining.py successfully patched!")
        print("💡 Auto mining monitor will activate 45 seconds after startup")
        return True
        
    except Exception as e:
        print(f"❌ Patch failed: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        apply_patch()
    else:
        show_integration_instructions()