#!/usr/bin/env python3
"""
Telegram Bot - Trader-Obsidian 移动端交互接口

用法:
    python telegram_bot.py              # 启动 bot
    python telegram_bot.py --polling    # 使用长轮询模式（默认）
    python telegram_bot.py --webhook    # 使用 webhook 模式（需配置服务器）

命令:
    /note [TICKER] 内容...  - 写入笔记到 Inbox
    /get TICKER             - 读取股票分析摘要
    /scan                   - 触发 Inbox 扫描
    /inbox                  - 查看待处理列表
    /task                   - 查看待办任务
    /help                   - 显示帮助

环境变量 (.env):
    TELEGRAM_BOT_TOKEN      - Bot Token（从 @BotFather 获取）
    TELEGRAM_USER_ID        - 用户 ID（从 @userinfobot 获取，仅响应特定用户）
"""
import os
import sys
import re
import asyncio
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

# 添加项目根目录到路径
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv()

try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
except ImportError:
    Update = Bot = Application = CommandHandler = MessageHandler = ContextTypes = filters = None

# 导入项目模块
from inbox_scanner import (
    scan_inbox,
    get_pending_analysis,
    extract_stock_codes,
    get_related_materials,
)
from memory.manager import MemoryManager
from notification import notify_telegram

# ========== 配置 ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")

OBSIDIAN_TASKS_DIR = os.getenv("OBSIDIAN_TASKS_DIR", "")
WIKI_BASE_DIR = os.getenv("WIKI_BASE_DIR", "")
WIKI_SUBDIR = os.getenv("WIKI_SUBDIR", "4_Trader/Analysis")

# 日志文件
LOG_FILE = Path(OBSIDIAN_TASKS_DIR) / "telegram_log.md" if OBSIDIAN_TASKS_DIR else None

# ========== 股票代码提取正则 ==========
# 匹配 $AAPL, AAPL, AAPL.US, 00700.HK 等格式
TICKER_PATTERN = re.compile(
    r'\$([A-Z]{1,5})\b|'              # $AAPL
    r'\b([A-Z]{1,5})\b|'              # AAPL
    r'\b([A-Z]{1,5}\.US)\b|'          # AAPL.US
    r'\b([0-9]{5}\.HK)\b|'            # 00700.HK
    r'\b((?:SH|SZ|BJ)[0-9]{6})\b',    # SH603906
    re.IGNORECASE
)

# ========== 工具函数 ==========


def is_authorized(user_id: int) -> bool:
    """检查用户是否有权限使用 bot"""
    if not TELEGRAM_USER_ID:
        return True  # 未配置则允许所有人
    return str(user_id) == TELEGRAM_USER_ID


def log_interaction(command: str, user_input: str, response: str):
    """记录 bot 交互到日志文件"""
    if not LOG_FILE:
        return

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n## {timestamp} - {command}\n")
            f.write(f"**输入**: {user_input}\n\n")
            f.write(f"**输出**: {response}\n\n")
    except Exception:
        pass  # 日志失败不影响主流程


def extract_ticker(text: str) -> Optional[str]:
    """从文本中提取第一个股票代码"""
    match = TICKER_PATTERN.search(text)
    if not match:
        return None

    # 提取匹配的代码
    for group in match.groups():
        if group:
            return group.upper()
    return None


def normalize_ticker(ticker: str) -> str:
    """标准化股票代码格式"""
    ticker = ticker.upper()

    # 美股添加 .US 后缀
    if re.match(r'^[A-Z]{1,5}$', ticker) and not ticker.endswith('.US'):
        return f"{ticker}.US"

    # 港股
    if re.match(r'^[0-9]{5}$', ticker):
        return f"{ticker}.HK"

    # A股
    if re.match(r'^(SH|SZ|BJ)[0-9]{6}$', ticker, re.IGNORECASE):
        return ticker.upper()

    return ticker


def truncate_text(text: str, max_length: int = 4000) -> str:
    """截断文本以适应 Telegram 消息长度限制"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_analysis_summary(context: str, ticker: str) -> str:
    """格式化分析报告摘要"""
    if not context:
        return f"❌ 未找到 {ticker} 的分析记录"

    # 提取关键信息
    lines = context.split('\n')

    # 查找综合评估表
    eval_section = []
    in_eval = False
    for line in lines:
        if '综合评估' in line or 'Evaluation' in line:
            in_eval = True
        if in_eval:
            eval_section.append(line)
            if len(eval_section) > 20:  # 限制行数
                break

    # 查找最新分析时间线
    timeline_section = []
    in_timeline = False
    for line in lines:
        if '分析时间线' in line or 'Timeline' in line:
            in_timeline = True
        if in_timeline:
            timeline_section.append(line)
            if len(timeline_section) > 10:
                break

    result = f"📊 {ticker} 分析摘要\n\n"

    if eval_section:
        result += "【综合评估】\n"
        result += '\n'.join(eval_section[:15]) + "\n\n"

    if timeline_section:
        result += "【最近分析】\n"
        result += '\n'.join(timeline_section[:8]) + "\n\n"

    result += f"💡 使用 /get {ticker} 获取完整分析"

    return truncate_text(result)


# ========== 命令处理函数 ==========


async def start(update: Any, context: Any):
    """启动命令"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你没有权限使用此 bot")
        return

    welcome = (
        "👋 欢迎使用 Trader-Obsidian Bot\n\n"
        "可用命令:\n"
        "/note [代码] 内容 - 写入笔记\n"
        "/get 代码 - 读取分析\n"
        "/scan - 扫描 Inbox\n"
        "/inbox - 待处理列表\n"
        "/task - 待办任务\n"
        "/help - 帮助\n\n"
        "也可以直接转发推文，会自动提取内容并归类。"
    )
    await update.message.reply_text(welcome)
    log_interaction("start", update.message.text, welcome)


