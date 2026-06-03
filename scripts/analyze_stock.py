#!/usr/bin/env python3
"""
股票分析脚本 - 将分析结果写入 Obsidian

用法: python scripts/analyze_stock.py INVZ

整合了 report_generator.py，统一生成格式化报告
"""
import sys
import os
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from run_analysis import write_analysis_to_obsidian
from data.analysis_pipeline import generate_analysis
from analyzer.report_generator import ReportGenerator
from analyzer.research_score import ResearchScoreEngine
from analyzer.timing_engine import TimingEngine
from data.manager import DataManager
from input.evidence import EvidenceExtractor
from inbox_scanner import get_related_materials
from memory.manager import MemoryManager


def _build_comparison_markdown(wiki_context: str, research_score: float, timing_state: str) -> str:
    """Build a compact comparison against the previous wiki timeline when available."""
    if not wiki_context:
        return "（首次分析，暂无历史对比）"

    import re
    old_research = None
    old_timing = None

    new_matches = re.findall(r"Research:\s*([\d.]+)/100\s*\|\s*Timing:\s*([^|\n]+)", wiki_context)
    if new_matches:
        old_research = float(new_matches[-1][0])
        old_timing = new_matches[-1][1].strip()
    else:
        old_matches = re.findall(r"评分:\s*([\d.]+)/100", wiki_context)
        if old_matches:
            old_research = float(old_matches[-1])

    if old_research is None and old_timing is None:
        return "有历史 wiki，但未找到可比较的结构化评分或 Timing 状态。"

    rows = [
        "| 项目 | 上次 | 本次 | 变化原因 |",
        "|---|---|---|---|",
    ]
    if old_research is not None:
        delta = research_score - old_research
        if abs(delta) >= 5:
            reason = "Research Score 明显上调" if delta > 0 else "Research Score 明显下调"
        else:
            reason = "核心研究分未发生实质变化"
        rows.append(f"| Research Score | {old_research:.1f} | {research_score:.1f} | {reason} |")
    if old_timing:
        reason = "交易时机状态变化" if old_timing != timing_state else "交易时机状态未变"
        rows.append(f"| Timing State | {old_timing} | {timing_state} | {reason} |")
    return "\n".join(rows)



