#!/usr/bin/env python3
"""
Inbox 文件监控 - 监控 Obsidian Inbox 目录变化并自动触发扫描

用法:
    python inbox_watcher.py              # 启动监控（前台）
    python inbox_watcher.py --daemon     # 后台守护进程
    python inbox_watcher.py --stop       # 停止监控

监控目录:
    - OBSIDIAN_INBOX_DIR
    - OBSIDIAN_CLIPPINGS_DIR
    - OBSIDIAN_RAW_DIR

触发条件:
    - .md 文件创建
    - Debounce: 延迟 2 秒后触发，避免重复

触发动作:
    1. 运行 run_analysis.py --scan
    2. 发送 Telegram 通知
"""
import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime
from threading import Timer

# 添加项目根目录到路径
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv()

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    class FileSystemEventHandler:
        pass

    class FileCreatedEvent:
        pass

from notification import notify_telegram

# ========== 配置 ==========
INBOX_DIR = os.getenv("OBSIDIAN_INBOX_DIR", "")
CLIPPINGS_DIR = os.getenv("OBSIDIAN_CLIPPINGS_DIR", "")
RAW_DIR = os.getenv("OBSIDIAN_RAW_DIR", "")

DEBOUNCE_DELAY = 2  # 防抖延迟（秒）
SCAN_TIMEOUT = 300  # 扫描超时（秒）

PID_FILE = Path("/tmp/trader-obsidian-watcher.pid")

# ========== 防抖机制 ==========


class Debouncer:
    """防抖器 - 延迟执行，避免重复触发"""

    def __init__(self, delay: float, callback):
        self.delay = delay
        self.callback = callback
        self.timer: Timer = None
        self.pending_files = set()

    def trigger(self, file_path: str):
        """触发防抖"""
        self.pending_files.add(file_path)

        if self.timer is not None:
            self.timer.cancel()

        self.timer = Timer(self.delay, self._execute)
        self.timer.start()

    def _execute(self):
        """执行回调"""
        if self.pending_files:
            files = list(self.pending_files)
            self.pending_files.clear()
            self.callback(files)

    def cancel(self):
        """取消待执行的回调"""
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None


# ========== 文件事件处理 ==========


class InboxHandler(FileSystemEventHandler):
    """Inbox 文件事件处理器"""

    def __init__(self, debouncer: Debouncer):
        self.debouncer = debouncer
        self.last_scan = 0
        self.scan_in_progress = False

    def on_created(self, event):
        """文件创建事件"""
        if event.is_directory:
            return

        # 只处理 .md 文件
        if not event.src_path.endswith('.md'):
            return

        # 忽略临时文件
        if '.obsidian' in event.src_path or '~' in Path(event.src_path).name:
            return

        print(f"New file detected: {Path(event.src_path).name}")

        # 触发防抖
        self.debouncer.trigger(event.src_path)

    def on_moved(self, event):
        """文件移动事件（某些编辑器保存时会发生）"""
        if event.is_directory:
            return

        if not event.dest_path.endswith('.md'):
            return

        print(f"Moved file detected: {Path(event.dest_path).name}")
        self.debouncer.trigger(event.dest_path)


def trigger_scan(files: list):
    """触发扫描"""
    print(f"\n{'='*50}")
    print(f"SCAN_TRIGGERED ({len(files)} new files)")
    print(f"{'='*50}")

    for f in files:
        print(f"  - {Path(f).name}")

    start_time = time.time()

    try:
        result = subprocess.run(
            [sys.executable, "run_analysis.py", "--scan"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT,
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            message = f"SCAN_OK ({elapsed:.1f}s)\n\n{result.stdout}"
            print(message)
        else:
            message = f"SCAN_ERROR ({elapsed:.1f}s)\n\n{result.stderr}"
            print(message)

        # 发送 Telegram 通知
        summary = (
            f"📬 Inbox 扫描完成\n"
            f"处理文件: {len(files)}\n"
            f"耗时: {elapsed:.1f}s\n"
        )

        if result.returncode != 0:
            summary += f"状态: 有错误"
        else:
            summary += f"状态: 成功"

        notify_telegram("Inbox 监控", summary)

    except subprocess.TimeoutExpired:
        message = f"SCAN_TIMEOUT ({SCAN_TIMEOUT}s)"
        print(message)
        notify_telegram("Inbox 监控", f"扫描超时")
    except Exception as e:
        message = f"SCAN_FAILED: {str(e)}"
        print(message)
        notify_telegram("Inbox 监控", f"扫描失败: {str(e)}")

    print(f"{'='*50}\n")


# ========== 守护进程管理 ==========


def start_daemon():
    """启动守护进程"""
    if not WATCHDOG_AVAILABLE:
        print("ERROR: watchdog not installed")
        print("Install with: pip install watchdog")
        return 1

    # 检查是否已在运行
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            print(f"ERROR: watcher already running (PID: {old_pid})")
            return 1
        except (OSError, ValueError):
            pass

    # 检查监控目录
    watch_dirs = []
    for name, path in [("Inbox", INBOX_DIR), ("Clippings", CLIPPINGS_DIR), ("Raw", RAW_DIR)]:
        if path and Path(path).exists():
            watch_dirs.append((name, path))
        else:
            print(f"WARNING: {name} directory missing: {path}")

    if not watch_dirs:
        print("ERROR: no directories to watch")
        print("Configure OBSIDIAN_INBOX_DIR in .env")
        return 1

    # 写 PID 文件
    PID_FILE.write_text(str(os.getpid()))

    # 创建防抖器
    debouncer = Debouncer(DEBOUNCE_DELAY, trigger_scan)

    # 创建观察者
    observer = Observer()

    for name, path in watch_dirs:
        handler = InboxHandler(debouncer)
        observer.schedule(handler, path, recursive=False)
        print(f"📁 监控 {name}: {path}")

    # 启动
    observer.start()
    print(f"Debounce delay: {DEBOUNCE_DELAY}s")
    print("Watcher running... (Ctrl+C to stop)")

    # 信号处理
    def signal_handler(signum, frame):
        print("\n🛑 收到停止信号...")
        observer.stop()
        debouncer.cancel()
        PID_FILE.unlink(missing_ok=True)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nGoodbye")

    observer.join()
    PID_FILE.unlink(missing_ok=True)
    return 0


def stop_daemon():
    """停止监控"""
    if not PID_FILE.exists():
        print("Watcher not running")
        return 0

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"Stop signal sent (PID: {pid})")

        # 等待进程退出
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                PID_FILE.unlink(missing_ok=True)
                print("Watcher stopped")
                return 0

        print("Process did not respond; force stopping")
        os.kill(pid, signal.SIGKILL)
        PID_FILE.unlink(missing_ok=True)
        return 0

    except Exception as e:
        print(f"ERROR: stop failed: {e}")
        return 1


def status_daemon():
    """查看监控状态"""
    if not PID_FILE.exists():
        print("Watcher not running")
        return 0

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        print(f"Watcher running (PID: {pid})")
        return 0
    except (OSError, ValueError):
        print("PID file exists but process is gone")
        PID_FILE.unlink(missing_ok=True)
        return 1


# ========== CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Inbox 文件监控")
    parser.add_argument("--daemon", action="store_true", help="后台守护进程模式")
    parser.add_argument("--stop", action="store_true", help="停止监控")
    parser.add_argument("--status", action="store_true", help="查看状态")
    args = parser.parse_args()

    if args.stop:
        return stop_daemon()

    if args.status:
        return status_daemon()

    # 默认启动监控
    return start_daemon()


if __name__ == "__main__":
    sys.exit(main())