async def help_command(update: Any, context: Any):
    """帮助命令"""
    help_text = (
        "📖 命令说明\n\n"
        "📝 /note [代码] 内容\n"
        "   写入笔记到 Inbox\n"
        "   例: /note AAPL 看好财报，准备建仓\n\n"
        "📊 /get 代码\n"
        "   读取股票分析摘要\n"
        "   例: /get NVDA\n\n"
        "🔄 /scan\n"
        "   触发 Inbox 扫描\n\n"
        "📬 /inbox\n"
        "   查看待处理列表\n\n"
        "✅ /task\n"
        "   查看待办任务\n\n"
        "💡 转发推文\n"
        "   自动提取内容并按股票代码归类"
    )
    await update.message.reply_text(help_text)
    log_interaction("help", update.message.text, help_text)


async def note_command(update: Any, context: Any):
    """写入笔记命令"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你没有权限使用此 bot")
        return

    # 获取消息内容（去掉 /note 前缀）
    text = update.message.text
    content = text[len("/note"):].strip()

    if not content:
        await update.message.reply_text("❌ 请输入笔记内容\n例: /note AAPL 看好财报")
        return

    # 提取股票代码
    ticker = extract_ticker(content)
    if not ticker:
        await update.message.reply_text(
            "❌ 未识别到股票代码\n"
            "支持的格式: $AAPL, AAPL.US, 00700.HK, SH603906"
        )
        return

    # 标准化代码
    normalized = normalize_ticker(ticker)

    try:
        mm = MemoryManager()
        path = mm.save_material(
            stock_code=normalized,
            source_type="telegram",
            content=content,
            title=f"Telegram Note - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            summary=content[:100],
            tags="telegram,quick-note",
        )

        response = f"✅ 已写入 {normalized}\n📁 {path}"
        await update.message.reply_text(response)
        log_interaction("note", content, response)

    except Exception as e:
        error_msg = f"❌ 写入失败: {str(e)}"
        await update.message.reply_text(error_msg)
        log_interaction("note", content, error_msg)


async def get_command(update: Any, context: Any):
    """读取分析命令"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你没有权限使用此 bot")
        return

    # 获取股票代码
    args = context.args
    if not args:
        await update.message.reply_text("❌ 请输入股票代码\n例: /get AAPL")
        return

    ticker = args[0].upper()
    normalized = normalize_ticker(ticker)

    try:
        mm = MemoryManager()
        context_data = mm.get_stock_context(normalized, include_materials=False)

        response = format_analysis_summary(context_data, normalized)
        await update.message.reply_text(response)
        log_interaction("get", ticker, "分析摘要已返回")

    except Exception as e:
        error_msg = f"❌ 读取失败: {str(e)}"
        await update.message.reply_text(error_msg)
        log_interaction("get", ticker, error_msg)


async def scan_command(update: Any, context: Any):
    """触发扫描命令"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你没有权限使用此 bot")
        return

    await update.message.reply_text("🔄 正在扫描 Inbox...")

    try:
        result = subprocess.run(
            [sys.executable, "run_analysis.py", "--scan"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            response = f"✅ 扫描完成\n\n{result.stdout}"
        else:
            response = f"⚠️ 扫描完成但有错误\n\n{result.stderr}"

        await update.message.reply_text(truncate_text(response))
        log_interaction("scan", "", response)

    except subprocess.TimeoutExpired:
        error_msg = "⏱️ 扫描超时（5分钟）"
        await update.message.reply_text(error_msg)
        log_interaction("scan", "", error_msg)
    except Exception as e:
        error_msg = f"❌ 扫描失败: {str(e)}"
        await update.message.reply_text(error_msg)
        log_interaction("scan", "", error_msg)


async def inbox_command(update: Any, context: Any):
    """待处理列表命令"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你没有权限使用此 bot")
        return

    try:
        pending = get_pending_analysis()

        if not pending:
            response = "📭 Inbox 为空，无待处理材料"
        else:
            lines = [f"📬 待处理列表 ({len(pending)} 项)\n"]

            for item in pending[:10]:  # 最多显示 10 项
                ticker_str = ", ".join(item.stock_codes) if item.stock_codes else "无代码"
                lines.append(f"• {item.filename}")
                lines.append(f"  代码: {ticker_str}")
                lines.append(f"  来源: {item.source_type}")

            if len(pending) > 10:
                lines.append(f"\n... 还有 {len(pending) - 10} 项")

            response = "\n".join(lines)

        await update.message.reply_text(truncate_text(response))
        log_interaction("inbox", "", f"{len(pending) if pending else 0} 项")

    except Exception as e:
        error_msg = f"❌ 查询失败: {str(e)}"
        await update.message.reply_text(error_msg)
        log_interaction("inbox", "", error_msg)


