"""LLM 报告增强客户端 —— DeepSeek 兼容 OpenAI Chat Completions API

只做报告叙事增强（核心观点 / 关键判断 / 主要风险），不接触确定性评分路径。
未配置 LLM_API_KEY 或调用失败时静默返回 None，由调用方降级为确定性文本。
"""

import json
from typing import Optional

import requests

from config import Config

_SYSTEM_PROMPT = (
    "你是资深股票分析师助手。基于给定的结构化分析数据，生成一段简洁的"
    "中文投资解读，包含：核心观点（一句话）、关键判断（2-3 条）、主要风险（2-3 条）。"
    "只陈述数据支持的事实，不要编造数字，不要给出买卖指令。"
    "输出 Markdown，格式：\n"
    "### 核心观点\n...\n\n### 关键判断\n- ...\n\n### 主要风险\n- ..."
)


def llm_available() -> bool:
    return bool(Config.LLM_API_KEY and Config.LLM_BASE_URL)


def complete(
    system: str,
    user: str,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> Optional[str]:
    """OpenAI 兼容 Chat Completions 通用调用；未配置或失败返回 None。

    供 `enhance_summary`（报告叙事增强）与 `input/brief_summarizer`（每日简报）
    等上层复用，避免各自重复实现 HTTP 细节。
    """
    if not llm_available():
        return None
    payload = {
        "model": Config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(
            f"{Config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {Config.LLM_API_KEY}"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return content.strip() if content else None
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def enhance_summary(
    stock_code: str,
    stock_name: str,
    market_data: dict,
    research_score: Optional[float],
    timing_state: str,
) -> Optional[str]:
    """生成 LLM 叙事段 Markdown；未配置或失败返回 None（调用方静默降级）"""
    if not llm_available():
        return None

    prompt = _build_prompt(
        stock_code, stock_name, market_data, research_score, timing_state
    )
    return complete(_SYSTEM_PROMPT, prompt)


def _build_prompt(
    stock_code: str,
    stock_name: str,
    market_data: dict,
    research_score: Optional[float],
    timing_state: str,
) -> str:
    stock_info = market_data.get("stock_info", {}) or {}
    fundamentals = market_data.get("fundamentals", {}) or {}
    technicals = market_data.get("technicals", {}) or {}
    wyckoff = market_data.get("wyckoff", {}) or {}
    earnings = market_data.get("earnings", {}) or {}

    compact = {
        "代码": stock_code,
        "名称": stock_name or stock_info.get("name", ""),
        "价格": stock_info.get("price"),
        "涨跌幅%": stock_info.get("change_pct"),
        "行业": stock_info.get("industry", ""),
        "板块": stock_info.get("sector", ""),
        "Research评分": round(research_score, 1)
        if research_score is not None
        else None,
        "交易时机": timing_state,
        "远期PE": fundamentals.get("pe_forward"),
        "目标均价": fundamentals.get("target_mean_price"),
        "分析师评级": fundamentals.get("analyst_rating", ""),
        "护城河": fundamentals.get("moat", ""),
        "RSI": technicals.get("rsi"),
        "MA20": technicals.get("ma20"),
        "MA60": technicals.get("ma60"),
        "Wyckoff阶段": wyckoff.get("phase"),
        "支撑位": wyckoff.get("support"),
        "阻力位": wyckoff.get("resistance"),
        "下次财报": earnings.get("next_earnings_date", ""),
    }
    return json.dumps(compact, ensure_ascii=False, indent=2, default=str)
