"""rdt_cache_control.manager
Quản lý phân bổ LLC qua Intel RDT/CAT (resctrl).
- Cấp mặc định 25% cache cho PID miner.
- Nếu IPC < 0.9 trong adaptive callback => tăng thêm 5% (tối đa 100%).
Giống eBPF manager, module an toàn fallback khi CPU/Kernel không hỗ trợ CAT.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
import psutil
from typing import Dict, Optional, Tuple

RESCTRL_PATH = Path("/sys/fs/resctrl")

class RdtCatManager:
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        enabled: bool = True,
        min_pct: int = 25,
        max_pct: int = 100,
        step_pct: int = 5,
    ):
        self.logger = logger or logging.getLogger("RdtCat")
        self.enabled = enabled
        self.min_pct = min_pct
        self.max_pct = max_pct
        self.step_pct = step_pct
        self._classid_counter = 1
        self.group_map: Dict[int, str] = {}  # pid -> group name
        self.perf_map: Dict[int, Tuple[int, int, Tuple[int, int]]] = {}
        self._lock = threading.RLock()
        self._supported = self._check_support()
        if self._supported and self.enabled:
            self.logger.info("[RDT] CAT support OK. resctrl mounted.")
            threading.Thread(target=self._cleanup_thread, daemon=True).start()
            threading.Thread(target=self._ipc_loop, daemon=True).start()
        else:
            self.logger.warning("[RDT] Không hỗ trợ CAT trên hệ thống hiện tại.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_active(self) -> bool:
        return self._supported and self.enabled

    def set_cache_pct(self, pid: int, pct: int) -> None:
        if not self._supported:
            return
        pct = max(self.min_pct, min(self.max_pct, pct))
        cbm_mask = self._pct_to_cbm(pct)
        group_name = self._ensure_group(pid, cbm_mask)
        try:
            with open(RESCTRL_PATH / group_name / "tasks", "w", encoding="utf-8") as f:
                f.write(str(pid))
            self.group_map[pid] = group_name
            self.logger.debug(f"[RDT] Đặt **[PID]** (Process ID - mã định danh tiến trình)={pid} vào group={group_name}, pct={pct}%.")
            # mở perf counters per PID
            self.perf_map[pid] = self._open_perf_counters(pid)
        except Exception as e:  # noqa: BLE001
            self.logger.debug(f"[RDT] Không thể ghi tasks: {e}")

    def adjust_cache_on_ipc(self, pid: int, ipc: float) -> None:
        if not self._supported or pid not in self.group_map:
            return
        current_group = self.group_map[pid]
        try:
            with open(RESCTRL_PATH / current_group / "schemata", "r", encoding="utf-8") as f:
                line = f.readline().strip()
            match = re.search(r"L3:0=(.+)", line)
            if not match:
                return
            current_mask_hex = match.group(1)
            current_pct = self._mask_to_pct(int(current_mask_hex, 16))
            if ipc < 0.9:
                new_pct = min(current_pct + self.step_pct, self.max_pct)
                self._ipc_low_count = self._ipc_low_count + 1 if hasattr(self, '_ipc_low_count') else 1
            else:
                # nếu IPC cao liên tiếp 3 lần ⇒ giảm về min_pct
                if hasattr(self, '_ipc_low_count'):
                    self._ipc_low_count = 0
                if ipc >= 0.95:
                    new_pct = max(current_pct - self.step_pct, self.min_pct)
                else:
                    new_pct = current_pct
            if new_pct != current_pct:
                new_mask = self._pct_to_cbm(new_pct)
                self._write_schemata(current_group, new_mask)
                self.logger.info(f"[RDT] IPC={ipc:.2f} => cập nhật LLC {current_pct}% → {new_pct}% cho **[PID]** (Process ID - mã định danh tiến trình)={pid}")
        except Exception as e:  # noqa: BLE001
            self.logger.debug(f"[RDT] adjust_cache_on_ipc **[error]** (lỗi): {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _check_support(self) -> bool:
        # 1. mount resctrl nếu chưa
        if not RESCTRL_PATH.exists():
            try:
                # Tạo mountpoint nếu kernel chưa sinh
                RESCTRL_PATH.mkdir(parents=True, exist_ok=True)
            except Exception:
                # Không thể tạo mountpoint
                return False

            try:
                subprocess.run(["mount", "-t", "resctrl", "resctrl", str(RESCTRL_PATH)], check=True)
            except Exception:
                return False
        # 2. kiểm tra file info/L3/cbm_mask
        return (RESCTRL_PATH / "info/L3/cbm_mask").exists()

    def _pct_to_cbm(self, pct: int) -> str:
        try:
            with open(RESCTRL_PATH / "info/L3/cbm_mask", "r", encoding="utf-8") as f:
                mask_bits = len(f.read().strip()) * 4  # số bit mask
        except Exception:
            mask_bits = 20  # mặc định
        bits_to_use = max(1, int(mask_bits * pct / 100))
        mask_val = (1 << bits_to_use) - 1
        return format(mask_val, 'x')

    def _mask_to_pct(self, mask: int) -> int:
        total_bits = mask.bit_length()
        used_bits = bin(mask).count("1")
        return int(used_bits / total_bits * 100)

    def _ensure_group(self, pid: int, cbm_mask_hex: str) -> str:
        # giới hạn group theo num_closids
        closid_limit = self._get_closid_limit()
        if len(self.group_map) >= closid_limit:
            # reuse nhóm theo modulo
            group_name = list(self.group_map.values())[len(self.group_map) % closid_limit]
            return group_name

        group_name = f"g{self._classid_counter}"
        if not (RESCTRL_PATH / group_name).exists():
            try:
                (RESCTRL_PATH / group_name).mkdir()
                self._write_schemata(group_name, cbm_mask_hex)
                self._classid_counter += 1
            except Exception as e:
                self.logger.debug(f"[RDT] mkdir group **[error]** (lỗi): {e}")
        return group_name

    def _write_schemata(self, group: str, cbm_mask_hex: str) -> None:
        sockets = self._get_socket_count()
        schema_line = "L3:" + ";".join(f"{s}={cbm_mask_hex}" for s in range(sockets)) + "\n"
        try:
            with open(RESCTRL_PATH / group / "schemata", "w", encoding="utf-8") as f:
                f.write(schema_line)
            for p, grp in list(self.group_map.items()):
                if not psutil.pid_exists(p):
                    try:
                        (RESCTRL_PATH / grp).rmdir()
                    except Exception:
                        pass
                    self.group_map.pop(p, None)
                    # đóng perf fds
                    if p in self.perf_map:
                        self._close_perf(self.perf_map[p])
                        self.perf_map.pop(p, None)
        except Exception as e:
            self.logger.debug(f"[RDT] write schemata **[error]** (lỗi): {e}")

    def _cleanup_thread(self):
        """Xoá group rỗng định kỳ."""
        while True:
            try:
                for p, grp in list(self.group_map.items()):
                    if not psutil.pid_exists(p):
                        try:
                            (RESCTRL_PATH / grp).rmdir()
                        except Exception:
                            pass
                        self.group_map.pop(p, None)
                time.sleep(60)
            except Exception:
                time.sleep(60)

    def _ipc_loop(self):
        """Đọc IPC mỗi 10 s và điều chỉnh cache"""
        while True:
            try:
                ipc = self._read_ipc()
                for pid in list(self.group_map.keys()):
                    self.adjust_cache_on_ipc(pid, ipc)
                time.sleep(10)
            except Exception:
                time.sleep(10)

    def _read_ipc(self) -> float:
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                cpu_line = f.readline()
            parts = cpu_line.strip().split()
            if len(parts) < 8:
                return 1.0
            user, nice, system, idle, iowait, irq, softirq, steal = map(int, parts[1:9])
            busy = user + nice + system + irq + softirq + steal
            total = busy + idle + iowait
            return busy / max(total, 1)
        except Exception:
            return 1.0

    # ------------------------------------------------------------------
    # perf helpers
    # ------------------------------------------------------------------
    def _open_perf_counters(self, pid: int):
        try:
            import ctypes, ctypes.util
            PERF_TYPE_HARDWARE = 0
            PERF_COUNT_HW_INSTRUCTIONS = 0x1
            PERF_COUNT_HW_CPU_CYCLES = 0x0

            class perf_event_attr(ctypes.Structure):
                _fields_ = [
                    ("type", ctypes.c_uint),
                    ("size", ctypes.c_uint),
                    ("config", ctypes.c_ulonglong),
                    ("sample_period", ctypes.c_ulonglong),
                    ("sample_type", ctypes.c_ulonglong),
                    ("read_format", ctypes.c_ulonglong),
                    ("flags", ctypes.c_ulonglong),
                ]

            libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)

            def _open(config):
                attr = perf_event_attr()
                attr.type = PERF_TYPE_HARDWARE
                attr.size = ctypes.sizeof(perf_event_attr)
                attr.config = config
                attr.flags = 1  # disabled
                fd = libc.syscall(298, ctypes.byref(attr), pid, -1, -1, 0)
                if fd < 0:
                    raise OSError(ctypes.get_errno(), "perf_event_open")
                libc.ioctl(fd, 0x2400, 0)
                libc.ioctl(fd, 0x2401, 0)
                return fd

            return _open(PERF_COUNT_HW_INSTRUCTIONS), _open(PERF_COUNT_HW_CPU_CYCLES), (0, 0)
        except Exception:
            return (-1, -1, (0, 0))

    def _close_perf(self, fds):
        import os
        for fd in fds[:2]:
            if fd >= 0:
                try:
                    os.close(fd)
                except Exception:
                    pass

    def _get_socket_count(self) -> int:
        try:
            nodes = [p for p in Path("/sys/devices/system/node").glob("node[0-9]*")]
            # use unique L3 index
            return max(1, len(nodes))
        except Exception:
            return 1

    def _get_closid_limit(self) -> int:
        try:
            with open(RESCTRL_PATH / "info/L3/num_closids", "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            return 16 
