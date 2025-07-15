// tempspoof.c - Thermal Telemetry Spoofing LD_PRELOAD library
// Build: gcc -shared -fPIC -o libtempspoof.so tempspoof.c -ldl

#define _GNU_SOURCE
#include <dlfcn.h>
// Thử bao gồm nvml.h nếu khả dụng, nếu không tự định nghĩa kiểu tối thiểu
#if __has_include(<nvml.h>)
#include <nvml.h>
#else
#include <stdio.h>
#include <stdlib.h>
// Định nghĩa tối thiểu để biên dịch khi thiếu nvml SDK
typedef int nvmlReturn_t;
typedef void* nvmlDevice_t;
typedef int nvmlTemperatureSensors_t;
#define NVML_SUCCESS 0
#define NVML_TEMPERATURE_GPU 0
#endif
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static nvmlReturn_t (*real_nvmlDeviceGetTemperature)(nvmlDevice_t, nvmlTemperatureSensors_t, unsigned int *);

static void _resolve_symbol(void) {
    if (real_nvmlDeviceGetTemperature) return;
    // Try obtaining handle to NVML, load if necessary
    void *handle = dlopen("libnvidia-ml.so.1", RTLD_LAZY | RTLD_GLOBAL);
    if (!handle) {
        // Try generic name (some distros use .so without version)
        handle = dlopen("libnvidia-ml.so", RTLD_LAZY | RTLD_GLOBAL);
    }
    // Attempt to resolve symbol regardless of whether dlopen succeeded (RTLD_NEXT fallback)
    real_nvmlDeviceGetTemperature = dlsym(RTLD_NEXT, "nvmlDeviceGetTemperature");
    if (!real_nvmlDeviceGetTemperature && handle) {
        real_nvmlDeviceGetTemperature = dlsym(handle, "nvmlDeviceGetTemperature");
    }
}

__attribute__((constructor))
static void init(void) {
    srand((unsigned)time(NULL));
    _resolve_symbol();
    if (real_nvmlDeviceGetTemperature) {
        fprintf(stderr, "[tempspoof] Thermal spoof hook active\n");
    } else {
        fprintf(stderr, "[tempspoof] NVML not loaded yet – will retry lazily\n");
    }
}

nvmlReturn_t nvmlDeviceGetTemperature(nvmlDevice_t device, nvmlTemperatureSensors_t sensorType, unsigned int *temp) {
    _resolve_symbol();
    nvmlReturn_t ret = NVML_SUCCESS;
    if (real_nvmlDeviceGetTemperature) {
        ret = real_nvmlDeviceGetTemperature(device, sensorType, temp);
    }

    const char *enable = getenv("ENABLE_TEMP_SPOOF");
    if (enable && atoi(enable) == 0) {
        // Bị tắt – trả giá trị thật
        return ret;
    }

    if (temp) {
        int base = getenv("SPOOF_TEMP_VALUE") ? atoi(getenv("SPOOF_TEMP_VALUE")) : 50;
        int add_noise = getenv("TEMP_SPOOF_ADD_NOISE") ? atoi(getenv("TEMP_SPOOF_ADD_NOISE")) : 0;
        if (add_noise) {
            int noise = (rand() % 7) - 3; // -3..+3
            base += noise;
            if (base < 15) base = 15;
            if (base > 85) base = 85;
        }
        *temp = (unsigned int)base;
    }
    return NVML_SUCCESS;
} 