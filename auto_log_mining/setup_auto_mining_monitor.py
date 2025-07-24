#!/usr/bin/env python3
"""
🚀 Setup Auto Mining Monitor - Comprehensive Solution
Script thiết lập toàn diện hệ thống tự động giám sát mining output

TÍNH NĂNG:
✅ Tích hợp vào start_mining.py (tự động kích hoạt)
✅ Standalone service mode
✅ Systemd service integration  
✅ Docker container support
✅ Manual activation options
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

class AutoMiningMonitorSetup:
    """**Auto Mining Monitor Setup** (thiết lập giám sát khai thác tự động)"""
    
    def __init__(self):
        self.app_dir = Path.cwd()
        self.service_file = self.app_dir / "mining-monitor.service"
        
    def print_header(self, title):
        """**Print section header** (in tiêu đề phần)"""
        print(f"\n{'='*60}")
        print(f"🔧 {title}")
        print('='*60)
    
    def print_option(self, num, title, description):
        """**Print setup option** (in tùy chọn thiết lập)"""
        print(f"\n{num}️⃣ **{title}**")
        print(f"   {description}")
    
    def check_prerequisites(self):
        """**Check prerequisites** (kiểm tra điều kiện tiên quyết)"""
        self.print_header("KIỂM TRA ĐIỀU KIỆN TIÊN QUYẾT")
        
        required_files = [
            'start_mining.py',
            'continuous_mining_monitor.py',
            'auto_mining_monitor.py',
            'mining_environment/scripts/auto_monitor_integration.py'
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.app_dir / file_path).exists():
                missing_files.append(file_path)
            else:
                print(f"✅ {file_path}")
        
        if missing_files:
            print(f"\n❌ Missing files:")
            for file_path in missing_files:
                print(f"   - {file_path}")
            return False
        
        print(f"\n✅ All required files present")
        return True
    
    def setup_option_1_integration(self):
        """**Option 1: Integration with start_mining.py** (tích hợp với start_mining.py)"""
        self.print_header("TÍCH HỢP VỚI start_mining.py")
        
        try:
            # Import and apply patch
            sys.path.append(str(self.app_dir))
            from start_mining_monitor_patch import apply_patch
            
            success = apply_patch()
            if success:
                print("\n🎯 INTEGRATION COMPLETED!")
                print("💡 Auto monitor sẽ kích hoạt 45 giây sau khi start_mining.py chạy")
                print("📋 Usage: python3 start_mining.py")
                return True
            else:
                print("\n❌ Integration failed")
                return False
                
        except Exception as e:
            print(f"❌ Integration error: {e}")
            return False
    
    def setup_option_2_standalone(self):
        """**Option 2: Standalone Service** (dịch vụ độc lập)"""
        self.print_header("STANDALONE SERVICE SETUP")
        
        print("📋 Standalone Usage Commands:")
        print("   🚀 Start: python3 auto_mining_monitor.py")
        print("   🛑 Stop:  Ctrl+C")
        print("   🔍 Logs:  Check mining_environment/logs/")
        
        print(f"\n✅ Standalone service ready!")
        print("💡 Chạy sau khi start_mining.py đã khởi động")
        return True
    
    def setup_option_3_systemd(self):
        """**Option 3: Systemd Service** (dịch vụ systemd)"""
        self.print_header("SYSTEMD SERVICE SETUP")
        
        try:
            # Check if running as root for systemd
            if os.geteuid() != 0:
                print("⚠️ Systemd setup requires root privileges")
                print("💡 Run: sudo python3 setup_auto_mining_monitor.py")
                return False
            
            # Copy service file
            service_dest = Path("/etc/systemd/system/mining-monitor.service")
            shutil.copy2(self.service_file, service_dest)
            print(f"✅ Service file copied to {service_dest}")
            
            # Reload systemd
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            print("✅ Systemd daemon reloaded")
            
            # Enable service
            subprocess.run(["systemctl", "enable", "mining-monitor.service"], check=True)
            print("✅ Service enabled for auto-start")
            
            print("\n📋 Systemd Service Commands:")
            print("   🚀 Start:   sudo systemctl start mining-monitor")
            print("   🛑 Stop:    sudo systemctl stop mining-monitor")
            print("   📊 Status:  sudo systemctl status mining-monitor")
            print("   📋 Logs:    sudo journalctl -u mining-monitor -f")
            print("   🔄 Restart: sudo systemctl restart mining-monitor")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Systemd setup failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Systemd setup error: {e}")
            return False
    
    def setup_option_4_docker(self):
        """**Option 4: Docker Integration** (tích hợp Docker)"""
        self.print_header("DOCKER INTEGRATION SETUP")
        
        print("📋 Docker Integration Options:")
        print("\n🔹 **Method 1: Run inside existing container**")
        print("   sudo docker exec opus-container python3 /app/auto_mining_monitor.py")
        
        print("\n🔹 **Method 2: Modify container startup**")
        print("   Add to Dockerfile:")
        print("   CMD [\"sh\", \"-c\", \"python3 start_mining.py & sleep 60 && python3 auto_mining_monitor.py\"]")
        
        print("\n🔹 **Method 3: Docker Compose service**")
        print("   Create separate monitoring service container")
        
        print(f"\n✅ Docker integration instructions provided!")
        return True
    
    def show_setup_menu(self):
        """**Show setup menu** (hiển thị menu thiết lập)"""
        self.print_header("AUTO MINING MONITOR SETUP - MENU")
        
        self.print_option(1, "Tích hợp với start_mining.py", 
                         "Tự động kích hoạt monitor khi start_mining.py chạy (KHUYẾN NGHỊ)")
        
        self.print_option(2, "Standalone Service",
                         "Chạy monitor như service độc lập")
        
        self.print_option(3, "Systemd Service", 
                         "Cài đặt như system service (auto-start)")
        
        self.print_option(4, "Docker Integration",
                         "Hướng dẫn tích hợp với Docker container")
        
        print(f"\n0️⃣ **Exit** - Thoát setup")
    
    def run_interactive_setup(self):
        """**Run interactive setup** (chạy thiết lập tương tác)"""
        if not self.check_prerequisites():
            print("\n❌ Setup cannot continue - missing required files")
            return False
        
        while True:
            self.show_setup_menu()
            
            try:
                choice = input(f"\n🔧 Chọn option (1-4, 0 để thoát): ").strip()
                
                if choice == '0':
                    print(f"\n👋 Setup ended. See you later!")
                    break
                elif choice == '1':
                    self.setup_option_1_integration()
                elif choice == '2':
                    self.setup_option_2_standalone()
                elif choice == '3':
                    self.setup_option_3_systemd()
                elif choice == '4':
                    self.setup_option_4_docker()
                else:
                    print(f"\n❌ Invalid choice: {choice}")
                    continue
                
                input(f"\n⏸️ Press Enter to continue...")
                
            except KeyboardInterrupt:
                print(f"\n\n👋 Setup interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Setup error: {e}")
                input(f"\n⏸️ Press Enter to continue...")

def main():
    """**Main setup function** (hàm thiết lập chính)"""
    print("🚀 AUTO MINING MONITOR SETUP")
    print("Comprehensive solution for automatic mining output monitoring")
    
    setup = AutoMiningMonitorSetup()
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        option = sys.argv[1]
        if option == '--integrate':
            setup.setup_option_1_integration()
        elif option == '--standalone':
            setup.setup_option_2_standalone()
        elif option == '--systemd':
            setup.setup_option_3_systemd()
        elif option == '--docker':
            setup.setup_option_4_docker()
        else:
            print(f"❌ Unknown option: {option}")
            print("💡 Available options: --integrate, --standalone, --systemd, --docker")
    else:
        # Run interactive setup
        setup.run_interactive_setup()

if __name__ == "__main__":
    main()