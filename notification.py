"""
通知模块 - macOS 桌面通知

用法:
    from notification import notify
    notify("分析完成", "AAPL 分析报告已写入 Obsidian")

    from notification import notify_error
    notify_error("数据获取失败", "Longbridge API 超时")
"""

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request


def _safe_print(text: str) -> None:
    stream = sys.stderr
    encoding = stream.encoding or "utf-8"
    safe_text = text.encode(encoding, errors="replace").decode(
        encoding, errors="replace"
    )
    print(safe_text, file=stream, flush=True)


def notify(title: str, message: str, sound: bool = True) -> bool:
    """
    发送 macOS 桌面通知

    Args:
        title: 通知标题
        message: 通知内容
        sound: 是否播放提示音

    Returns:
        是否成功发送
    """
    try:
        sound_cmd = 'sound name "Glass"' if sound else ""
        script = f'display notification "{message}" with title "{title}" {sound_cmd}'
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        # fallback: 打印到 stderr
        _safe_print(f"[NOTIFY] {title}: {message}")
        return False


def notify_error(title: str, message: str) -> bool:
    """发送错误通知（带错误音效）"""
    try:
        script = f'display notification "{message}" with title "ERROR: {title}" sound name "Basso"'
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        _safe_print(f"[ERROR] {title}: {message}")
        return False


def notify_success(title: str, message: str) -> bool:
    """发送成功通知"""
    return notify(f"SUCCESS: {title}", message, sound=True)


def notify_telegram(title: str, message: str) -> bool:
    """Send a Telegram notification when credentials are configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    user_id = os.getenv("TELEGRAM_USER_ID")
    if not token or not user_id:
        return notify(title, message)

    try:
        text = f"{title}\n{message}"
        payload = urllib.parse.urlencode({"chat_id": user_id, "text": text}).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except Exception:
        return notify(title, message)


def notify_feishu(title: str, message: str) -> bool:
    """飞书自定义机器人 webhook 通知。

    依赖 env `FEISHU_WEBHOOK_URL`（形如 https://open.feishu.cn/open-apis/bot/v2/hook/xxxx）。
    未配置或发送失败返回 False（由调用方降级到下一通道）。
    """
    url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if not url:
        return False
    try:
        payload = json.dumps(
            {"msg_type": "text", "content": {"text": f"{title}\n{message}"}},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="ignore")
            # 飞书成功返回 {"code":0,"msg":"success",...}
            return json.loads(body).get("code") == 0
    except Exception:
        return False


def notify_wecom(title: str, message: str) -> bool:
    """企业微信机器人 webhook 通知（markdown）。

    依赖 env `WECOM_WEBHOOK_URL`（形如 https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx）。
    """
    url = os.getenv("WECOM_WEBHOOK_URL", "")
    if not url:
        return False
    try:
        payload = json.dumps(
            {"msgtype": "markdown", "markdown": {"content": f"**{title}**\n{message}"}},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="ignore")
            return json.loads(body).get("errcode") == 0
    except Exception:
        return False


def notify_brief(title: str, message: str) -> str:
    """每日简报通道链：飞书 → 企业微信 → Telegram → 桌面通知 → stderr 打印。

    返回实际使用的通道名（feishu / wecom / telegram / desktop / log）。
    """
    if notify_feishu(title, message):
        return "feishu"
    if notify_wecom(title, message):
        return "wecom"
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    user_id = os.getenv("TELEGRAM_USER_ID")
    if token and user_id and notify_telegram(title, message):
        return "telegram"
    if notify(title, message):
        return "desktop"
    _safe_print(f"[BRIEF] {title}: {message}")
    return "log"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python notification.py <title> <message> [--error]")
        sys.exit(1)

    title = sys.argv[1]
    message = sys.argv[2]
    is_error = "--error" in sys.argv

    if is_error:
        notify_error(title, message)
    else:
        notify(title, message)