async def task_command(update: Any, context: Any):
    """待办任务命令"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ 你没有权限使用此 bot")
        return

    if not OBSIDIAN_TASKS_DIR:
        await update.message.reply_text("❌ 未配置 TASKS_DIR")
        return

    try:
        tasks_dir = Path(OBSIDIAN_TASKS_DIR)
        if not tasks_dir.exists():
            response = "📋 Tasks 目录不存在"
        else:
            # 获取所有 .md 文件
            task_files = list(tasks_dir.glob("*.md"))
            task_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            if not task_files:
                response = "📋 无待办任务"
            else:
                lines = [f"📋 待办任务 ({len(task_files)} 项)\n"]

                for f in task_files[:10]:
                    # 读取 frontmatter
                    content = f.read_text(encoding="utf-8")
                    title = "无标题"
                    for line in content.split("\n")[:10]:
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"\'')
                            break

                    lines.append(f"• {title}")
                    lines.append(f"  📄 {f.name}")

                if len(task_files) > 10:
                    lines.append(f"\n... 还有 {len(task_files) - 10} 项")

                response = "\n".join(lines)

        await update.message.reply_text(truncate_text(response))
        log_interaction("task", "", f"{len(task_files)} 项" if task_files else "无")

    except Exception as e:
        error_msg = f"❌ 查询失败: {str(e)}"
        await update.message.reply_text(error_msg)
        log_interaction("task", "", error_msg)


async def handle_forward(update: Any, context: Any):
    """处理转发推文"""
    if not is_authorized(update.effective_user.id):
        return

    message = update.message

    # 检查是否是转发消息
    if not message.forward_from:
        # 普通消息，尝试提取股票代码并保存
        text = message.text
        if not text:
            return

        ticker = extract_ticker(text)
        if ticker:
            normalized = normalize_ticker(ticker)
            try:
                mm = MemoryManager()
                mm.save_material(
                    stock_code=normalized,
                    source_type="telegram",
                    content=text,
                    title=f"Telegram Message - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    tags="telegram,message",
                )
                await message.reply_text(f"✅ 已归类到 {normalized}")
                log_interaction("auto_sort", text[:50], normalized)
            except Exception:
                pass
        return

    # 处理转发推文
    forward_from = message.forward_from

    if forward_from.username and "twitter" in str(message).lower():
        # 从 Twitter 转发
        text = message.text or message.caption or ""
        ticker = extract_ticker(text)

        if ticker:
            normalized = normalize_ticker(ticker)
            try:
                mm = MemoryManager()
                mm.save_material(
                    stock_code=normalized,
                    source_type="twitter",
                    content=text,
                    title=f"Twitter Forward - @{forward_from.username}",
                    tags="twitter,forward",
                )
                await message.reply_text(f"✅ 推文已归类到 {normalized}")
                log_interaction("twitter_forward", text[:50], normalized)
            except Exception:
                pass
        else:
            # 无股票代码，存入 raw
            # TODO: 实现 raw 目录保存逻辑
            pass


# ========== 主程序 ==========


def main():
    """启动 bot"""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set")
        print("Configure TELEGRAM_BOT_TOKEN=your_token in .env")
        print("Get one from @BotFather with /newbot")
        sys.exit(1)

    # 创建应用
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 注册命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("get", get_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("inbox", inbox_command))
    application.add_handler(CommandHandler("task", task_command))

    # 注册消息处理器（处理转发和普通消息）
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_forward))

    # 启动
    print("🤖 Trader-Obsidian Bot 启动中...")
    if TELEGRAM_USER_ID:
        print(f"🔒 仅响应用户 ID: {TELEGRAM_USER_ID}")
    else:
        print("⚠️  警告: 未设置 TELEGRAM_USER_ID，所有人都可以使用")

    print("Polling mode enabled...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def main_cli():
    parser = argparse.ArgumentParser(description="Telegram Bot - Trader-Obsidian")
    parser.add_argument("--polling", action="store_true", help="使用长轮询模式（默认）")
    parser.add_argument("--webhook", action="store_true", help="使用 webhook 模式（需配置服务器）")
    args = parser.parse_args()

    if Application is None:
        print("ERROR: missing python-telegram-bot dependency")
        print("Install with: pip install python-telegram-bot")
        return 1

    if args.webhook:
        print("Webhook mode is not implemented yet.")
        return 1

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set")
        print("Configure TELEGRAM_BOT_TOKEN=your_token in .env")
        print("Get one from @BotFather with /newbot")
        return 1

    main()
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
