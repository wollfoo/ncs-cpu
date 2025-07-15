// mpo_kernel.cu
// CUDA Memory-Pattern Obfuscation library dành cho GPU Cloaking Manager.
// Biên dịch:  nvcc -Xcompiler -fPIC -shared mpo_kernel.cu -o libmpo.so

#include <cuda.h>
#include <cuda_runtime.h>
#include <thread>
#include <atomic>
#include <chrono>
#include <mutex>

// ---- CUDA kernel tạo nhiễu truy cập VRAM/L2 ---------------------------------
__device__ __forceinline__ unsigned int xorshift32(unsigned int *state) {
    unsigned int x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

__global__ void mpo_noise_kernel(float *scratch, size_t elements, unsigned long long seed) {
    size_t tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= elements) return;
    unsigned int state = static_cast<unsigned int>(seed ^ tid);
    unsigned int idx = xorshift32(&state) & 0xFFFF; // 64K vùng scratch
    // Dummy read-modify-write
    float val = scratch[idx];
    scratch[idx] = val + 1.0f;
}

// ---- Worker thread chạy lặp vô hạn ------------------------------------------
static std::atomic<bool> g_stop{false};

static void mpo_worker() {
    const size_t kScratchElements = 1 << 16; // 64K
    float *d_scratch = nullptr;
    cudaMalloc(&d_scratch, kScratchElements * sizeof(float));
    cudaMemset(d_scratch, 0, kScratchElements * sizeof(float));

    dim3 block(256);
    dim3 grid((kScratchElements + block.x - 1) / block.x);

    while (!g_stop.load()) {
        unsigned long long seed = static_cast<unsigned long long>(
            std::chrono::high_resolution_clock::now().time_since_epoch().count());
        mpo_noise_kernel<<<grid, block>>>(d_scratch, kScratchElements, seed);
        cudaDeviceSynchronize();
        // Jitter 50-500 µs
        std::this_thread::sleep_for(std::chrono::microseconds(100));
    }

    cudaFree(d_scratch);
}

// ---- API xuất ra cho GPUCloakingManager --------------------------------------
extern "C" void launch_mpo_kernel() {
    // Đảm bảo luồng MPO chỉ được khởi chạy và detach đúng một lần.
    static std::once_flag flag;
    std::call_once(flag, [] {
        std::thread([] { mpo_worker(); }).detach();
    });
}

extern "C" void stop_mpo_kernel() {
    g_stop.store(true);
} 