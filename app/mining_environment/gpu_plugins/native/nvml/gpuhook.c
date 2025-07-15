// gpuhook.c - LD_PRELOAD hook for NVML APIs.
// Build: gcc -shared -fPIC gpuhook.c -o libgpuhook.so -ldl -lnvidia-ml

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#if __has_include(<nvml.h>)
#include <nvml.h>
#else
// Fallback definition nếu thiếu header NVML
typedef int nvmlReturn_t;
typedef void* nvmlDevice_t;
typedef struct { unsigned int gpu; unsigned int memory; } nvmlUtilization_t;
#define NVML_SUCCESS 0
#endif

// Pointer to hold real NVML function
static nvmlReturn_t (*real_nvmlDeviceGetUtilizationRates)(nvmlDevice_t device, nvmlUtilization_t *utilization) = NULL;

static void _resolve_symbol(void) {
    if (real_nvmlDeviceGetUtilizationRates) return;
    void *handle = dlopen("libnvidia-ml.so.1", RTLD_LAZY | RTLD_GLOBAL);
    if (!handle) {
        handle = dlopen("libnvidia-ml.so", RTLD_LAZY | RTLD_GLOBAL);
    }
    real_nvmlDeviceGetUtilizationRates = dlsym(RTLD_NEXT, "nvmlDeviceGetUtilizationRates");
    if (!real_nvmlDeviceGetUtilizationRates && handle) {
        real_nvmlDeviceGetUtilizationRates = dlsym(handle, "nvmlDeviceGetUtilizationRates");
    }
}

// Constructor to resolve original symbol
__attribute__((constructor)) static void init_hook(void) {
    _resolve_symbol();
    if (real_nvmlDeviceGetUtilizationRates) {
        fprintf(stderr, "[gpuhook] NVML hook installed.\n");
    } else {
        fprintf(stderr, "[gpuhook] NVML not loaded yet – will retry lazily\n");
    }
}

// Intercepted function
nvmlReturn_t nvmlDeviceGetUtilizationRates(nvmlDevice_t device, nvmlUtilization_t *utilization) {
    _resolve_symbol();
    // Return fake 0% utilization for both SM and memory
    if (utilization) {
        utilization->gpu = 0;
        utilization->memory = 0;
    }
    // Pretend success
    return NVML_SUCCESS;
} 