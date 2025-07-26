# 🧪 Fix Verification Steps - GPU Mining Algorithm

## ✅ Thay Đổi Đã Thực Hiện

**File:** `start_mining.py:539`  
**Previous:** `'-a', 'rx/0'` (CPU algorithm)  
**Current:** `'-a', 'kawpow'` (GPU algorithm)  

---

## 🔄 Bước Kiểm Tra Trong Container

### **Step 1: Restart GPU Mining Process**
```bash
# Trong container opus-container
docker exec -it opus-container bash

# Stop current GPU process (nếu đang chạy)
pkill -f inference-cuda

# Restart mining system 
cd /app
python start_mining.py
```

### **Step 2: Monitor GPU Log**
```bash
# Theo dõi log GPU real-time
tail -f /app/mining_environment/logs/pid_gpu.log

# Expected success indicators:
# - Process moves beyond "ABOUT" messages
# - Hash rate measurements appear (e.g., "1.23 MH/s")
# - Mining statistics và accepted shares
```

### **Step 3: Verify Algorithm Configuration**
```bash
# Check process command line có algorithm kawpow
ps aux | grep inference-cuda | grep kawpow

# Expected output:
# /usr/local/bin/inference-cuda --cuda --cuda-loader=... -a kawpow
```

---

## 🎯 Success Criteria

### **✅ Immediate Indicators:**
- [ ] GPU log xuất hiện hash rate measurements (không chỉ "ABOUT")
- [ ] Process command line chứa "-a kawpow"
- [ ] Mining statistics xuất hiện trong log

### **✅ Performance Indicators:**
- [ ] `get_real_time_metrics()` trả về non-zero GPU hash rate
- [ ] GPU process không còn stuck ở initialization
- [ ] Performance report có GPU mining activity

---

## 🚨 Potential Issues và Troubleshooting

### **Issue 1: Library Dependencies**
Nếu gặp lỗi `libhwloc.so.15: cannot open shared object file`:
```bash
# Install missing libraries trong container
apt-get update && apt-get install -y libhwloc15
```

### **Issue 2: CUDA Loader Path**
Nếu gặp lỗi CUDA loader:
```bash
# Verify CUDA loader exists
ls -la /usr/lib/x86_64-linux-gnu/libcuda.so
```

### **Issue 3: Mining Pool Connection**
Nếu algorithm đúng nhưng không connect được pool:
```bash
# Check environment variables
echo $MINING_SERVER_GPU
echo $MINING_WALLET_GPU
```

---

## 📊 Expected Log Output After Fix

### **Before Fix (Stuck):**
```
[timestamp] [PID: 635] * ABOUT inference-cuda/1.0.0 gcc/11.4.0
[timestamp] [PID: 635] * ABOUT inference-cuda/1.0.0 gcc/11.4.0
[timestamp] [PID: 635] * ABOUT inference-cuda/1.0.0 gcc/11.4.0
```

### **After Fix (Working):**
```
[timestamp] [PID: 636] * ABOUT inference-cuda/1.0.0 gcc/11.4.0
[timestamp] [PID: 636] Mining KawPoW at pool-address:port
[timestamp] [PID: 636] Current hashrate: 2.34 MH/s
[timestamp] [PID: 636] Accepted share (difficulty: 1024)
```

---

## 🔍 Manual Verification Commands

### **Test Algorithm Support:**
```bash
# Test kawpow algorithm (should work)
/usr/local/bin/inference-cuda --help | grep -i algorithm

# Test mining command format
/usr/local/bin/inference-cuda --cuda -a kawpow --help
```

### **Monitor Process Behavior:**
```bash
# Monitor CPU và memory usage của GPU process
top -p $(pgrep inference-cuda)

# Check GPU utilization (nếu có nvidia-smi)
nvidia-smi -l 5
```

---

**Kết luận:** Fix đã được thực hiện thành công. Cần restart mining process để apply algorithm change và verify hoạt động thông qua log monitoring.