"""
CLI 入口 + workflow dispatch - Serenity 产业链扫描。
"""
import sys
import json as json_lib
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.serenity.chain_analyzer import ChainAnalyzer
from data.serenity.bottleneck_scorer import BottleneckScorer
from data.serenity.report_builder import ReportBuilder
from data.serenity.integrator import SerenityIntegrator
from memory.manager import MemoryManager


def main():
    parser = argparse.ArgumentParser(description="Serenity 产业链扫描：从热点出发，拆产业链、找瓶颈、筛候选公司。")
    parser.add_argument("topic", help="热点关键词，如 AI 半导体、机器人减速器")
    parser.add_argument("--depth", choices=["normal", "deep"], default="normal", help="normal 纯 LLM 知识；deep 联网查公告（暂未实现）")
    parser.add_argument("--export-md", action="store_true", help="不写入，只打印 Markdown 到 stdout")
    parser.add_argument("--dry-run", action="store_true", help="不写入，只打印到 stdout")
    parser.add_argument("--json", action="store_true", dest="json_flag", help="配合 --dry-run 输出 JSON")
    parser.add_argument("--stock-code", default=None, help="写入到指定股票代码的 Obsidian 研究笔记（默认用 topic）")
    args = parser.parse_args()

    analyzer = ChainAnalyzer()
    result = analyzer.analyze(args.topic, args.depth)

    scorer = BottleneckScorer()
    scorer.score_layers(result.get("layers", []))
    scorer.rank_candidates(result.get("candidates", []))

    builder = ReportBuilder()
    markdown = builder.build(result)

    if args.dry_run:
        if args.json_flag:
            print(json_lib.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(markdown)
        return

    if args.export_md:
        print(markdown)
        return

    stock_code = args.stock_code or args.topic
    mm = MemoryManager()

    # 使用 SerenityIntegrator 将产业链分析融入现有分析框架
    integrator = SerenityIntegrator()
    updated_sections = integrator.integrate(stock_code, result, mm)

    print(f"Serenity 产业链扫描已融入 Obsidian: {stock_code}")
    print(f"已更新 sections: {', '.join(updated_sections)}")


if __name__ == "__main__":
    main()
