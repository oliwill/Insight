"""用户级股票分析服务

复刻 scripts/analyze_stock.py 的确定性分析流程（fetch → moat → chart →
evidence → score → timing → comparison → report → quality），全部路径基于
用户 vault 目录；LLM 叙事增强只写入 analysis_records.llm_summary，
不污染 wiki 与确定性评分路径。

入口：run_analysis(symbol, user_id) -> dict
（由 web/tasks.py 任务执行器调用；异常由调用方兜底标记 failed）
"""
import json
import re
from pathlib import Path
from typing import Optional

from config import Config
from data.analysis_pipeline import generate_analysis
from data.manager import DataManager
from analyzer.report_generator import ReportGenerator
from analyzer.report_quality import ReportQualityEvaluator
from analyzer.research_score import ResearchScoreEngine
from analyzer.timing_engine import TimingEngine
from input.evidence import EvidenceExtractor
from memory.manager import MemoryManager
from web import db
from web.llm_client import enhance_summary


def user_vault_dir(user_id: int) -> Path:
    """用户 vault 根目录（含 Analysis/Materials/Charts 子目录）"""
    return Path(Config.USERS_DATA_DIR) / str(user_id) / "vault"


def _build_comparison_markdown(wiki_context: str, research_score: float, timing_state: str) -> str:
    """对比上次分析（蓝本：scripts/analyze_stock.py::_build_comparison_markdown）"""
    if not wiki_context:
        return "（首次分析，暂无历史对比）"

    new_matches = re.findall(r"Research:\s*([\d.]+)/100\s*\|\s*Timing:\s*([^|\n]+)", wiki_context)
    old_research = None
    old_timing = None
    if new_matches:
        old_research = float(new_matches[-1][0])
        old_timing = new_matches[-1][1].strip()
    else:
        old_matches = re.findall(r"评分:\s*([\d.]+)/100", wiki_context)
        if old_matches:
            old_research = float(old_matches[-1])

    if old_research is None and old_timing is None:
        return "有历史 wiki，但未找到可比较的结构化评分或 Timing 状态。"

    rows = ["| 项目 | 上次 | 本次 | 变化原因 |", "|---|---|---|---|"]
    if old_research is not None:
        delta = research_score - old_research
        if delta >= 5:
            reason = "Research Score 明显上调"
        elif delta <= -5:
            reason = "Research Score 明显下调"
        else:
            reason = "核心研究分未发生实质变化"
        rows.append(f"| Research Score | {old_research:.1f} | {research_score:.1f} | {reason} |")
    if old_timing:
        reason = "交易时机状态变化" if old_timing != timing_state else "交易时机状态未变"
        rows.append(f"| Timing State | {old_timing} | {timing_state} | {reason} |")
    return "\n".join(rows)


def _generate_wyckoff_chart(stock_code: str, df, market_data: dict, charts_dir: Path) -> Optional[str]:
    """生成 Wyckoff 图表到 charts_dir，返回文件路径；失败返回 None（静默跳过）"""
    try:
        from analyzer.wyckoff import WyckoffAnalyzer
        from analyzer.wyckoff_chart import WyckoffChartRenderer

        wa = WyckoffAnalyzer()
        wyckoff_result = wa.analyze(df.reset_index(), market_data.get("fundamentals", {}) or {})
        structure = wyckoff_result.details.get("structure")
        if not structure or not structure.phases:
            return None

        charts_dir.mkdir(parents=True, exist_ok=True)
        safe_code = stock_code.replace(".", "_")
        output_path = charts_dir / f"{safe_code}_wyckoff.png"
        renderer = WyckoffChartRenderer()
        renderer.render(
            df=df,
            structure=structure,
            output_path=str(output_path),
            title=f"{stock_code} 威科夫分析",
        )
        return str(output_path)
    except (ImportError, AttributeError, TypeError, ValueError, OSError):
        return None


