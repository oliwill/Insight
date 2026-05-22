#!/usr/bin/env python3
"""
Podwise 同步脚本 - 自动同步 Podcast 笔记到 Obsidian

用法:
    python scripts/podwise_sync.py              # 同步最近 7 天的 episodes
    python scripts/podwise_sync.py --days 3     # 同步最近 3 天
    python scripts/podwise_sync.py --dry-run    # 只显示不同步
    python scripts/podwise_sync.py --list       # 列出最近的 episodes

依赖:
    - Podwise CLI (podwise)
    - podwise auth 已完成

环境变量 (.env):
    PODWISE_CLI_PATH      - Podwise CLI 路径（默认: podwise）
    PODWISE_SYNC_DAYS     - 同步天数（默认: 7）
    PODWISE_OUTPUT_DIR    - 输出目录（默认: OBSIDIAN_CLIPPINGS_DIR）
"""
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv()

# ========== 配置 ==========
PODWISE_CLI = os.getenv("PODWISE_CLI_PATH", "podwise")
PODWISE_DAYS = int(os.getenv("PODWISE_SYNC_DAYS", "7"))
OUTPUT_DIR = os.getenv("PODWISE_OUTPUT_DIR") or os.getenv("OBSIDIAN_CLIPPINGS_DIR", "")

# ========== 工具函数 ==========


def check_podwise() -> bool:
    """检查 Podwise CLI 是否可用"""
    try:
        result = subprocess.run(
            [PODWISE_CLI, "config", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def get_episode_list(days: int) -> list:
    """
    获取最近 N 天的 episodes

    Returns:
        List of dict with keys: url, title, podcast_name, published_at
    """
    try:
        # 使用 list episodes 命令
        cmd = [PODWISE_CLI, "list", "episodes", "--days", str(days), "--json"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"WARNING: 获取 episode 列表失败: {result.stderr}")
            return []

        # 解析 JSON 输出
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "episodes" in data:
                    return data["episodes"]
            except json.JSONDecodeError:
                pass

        # 如果 JSON 解析失败，回退到文本解析
        return parse_text_list(result.stdout)

    except subprocess.TimeoutExpired:
        print("WARNING: 获取 episode 列表超时")
        return []
    except Exception as e:
        print(f"ERROR: 获取 episode 列表失败: {e}")
        return []


def parse_text_list(text: str) -> list:
    """解析文本格式的 episode 列表"""
    episodes = []
    current_episode = {}

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # 简单解析（实际格式需要根据 CLI 输出调整）
        if "http" in line:
            current_episode["url"] = line.split()[0]
        elif current_episode.get("url"):
            episodes.append(current_episode)
            current_episode = {}

    return episodes


def sync_episode(episode_url: str, output_dir: Path, dry_run: bool = False) -> dict:
    """
    同步单个 episode 到 Obsidian

    Returns:
        {"success": bool, "path": str, "error": str}
    """
    result = {"success": False, "path": "", "error": ""}

    try:
        # 使用 episode-notes workflow
        cmd = [
            PODWISE_CLI,
            "episode-notes",
            episode_url,
            "--obsidian",
            "--output", str(output_dir),
        ]

        if dry_run:
            print(f"  [DRY RUN] {' '.join(cmd)}")
            result["success"] = True
            return result

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if proc.returncode == 0:
            # 查找生成的文件
            output_files = list(output_dir.glob("*.md"))
            if output_files:
                # 取最新的文件
                latest = max(output_files, key=lambda p: p.stat().st_mtime)
                result["success"] = True
                result["path"] = str(latest)

                # 添加 frontmatter
                add_frontmatter(latest, episode_url)
            else:
                result["error"] = "未找到生成的文件"
        else:
            result["error"] = proc.stderr

    except subprocess.TimeoutExpired:
        result["error"] = "处理超时"
    except Exception as e:
        result["error"] = str(e)

    return result


def add_frontmatter(file_path: Path, episode_url: str):
    """在文件中添加 frontmatter"""
    try:
        content = file_path.read_text(encoding="utf-8")

        # 检查是否已有 frontmatter
        if content.startswith("---"):
            return

        # 添加 frontmatter
        frontmatter = f"""---
source: podwise
url: {episode_url}
analyze: true
tags: podcast
imported: {datetime.now().strftime("%Y-%m-%d %H:%M")}
---

{content}
"""

        file_path.write_text(frontmatter, encoding="utf-8")

    except Exception as e:
        print(f"  WARNING: 添加 frontmatter 失败: {e}")


# ========== 主程序 ==========


def main():
    parser = argparse.ArgumentParser(description="Podwise 同步脚本")
    parser.add_argument("--days", type=int, default=PODWISE_DAYS, help="同步最近 N 天")
    parser.add_argument("--dry-run", action="store_true", help="只显示不同步")
    parser.add_argument("--list", action="store_true", help="只列出 episodes")
    args = parser.parse_args()

    # 检查 Podwise CLI
    if not check_podwise():
        print("ERROR: Podwise CLI 不可用")
        print("请安装: brew install hardhackerlabs/podwise-tap/podwise")
        print("或: curl -sL https://raw.githubusercontent.com/hardhackerlabs/podwise-cli/main/install.sh | sh")
        print("然后运行: podwise auth")
        return 1

    # 检查输出目录
    output_dir = Path(OUTPUT_DIR) if OUTPUT_DIR else Path.cwd() / "clippings"
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"OUTPUT_DIR: {output_dir}")
    print(f"SYNC_DAYS: 最近 {args.days} 天")

    # 获取 episode 列表
    print("\nGET EPISODE LIST...")
    episodes = get_episode_list(args.days)

    if not episodes:
        print("NO_EPISODES")
        return 0

    print(f"FOUND_EPISODES: {len(episodes)}")

    # 如果只是列表
    if args.list:
        for i, ep in enumerate(episodes[:20], 1):
            title = ep.get("title", "无标题")
            podcast = ep.get("podcast_name", "未知")
            url = ep.get("url", "")
            print(f"{i}. {title}")
            print(f"   PODCAST: {podcast}")
            print(f"   URL: {url}")
        return 0

    # 同步
    print(f"\nSTART_SYNC...")

    results = {"success": 0, "failed": 0, "skipped": 0}

    for i, ep in enumerate(episodes, 1):
        title = ep.get("title", "无标题")
        url = ep.get("url", "")

        print(f"\n[{i}/{len(episodes)}] {title}")

        if not url:
            print(f"  WARNING: 跳过: 无 URL")
            results["skipped"] += 1
            continue

        result = sync_episode(url, output_dir, dry_run=args.dry_run)

        if result["success"]:
            print(f"  OK: {result['path']}")
            results["success"] += 1
        elif result["error"]:
            print(f"  ERROR: {result['error']}")
            results["failed"] += 1

    # 总结
    print(f"\n{'='*50}")
    print(f"同步完成:")
    print(f"  OK: {results['success']}")
    print(f"  ERROR: {results['failed']}")
    print(f"  SKIPPED: {results['skipped']}")
    print(f"{'='*50}")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
