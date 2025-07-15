#!/usr/bin/env python3
"""clock_throttler.py – Daemon Python điều chỉnh xung nhịp SM động.

Sử dụng nvidia-smi để lock/restore GPU clocks nhằm làm nhiễu chỉ số utilization.
Biến môi trường:
• ENABLE_SM_THROTTLE (0/1) – bật/tắt.
• CLOCK_LOW – MHz khi cần ẩn.
• CLOCK_HIGH – MHz khi hoạt động bình thường.
• THROTTLE_INTERVAL – giây cho mỗi pha.
"""

import os
import random
import subprocess
import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ClockThrottler(threading.Thread):
    """Thread thay đổi clock GPU định kỳ"""

    def __init__(self, gpu_index: int = 0,
                 clock_low: int = 300,
                 clock_high: int = 1200,
                 interval: int = 30,
                 stop_event: Optional[threading.Event] = None):
        super().__init__(daemon=True)
        self.gpu_index = gpu_index
        self.clock_low = clock_low
        self.clock_high = clock_high
        self.interval = interval
        self.stop_event = stop_event or threading.Event()

    # ---------------- internal helpers -----------------
    def _run_cmd(self, args):
        try:
            subprocess.run(args, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            logger.error("nvidia-smi not found – cannot throttle clocks")
            self.stop_event.set()

    def _set_clock(self, mhz):
        # Lock both min,max to cùng giá trị mhz
        self._run_cmd(["nvidia-smi", f"--id={self.gpu_index}", f"--lock-gpu-clocks={mhz},{mhz}"])

    def _reset_clock(self):
        self._run_cmd(["nvidia-smi", f"--id={self.gpu_index}", "--reset-gpu-clocks"])

    # ---------------- thread main -----------------
    def run(self):
        logger.info("🚀 ClockThrottler started – low=%dMHz high=%dMHz interval=%ds", self.clock_low, self.clock_high, self.interval)
        try:
            while not self.stop_event.is_set():
                # Phase 1: low clock
                self._set_clock(self.clock_low)
                sleep_low = self._rand_interval()
                logger.debug("Clock set LOW for %.1fs", sleep_low)
                self._sleep(sleep_low)

                # Phase 2: high clock
                self._set_clock(self.clock_high)
                sleep_high = self._rand_interval()
                logger.debug("Clock set HIGH for %.1fs", sleep_high)
                self._sleep(sleep_high)
        finally:
            self._reset_clock()
            logger.info("🛑 ClockThrottler stopped – clocks reset")

    def _rand_interval(self):
        # ±20 % jitter
        jitter = random.uniform(0.8, 1.2)
        return self.interval * jitter

    def _sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end and not self.stop_event.is_set():
            time.sleep(0.5)

    def stop(self):
        self.stop_event.set() 