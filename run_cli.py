#!/usr/bin/env python3
"""
Chạy bot không cần UI (tiện test nhanh / chạy nền trên server).

Ví dụ:
    python run_cli.py --task thanh_nhai_thu_6acc.yaml            # chạy trên tất cả device tìm thấy
    python run_cli.py --task thanh_nhai_thu_6acc.yaml --device 127.0.0.1:5555
    python run_cli.py --list-devices
    python run_cli.py --list-tasks
"""

from __future__ import annotations

import argparse
import sys
import time

from nthbot.adb import Device
from nthbot.orchestrator import AppConfig, Orchestrator, discover_devices, list_tasks, load_task


def main():
    ap = argparse.ArgumentParser(description="NTH Bot CLI")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--task", help="tên file task trong thư mục tasks/")
    ap.add_argument("--device", action="append", help="serial cụ thể (lặp lại để chạy nhiều)")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--list-tasks", action="store_true")
    ap.add_argument("--detect-package", action="store_true",
                    help="in package của app đang mở trên thiết bị (mở game trước rồi chạy)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")   # chạy nền/redirect trên Windows mặc định cp1252 -> lỗi in tiếng Việt

    cfg = AppConfig.load(args.config)

    if args.list_tasks:
        for t in list_tasks(cfg):
            print(t)
        return

    devices = discover_devices(cfg)
    if args.device:
        devices = [Device(serial=s, name=s, adb_path=cfg.adb_path) for s in args.device]

    if args.list_devices:
        for d in devices:
            print(f"{d.name}\t{d.serial}")
        return

    if args.detect_package:
        if not devices:
            print("Không thấy thiết bị. Bật ADB cho LDPlayer + mở game trước.")
            return
        for d in devices:
            d.connect()
            pkg = d.current_app()
            print(f"{d.name}\t{d.serial}\t->  {pkg or '(không lấy được — game đã mở chưa?)'}")
        return

    if not args.task:
        ap.error("cần --task (hoặc dùng --list-tasks)")
    if not devices:
        print("Không tìm thấy thiết bị nào. Kiểm tra LDPlayer đã chạy + config.yaml.")
        return

    task = load_task(cfg, args.task)
    orch = Orchestrator(cfg)
    print(f"Chạy task '{task.name}' trên {len(devices)} thiết bị...")
    for d in devices:
        orch.make_runner(d, task)
    orch.start_all()

    try:
        while any(r.is_running for r in orch.runners.values()):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nĐang dừng...")
        orch.stop_all()
        for r in orch.runners.values():
            r.join(timeout=10)


if __name__ == "__main__":
    main()
