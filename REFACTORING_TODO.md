# VIETNAMESE REFACTORING TODO - Danh sách công việc tái cấu trúc tiếng Việt

## 📋 PHASE 1: CRITICAL INFRASTRUCTURE FILES (Tệp hạ tầng quan trọng)

### 🎯 **ACTIVE TASK**: start_mining.py
- [ ] Line 569: "Wait for stealth wrapper to spawn child process"
- [ ] Line 572: "Find actual mining process by command name"  
- [ ] Line 589: "Register real mining process for Enhanced PID Logger"
- [ ] Line 1022: "Force restart worker"
- [ ] Line 1080: "Fallback to fake process if access denied"
- [ ] Additional pure English comments (~45 more)

### ⏳ **PENDING**: privileged_operations.py
- [ ] Line 211: "Set CPU limit" 
- [ ] Line 216: "Set memory limit"
- [ ] Line 221: "Add process to cgroup"
- [ ] Line 306: "Test script"

### ⏳ **PENDING**: stealth_monitor.py  
- [ ] Line 25: "Add project root to path"
- [ ] Line 42: "Stealth name patterns"
- [ ] Line 129: "Count CPU warnings"
- [ ] Additional monitoring comments

## 📋 PHASE 2: CORE PROCESSING FILES (Tệp xử lý cốt lõi)

### ⏳ **PENDING**: optimized_calculation_chain.py
- [ ] Multiple calculation and optimization comments
- [ ] Technical algorithm comments
- [ ] Performance logging comments

### ⏳ **PENDING**: audit_integration.py  
- [ ] English docstrings for audit functions
- [ ] System logging setup comments

### ⏳ **PENDING**: mining_output_bridge.py
- [ ] Bridge setup and forwarding docstrings
- [ ] Output processing comments

## 📋 PHASE 3: SUPPORTING MODULES (Module hỗ trợ)

### ⏳ **PENDING**: setup_env.py
- [ ] Helper function comments
- [ ] Environment validation comments

### ⏳ **PENDING**: logging_config.py
- [ ] Format and args comments
- [ ] Configuration setup comments

### ⏳ **PENDING**: eventbus_config.py
- [ ] Backend selection comments
- [ ] Configuration setup comments

## 📊 PROGRESS TRACKING (Theo dõi tiến độ)

### **Current Status**:
- **Files Completed**: 0/9
- **Total Changes Made**: 0/140 (estimated)
- **Current Phase**: 1 (Critical Infrastructure)
- **Active File**: start_mining.py

### **Quality Metrics**:
- **Format Compliance**: **[English Term]** (Vietnamese description – function/purpose)  
- **Consistency Check**: ✅ Existing translations maintained
- **Technical Accuracy**: ✅ Preserve all technical meaning
- **Professional Tone**: ✅ Business Vietnamese terminology

---

**NEXT ACTIONS**: 
1. Complete start_mining.py refactoring
2. Verify changes don't affect functionality  
3. Move to privileged_operations.py
4. Continue systematic phase-by-phase approach