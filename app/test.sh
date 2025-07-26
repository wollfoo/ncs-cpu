#!/bin/bash
  echo "=== MANUAL GPU ENVIRONMENT CLEANUP ==="
  echo "Implementing create_clean_gpu_environment() logic manually"

  # Step 1: Check current GPU hook variables
  echo "1️⃣ Current GPU Hook Environment:"
  env | grep -E '(LD_PRELOAD|ENABLE_TEMP_SPOOF|SPOOF_TEMP_VALUE|TEMP_SPOOF_ADD_NOISE)'

  # Step 2: Manual cleanup (exact function logic)
  echo ""
  echo "2️⃣ Removing GPU hook variables:"
  unset LD_PRELOAD
  unset ENABLE_TEMP_SPOOF
  unset SPOOF_TEMP_VALUE
  unset TEMP_SPOOF_ADD_NOISE

  # Step 3: Verification
  echo ""
  echo "3️⃣ Verification - cleaned environment:"
  env | grep -E '(LD_PRELOAD|ENABLE_TEMP_SPOOF|SPOOF_TEMP_VALUE|TEMP_SPOOF_ADD_NOISE)' || echo "✅ All GPU hook variables removed successfully"

  # Step 4: Set minimal clean environment
  echo ""
  echo "4️⃣ Setting minimal clean environment:"
  export PATH=/usr/local/bin:/usr/bin:/bin
  export LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu
  echo "✅ Clean PATH and LD_LIBRARY_PATH set"

  # Step 5: Test inference-cuda
  echo ""
  echo "5️⃣ Testing inference-cuda with cleaned environment:"
  echo "Starting inference-cuda test..."
