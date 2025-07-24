#!/bin/bash

echo "🔍 ===== GPU MINING DEBUG REPORT ====="
echo "📅 Timestamp: $(date)"
echo "🖥️  Hostname: $(hostname)"
echo ""

echo "1️⃣ NVIDIA Driver Status:"
if nvidia-smi >/dev/null 2>&1; then
    echo "✅ nvidia-smi: OK"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits
else
    echo "❌ nvidia-smi: FAILED"
fi
echo ""

echo "2️⃣ CUDA Environment:"
if command -v nvcc >/dev/null 2>&1; then
    echo "✅ CUDA Compiler: $(nvcc --version | grep 'release' | cut -d',' -f2)"
else
    echo "❌ nvcc: NOT FOUND"
fi

if ls /usr/local/cuda*/lib64/libcudart.so* >/dev/null 2>&1; then
    echo "✅ CUDA Runtime: $(ls /usr/local/cuda*/lib64/libcudart.so* | head -1)"
else
    echo "❌ CUDA Runtime: NOT FOUND"
fi
echo ""

echo "3️⃣ OpenCL Support:"
if command -v clinfo >/dev/null 2>&1; then
    echo "✅ OpenCL: OK"
    clinfo -l 2>/dev/null | head -5 || echo "   No OpenCL platforms detected"
else
    echo "❌ clinfo: NOT FOUND"
fi
echo ""

echo "4️⃣ Mining Executables:"
for exe in ml-inference inference-cuda; do
    if [ -x "/usr/local/bin/$exe" ]; then
        echo "✅ $exe: $(stat -c%s /usr/local/bin/$exe) bytes"
        ldd "/usr/local/bin/$exe" | grep -E "(cuda|nvidia)" | head -3 || echo "   No CUDA/NVIDIA libs linked"
    else
        echo "❌ $exe: NOT FOUND or NOT EXECUTABLE"
    fi
done
echo ""

echo "5️⃣ Environment Variables:"
env | grep -E "(CUDA|ML|MINING|NVIDIA)" | sort | while read var; do
    echo "   $var"
done
echo ""

echo "6️⃣ Device Files:"
if ls /dev/nvidia* >/dev/null 2>&1; then
    echo "✅ NVIDIA devices:"
    ls -la /dev/nvidia* | while read line; do echo "   $line"; done
else
    echo "❌ No NVIDIA device files found"
fi
echo ""

echo "7️⃣ Container GPU Support:"
if [ -n "$NVIDIA_VISIBLE_DEVICES" ]; then
    echo "✅ NVIDIA_VISIBLE_DEVICES: $NVIDIA_VISIBLE_DEVICES"
else
    echo "❌ NVIDIA_VISIBLE_DEVICES: NOT SET"
fi

if [ -n "$NVIDIA_DRIVER_CAPABILITIES" ]; then
    echo "✅ NVIDIA_DRIVER_CAPABILITIES: $NVIDIA_DRIVER_CAPABILITIES"
else
    echo "❌ NVIDIA_DRIVER_CAPABILITIES: NOT SET"
fi
echo ""

echo "8️⃣ Quick Mining Test:"
echo "Testing mining executable basic functionality..."
if [ -x "/usr/local/bin/inference-cuda" ]; then
    echo "✅ inference-cuda executable permissions: OK"
    if /usr/local/bin/inference-cuda --help >/dev/null 2>&1; then
        echo "✅ inference-cuda help output: OK"
    else
        echo "⚠️  inference-cuda help failed (might need GPU context)"
    fi
else
    echo "❌ inference-cuda not executable"
fi
echo ""

echo "9️⃣ System Resources:"
echo "📊 CPU Info: $(nproc) cores"
echo "📊 Memory: $(free -h | grep '^Mem:' | awk '{print $2}') total"
echo "📊 Disk Space: $(df -h / | tail -1 | awk '{print $4}') available"
echo ""

echo "🏁 ===== DEBUG REPORT COMPLETE ====="
echo "💡 Next steps if GPU mining fails:"
echo "   1. Verify container launched with --gpus all --runtime=nvidia"
echo "   2. Check NVIDIA_VISIBLE_DEVICES and NVIDIA_DRIVER_CAPABILITIES"
echo "   3. Test: python3 /app/start_mining.py"
echo ""