def generate_wyckoff_chart(stock_code: str, df, market_data: dict) -> None:
    """
    生成威科夫图表并保存到 Obsidian Charts 目录

    Args:
        stock_code: 股票代码
        df: K线数据 DataFrame
        market_data: 市场数据字典
    """
    try:
        from analyzer.wyckoff import WyckoffAnalyzer
        from analyzer.wyckoff_chart import WyckoffChartRenderer

        # 运行威科夫分析获取完整结构
        wa = WyckoffAnalyzer()
        fund_data = market_data.get('fundamentals', {})
        wyckoff_result = wa.analyze(df.reset_index(), fund_data)

        # 获取完整结构
        structure = wyckoff_result.details.get('structure')
        if not structure or not structure.phases:
            print("威科夫结构不完整，跳过图表生成")
            return

        # 确定输出路径
        from dotenv import load_dotenv
        load_dotenv()

        wiki_base = os.getenv('WIKI_BASE_DIR')
        if not wiki_base:
            print("未设置 WIKI_BASE_DIR，跳过图表生成")
            return

        charts_dir = Path(wiki_base) / "Charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名（将 . 替换为 _）
        safe_code = stock_code.replace('.', '_')
        output_path = charts_dir / f"{safe_code}_wyckoff.png"

        # 绘制图表
        renderer = WyckoffChartRenderer()
        renderer.render(
            df=df,
            structure=structure,
            output_path=str(output_path),
            title=f"{stock_code} 威科夫分析"
        )

        print(f"威科夫图表已生成: {output_path}")

    except ImportError as e:
        print(f"威科夫图表模块不可用: {e}")
    except Exception as e:
        print(f"生成威科夫图表失败: {e}")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--dashboard":
        print("Use `python scripts/update_dashboard.py` or `python run_analysis.py --dashboard` to update the dashboard.")
        sys.exit(2)

    parser = argparse.ArgumentParser(description="Analyze one stock and write the report to Obsidian")
    parser.add_argument("stock_code", help="Stock code, e.g. AAPL or 03986.HK")
    args = parser.parse_args()
    stock_code = args.stock_code

    # 获取分析数据
    market_data = generate_analysis(stock_code)

    # 运行基本面分析（补充护城河评分）
    try:
        from analyzer.fundamental import FundamentalAnalyzer
        import pandas as pd
        fa = FundamentalAnalyzer()
        fund_result = fa.analyze(
            pd.DataFrame(),
            market_data.get('fundamentals', {})
        )
        # 将护城河分析结果合并到 fundamentals
        if 'business' in fund_result.details:
            market_data['fundamentals']['moat'] = fund_result.details['business'].get('moat')
            market_data['fundamentals']['moat_indicators'] = fund_result.details['business'].get('moat_indicators', [])
    except Exception as e:
        print(f"护城河分析失败（跳过）: {e}")

    # 生成威科夫图表
    try:
        dm = DataManager()
        df = dm.get_historical_data(stock_code, period="2y")  # 获取 2 年数据用于威科夫分析
        if df is not None and len(df) > 100:  # 至少需要 100 天数据
            generate_wyckoff_chart(stock_code, df, market_data)
    except Exception as e:
        print(f"威科夫图表生成失败（跳过）: {e}")

    # 提取关键信息
    stock_info = market_data.get('stock_info', {})
    analysis_code = stock_info.get('code') or stock_code
    stock_name = stock_info.get('name', 'Unknown')
    price = stock_info.get('price') or 0
    fundamentals = market_data.get('fundamentals', {})
    earnings = market_data.get('earnings', {})
    liquidity = market_data.get('liquidity', {})
    options = market_data.get('options', {})
    peers = market_data.get('peers', [])
    web_search = market_data.get('web_search', {})

    # 生成 Cockpit 结构化输出：证据、Research Score、Timing State
    mm = MemoryManager()
    extractor = EvidenceExtractor()
    materials = mm.get_materials(analysis_code)
    inbox_items = get_related_materials(analysis_code)
    wiki_context = mm.get_stock_context(analysis_code)
    evidence = extractor.extract(
        wiki_context=wiki_context,
        materials=materials,
        inbox_items=inbox_items,
    )
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
    comparison_markdown = _build_comparison_markdown(wiki_context, research_score_obj.total_adjusted_score, timing.state)

    # 使用统一报告生成器
    analysis_text = ReportGenerator.generate(analysis_code, market_data, research_score_obj, timing, evidence)

    # 评分和核心观点
    score = research_score_obj.total_adjusted_score
    target_mean = fundamentals.get('target_mean_price') or 0
    potential = (target_mean / price - 1) * 100 if price > 0 and target_mean > 0 else 0

    core_view = (
        f"Research {score:.1f}/100（{research_score_obj.verdict}），"
        f"Timing {timing.state}；分析师目标价 ${target_mean:.2f} vs 当前 ${price:.2f} (潜在 {potential:+.1f}%)"
    )

    put_call_ratio = options.get('put_call_ratio')
    put_call_display = f"{put_call_ratio:.2f}" if put_call_ratio is not None else "N/A"

    # 信号
    signals = [
        f"Research {score:.1f}/100",
        f"Timing {timing.state}",
        f"潜在涨幅 {potential:+.1f}%",
        f"Put/Call {put_call_display}"
    ]

    # 写入 Obsidian
    write_analysis_to_obsidian(
        stock_code=analysis_code,
        stock_name=stock_name,
        analysis_text=analysis_text,
        score=score,
        signals=signals,
        core_view=core_view,
        price=price,
        earnings=earnings,
        liquidity=liquidity,
        options=options,
        peers=peers,
        web_search=web_search,
        evidence_markdown=evidence_markdown,
        research_score_markdown=research_score_markdown,
        timing_markdown=timing_markdown,
        comparison_markdown=comparison_markdown,
        research_score=score,
        timing_state=timing.state,
        entry_trigger=timing.entry_triggers[0] if timing.entry_triggers else "",
    )


if __name__ == '__main__':
    main()
