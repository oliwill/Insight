"""每日简报 LLM 摘要 —— 复用 `web/llm_client.complete()`。

把「近 7 天最关注的 N 只股票」的近期分析 + 近期文章压成一份简短中文日报。
未配置 `LLM_API_KEY` 或调用失败时返回 None，由调用方降级为确定性模板。
"""

from __future__ import annotations

import json
from datetime import datetime

from web.llm_client import complete, llm_available

_BRIEF_SYSTEM_PROMPT = (
    "你是投资简报助手。基于给定的 N 只股票（每只含代码/名称、分析频次、Research 评分与"
    "verdict、Timing 状态、五维打分（行业/护城河/增长/估值/团队）、核心观点、相关文章"
    "标题+一句话概要、入场触发条件、失效警戒条件），生成一份简洁的中文每日关注简报。"
    "每只股票按固定结构：\n"
    "1. 标题行：名称（代码）｜近N天分析M次\n"
    "2. 评分：Research X/100（verdict）｜ Timing 状态\n"
    "3. 目标价：分析师目标价 vs 当前价（潜在 X%）（重点突出）\n"
    "4. 基本面：行业 x ｜ 护城河 x ｜ 增长 x ｜ 估值 x ｜ 团队 x\n"
    "5. 相关文章：标题 — 一句话概要（2-3 条）\n"
    "6. 操作：状态 ｜ 触发条件 ｜ 警戒线\n"
    "只用提供的数据，缺的字段写「—」；不编造数字；不给买卖指令。输出 Markdown。"
)

_STATE_LABEL = {"Ready": "可关注", "Wait": "观望", "Watch": "观察", "Avoid": "回避"}


def summarize_brief(stocks: list, lookback_days: int = 7) -> str | None:
    """生成每日简报正文；未配置 LLM 或失败返回 None（调用方降级为确定性模板）。"""
    if not llm_available():
        return None
    user_prompt = json.dumps(
        {"lookback_days": lookback_days, "stocks": stocks},
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    return complete(_BRIEF_SYSTEM_PROMPT, user_prompt, max_tokens=4000, temperature=0.4)


def deterministic_template(stocks: list, lookback_days: int = 7) -> str:
    """无 LLM 时的确定性兜底模板（详版，每股 8 行）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"📊 今日关注简报 · {today}（近{lookback_days}天分析频次 Top{len(stocks)}）"
    ]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, s in enumerate(stocks):
        code = s.get("code", "?")
        name = s.get("name", "") or code
        count = s.get("count", 0)
        research = s.get("research") or "N/A"
        verdict = s.get("verdict") or "—"
        timing = s.get("timing") or "N/A"
        target = s.get("target") or ""
        dims = s.get("dims") or {}
        dims_str = " ｜ ".join(f"{k} {v}" for k, v in dims.items()) or "—"
        entry = s.get("entry") or "—"
        invalidation = s.get("invalidation") or "—"
        state_label = _STATE_LABEL.get(timing, "")

        marker = emojis[i] if i < len(emojis) else f"{i + 1}."
        lines.append(f"{marker} {name}（{code}）｜近{lookback_days}天分析 {count} 次")
        lines.append(f"   评分：Research {research}/100（{verdict}）｜ Timing {timing}")
        if target:
            lines.append(f"   🎯 目标价：{target}")
        lines.append(f"   基本面：{dims_str}")
        materials = s.get("materials") or []
        if materials:
            lines.append("   相关文章：")
            for m in materials[:3]:
                title = m.get("title") or "无标题"
                summary = (m.get("summary") or "").strip()
                suffix = f"— {summary}" if summary else ""
                lines.append(f"     ·《{title}》{suffix}")
        op_state = f"{timing} {state_label}".strip()
        lines.append(f"   操作：{op_state} ｜ 触发：{entry} ｜ 警戒：{invalidation}")
        lines.append("")
    lines.append("⚠️ 仅供研究参考，不构成投资建议")
    return "\n".join(lines)