def run_analysis(symbol: str, user_id: int) -> dict:
    """对 symbol 执行完整用户级分析，写回用户 vault + 保存 analysis_record。

    Returns:
        {"record_id", "symbol", "score", "timing_state", "quality_score", "llm_enhanced"}
    """
    vault = user_vault_dir(user_id)
    mm = MemoryManager(base_dir=vault)

    # 1. 全量数据（wiki 上下文基于用户 vault）
    market_data = generate_analysis(symbol, wiki_base=vault)

    # 2. 护城河增强（蓝本 analyze_stock.py；失败静默跳过）
    try:
        from analyzer.fundamental import FundamentalAnalyzer, build_moat_stress_test
        import pandas as pd

        fa = FundamentalAnalyzer()
        fund_result = fa.analyze(pd.DataFrame(), market_data.get("fundamentals", {}) or {})
        if "business" in fund_result.details:
            market_data.setdefault("fundamentals", {})["moat"] = fund_result.details["business"].get("moat")
            market_data["fundamentals"]["moat_indicators"] = fund_result.details["business"].get("moat_indicators", [])
        market_data["fundamentals"]["moat_stress_test"] = build_moat_stress_test(
            market_data.get("stock_info", {}) or {},
            market_data.get("fundamentals", {}) or {},
            market_data.get("peers", []) or [],
        )
    except Exception:
        pass

    stock_info = market_data.get("stock_info", {}) or {}
    analysis_code = stock_info.get("code") or symbol
    stock_name = stock_info.get("name") or symbol
    price = stock_info.get("price") or 0
    fundamentals = market_data.get("fundamentals", {}) or {}

    # 3. Wyckoff 图表（用户 Charts 目录）
    chart_path = None
    try:
        dm = DataManager()
        df = dm.get_historical_data(symbol, period="2y")
        if df is not None and len(df) > 100:
            chart_path = _generate_wyckoff_chart(analysis_code, df, market_data, vault / "Charts")
    except Exception:
        chart_path = None

    # 4-7. 证据 / 评分 / 时机 / 对比（全部基于用户 vault）
    extractor = EvidenceExtractor()
    materials = mm.get_materials(analysis_code)
    wiki_context = mm.get_stock_context(analysis_code)
    evidence = extractor.extract(wiki_context=wiki_context, materials=materials, inbox_items=[])
    evidence_markdown = extractor.to_markdown(evidence)

    research_engine = ResearchScoreEngine()
    research_score_obj = research_engine.score(market_data, evidence)
    research_score_markdown = research_engine.to_markdown(research_score_obj)

    timing_engine = TimingEngine()
    timing = timing_engine.analyze(
        market_data,
        research_score=research_score_obj.total_adjusted_score,
    )
    timing_markdown = timing_engine.to_markdown(timing)

    comparison_markdown = _build_comparison_markdown(
        wiki_context, research_score_obj.total_adjusted_score, timing.state
    )

    # 8. 统一报告（wiki_base=用户 vault，图表按用户目录解析）
    report_md = ReportGenerator.generate(
        analysis_code, market_data, research_score_obj, timing, evidence, wiki_base=vault
    )

    # 9. 质检
    quality = ReportQualityEvaluator().evaluate(report_md, market_data)
    quality_score = getattr(quality, "score", None)

    score = research_score_obj.total_adjusted_score
    target_mean = fundamentals.get("target_mean_price") or 0
    potential = (target_mean / price - 1) * 100 if price > 0 and target_mean > 0 else 0
    core_view = (
        f"Research {score:.1f}/100（{research_score_obj.verdict}），"
        f"Timing {timing.state}；分析师目标价 ${target_mean:.2f} vs 当前 ${price:.2f} "
        f"(潜在 {potential:+.1f}%)"
    )

    # 10. 写回用户 wiki（结构对齐 write_analysis_to_obsidian）
    mm.init_stock_wiki(analysis_code, stock_name)
    mm.update_evaluation_table(
        analysis_code,
        stock_name,
        dimension="综合",
        current_judgment=f"评分 {score}/100 - {core_view or '分析完成'}",
    )
    mm.update_cockpit_sections(
        analysis_code,
        evidence_markdown,
        research_score_markdown,
        timing_markdown,
        comparison_markdown,
    )
    mm.append_to_timeline(
        analysis_code,
        price=price,
        core_view=core_view,
        analysis_type="Web 分析",
        research_score=score,
        timing_state=timing.state,
        entry_trigger=timing.entry_triggers[0] if timing.entry_triggers else "",
    )
    mm.update_index(analysis_code, stock_name, score)

    # 11. LLM 叙事增强（失败降级，仅存 record 供展示）
    llm_summary = enhance_summary(analysis_code, stock_name, market_data, score, timing.state)
    llm_enhanced = llm_summary is not None

    # 12. 保存分析记录（追踪历史 + 报告全文展示）
    data_sources = json.dumps(market_data.get("_data_sources", {}), ensure_ascii=False, default=str)
    record_id = db.save_analysis_record(
        user_id=user_id,
        symbol=analysis_code,
        report_md=report_md,
        research_score=score,
        timing_state=timing.state,
        chart_path=chart_path,
        data_sources=data_sources,
        llm_enhanced=llm_enhanced,
        llm_summary=llm_summary,
    )

    return {
        "record_id": record_id,
        "symbol": analysis_code,
        "score": score,
        "timing_state": timing.state,
        "quality_score": quality_score,
        "llm_enhanced": llm_enhanced,
    }
