#!/usr/bin/env python3
"""
run_prometheus_exporter.py - Script khởi chạy riêng cho Prometheus Exporter.

Tách biệt logic khởi chạy ra khỏi module chính để tránh RuntimeWarning
và đảm bảo một "entry point" rõ ràng.
"""

import time
import logging

from mining_environment.cpu_plugins.monitoring.health_probe import PluginHealthProbe
from mining_environment.cpu_plugins.monitoring.prometheus_exporter import CPUPluginPrometheusExporter

def main():
    """
    Hàm chính để khởi tạo và chạy Prometheus Exporter.
    """
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("PrometheusExporterRunner")

    try:
        # 1. Khởi tạo các thành phần cần thiết
        health_probe = PluginHealthProbe()
        exporter = CPUPluginPrometheusExporter(health_probe=health_probe, port=9090, logger=logger)

        # 2. Khởi động máy chủ metrics
        exporter.start_metrics_server()
        logger.info("Prometheus Exporter đã khởi động.")

        # 3. Đăng ký callback để tự động cập nhật metrics
        # Health probe sẽ chạy trong một luồng riêng và gọi callback này
        exporter.register_with_health_probe()
        logger.info("Đã đăng ký callback với Health Probe để cập nhật metrics tự động.")

        # 4. Giữ cho tiến trình chính chạy để server không bị tắt
        logger.info("Exporter đang chạy. Nhấn Ctrl+C để thoát.")
        while True:
            time.sleep(3600)  # Ngủ một khoảng thời gian dài, công việc chính diễn ra ở các luồng khác

    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu dừng, đang tắt exporter.")
    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng khi chạy exporter: {e}", exc_info=True)

if __name__ == "__main__":
    main() 