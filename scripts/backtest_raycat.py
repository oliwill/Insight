"""
回测 raycat.substack.com 笔记中提到的股票推荐

从 Materials 目录中提取 raycat.substack.com 相关的笔记，
获取每个笔记中提到的股票代码和发布日期，
计算从发布日期到现在的收益率。
"""
import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.manager import DataManager
from memory.manager import MemoryManager


# 从笔记中提取的股票和发布日期
# 格式: (股票代码, 发布日期, 笔记标题/描述)
RAYCAT_STOCKS = [
    # 2026-04-21 (算一算AI资本的回报率)
    ("MSFT", "2026-04-21", "算一算AI资本的回报率(上)"),
    ("GOOG", "2026-04-21", "算一算AI资本的回报率(上)"),
    ("AMZN", "2026-04-21", "算一算AI资本的回报率(上)"),
    ("TSLA", "2026-04-21", "算一算AI资本的回报率(上)"),

    # 2026-04-23 (两年前无人问津，这只电信股好运快来了)
    ("LUMN", "2026-04-23", "两年前无人问津，这只电信股好运快来了"),

    # 2026-04-26 (AI一枝独秀，两只你从未听说过的基建股)
    ("HWM", "2026-04-26", "AI一枝独秀，两只你从未听说过的基建股 - Howmet Aerospace"),
    ("DY", "2026-04-26", "AI一枝独秀，两只你从未听说过的基建股 - Dycom Industries"),
    # 也提到但非重点: CHTR, CMCSA, INTC, AMD, ARM

    # 2026-04-26 (布局轨道数据中心)
    ("RKLB", "2026-05-06", "布局轨道数据中心 - Rocket Lab"),
    ("PL", "2026-05-06", "布局轨道数据中心 - Planet Labs"),
    ("LMT", "2026-05-06", "布局轨道数据中心 - 洛马"),
    ("NOC", "2026-05-06", "布局轨道数据中心 - 诺格"),
    ("LHX", "2026-05-06", "布局轨道数据中心 - L3Harris"),
    ("LDOS", "2026-05-06", "布局轨道数据中心 - Leidos"),
    ("RDW", "2026-05-06", "布局轨道数据中心 - Redwire"),
    ("BKSY", "2026-05-06", "布局轨道数据中心 - BlackSky"),
    ("SPIR", "2026-05-06", "布局轨道数据中心 - Spire"),

    # 2026-04-27 (英特尔：25年的等待，一个季度的翻身)
    ("INTC", "2026-04-27", "英特尔：25年的等待，一个季度的翻身"),
    ("FIX", "2026-04-27", "英特尔 - Comfort Systems USA"),
    ("MXL", "2026-04-27", "英特尔 - MaxLinear"),
    # 也提到: AVGO, MRVL, MU, STX, WDC, SNDK

    # 2026-05-01 (第二阶段扩张获证实)
    ("MSFT", "2026-05-01", "第二阶段扩张获证实 - 微软"),
    ("GOOG", "2026-05-01", "第二阶段扩张获证实 - Alphabet"),
    ("AMZN", "2026-05-01", "第二阶段扩张获证实 - 亚马逊"),
    ("META", "2026-05-01", "第二阶段扩张获证实 - Meta"),
    ("KLAC", "2026-05-01", "第二阶段扩张获证实 - KLA"),
    ("QCOM", "2026-05-01", "第二阶段扩张获证实 - 高通"),
    ("CAT", "2026-05-01", "第二阶段扩张获证实 - 卡特彼勒"),

    # 2026-05-07 (RSI极度拉伸，等待5-8%回调)
    ("AMD", "2026-05-07", "RSI极度拉伸 - AMD"),
    ("ANET", "2026-05-07", "RSI极度拉伸 - Arista Networks"),
    ("LEU", "2026-05-07", "RSI极度拉伸 - Centrus"),
    ("JOBY", "2026-05-07", "RSI极度拉伸 - Joby"),
    ("TEM", "2026-05-07", "RSI极度拉伸 - Tempus AI"),
    ("UBER", "2026-05-07", "RSI极度拉伸 - Uber"),
    ("LITE", "2026-05-07", "RSI极度拉伸 - Lumentum"),
    ("AVGO", "2026-05-07", "RSI极度拉伸 - 博通"),
    ("MRVL", "2026-05-07", "RSI极度拉伸 - Marvell"),
    ("FN", "2026-05-07", "RSI极度拉伸 - Fabrinet"),
    ("AAOI", "2026-05-07", "RSI极度拉伸 - Applied Optoelectronics"),
    ("CRDO", "2026-05-07", "RSI极度拉伸 - Credo Technologies"),

    # 2026-05-08 (IONQ笔记中提到的股票)
    ("COHR", "2026-05-08", "IONQ笔记 - Coherent"),
    ("DASH", "2026-05-08", "IONQ笔记 - DoorDash"),
    ("IONQ", "2026-05-08", "IONQ：有机会重演英伟达传奇？"),
    ("AMLX", "2026-05-08", "这家生物科技股有近期突破潜能 - Amylyx"),

    # 2026-05-12 (戳破AI泡沫的真风险)
    ("FN", "2026-05-12", "戳破AI泡沫的真风险 - Fabrinet"),

    # 2026-05-13 (量子计算悖论)
    ("QBTS", "2026-05-13", "量子计算悖论 - D-Wave Quantum"),
    ("RGTI", "2026-05-13", "量子计算悖论 - Rigetti Computing"),
    ("IBM", "2026-05-13", "量子计算悖论 - IBM"),
    # 也提到: GOOG, MSFT, HON, AMZN

    # 2026-05-13 (一次预期中、且未完成的回调)
    ("ASTS", "2026-05-13", "一次预期中、且未完成的回调 - ASTS"),
    ("TDY", "2026-05-13", "一次预期中、且未完成的回调 - Teledyne"),

    # 2026-05-18 (季报在即，英伟达还有机会吗？)
    ("NVDA", "2026-05-18", "季报在即，英伟达还有机会吗？"),
]


class RaycatBacktester:
    """raycat.substack.com 股票推荐回测器"""

    def __init__(self):
        self.dm = DataManager()
        self.mm = MemoryManager()
        self.current_date = datetime.now().strftime("%Y-%m-%d")

    def normalize_ticker(self, ticker: str) -> str:
        """标准化股票代码"""
        ticker = ticker.upper()
        if not "." in ticker and len(ticker) <= 5:
            # 默认为美股
            return f"{ticker}.US"
        return ticker

    def get_stock_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            # 计算需要的天数
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end_dt - start_dt).days + 30  # 多取30天确保数据完整
            period = f"{days}d"

            df = self.dm.get_historical_data(ticker, period)
            if df is None or df.empty:
                return None

            # 标准化列名
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]

            # 处理日期
            if "date" in df.columns:
                s = pd.to_datetime(df["date"])
                if s.dt.tz is not None:
                    df["date"] = s.dt.tz_convert(None)
                else:
                    df["date"] = s.dt.tz_localize(None)

            return df
        except Exception as e:
            print(f"获取 {ticker} 数据失败: {e}")
            return None

    def backtest_stock(self, ticker: str, publish_date: str, note_title: str) -> Dict:
        """回测单个股票"""
        normalized_ticker = self.normalize_ticker(ticker)

        # 获取数据
        df = self.get_stock_data(normalized_ticker, publish_date, self.current_date)
        if df is None:
            return {
                "ticker": ticker,
                "publish_date": publish_date,
                "note_title": note_title,
                "status": "NO_DATA",
                "error": "无法获取历史数据"
            }

        # 转换日期格式
        publish_dt = datetime.strptime(publish_date, "%Y-%m-%d").date()

        # 找到发布日期后的第一个交易日
        df = df[df["date"].dt.date >= publish_dt]
        if df.empty:
            return {
                "ticker": ticker,
                "publish_date": publish_date,
                "note_title": note_title,
                "status": "NO_DATA",
                "error": "发布日期后无数据"
            }

        # 入场价（发布后第一个收盘价）
        entry_price = float(df.iloc[0]["close"])
        entry_date = df.iloc[0]["date"].strftime("%Y-%m-%d")

        # 当前价格（最近一天）
        current_price = float(df.iloc[-1]["close"])
        current_date = df.iloc[-1]["date"].strftime("%Y-%m-%d")

        # 计算收益率
        return_pct = (current_price / entry_price - 1) * 100

        # 计算期间最高价和最低价
        max_price = float(df["close"].max())
        min_price = float(df["close"].min())
        max_return_pct = (max_price / entry_price - 1) * 100
        max_drawdown_pct = (min_price / entry_price - 1) * 100

        # 持有天数
        holding_days = (df.iloc[-1]["date"] - df.iloc[0]["date"]).days

        return {
            "ticker": ticker,
            "publish_date": publish_date,
            "note_title": note_title,
            "status": "SUCCESS",
            "entry_price": entry_price,
            "entry_date": entry_date,
            "current_price": current_price,
            "current_date": current_date,
            "return_pct": return_pct,
            "max_return_pct": max_return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "holding_days": holding_days,
        }

    def run_backtest(self) -> Tuple[List[Dict], pd.DataFrame]:
        """运行所有回测"""
        results = []

        print(f"开始回测 {len(RAYCAT_STOCKS)} 条股票推荐...")
        print("-" * 80)

        for ticker, publish_date, note_title in RAYCAT_STOCKS:
            print(f"回测 {ticker} ({publish_date})...", end=" ")
            result = self.backtest_stock(ticker, publish_date, note_title)
            results.append(result)

            if result["status"] == "SUCCESS":
                print(f"[OK] 收益: {result['return_pct']:+.2f}%")
            else:
                print(f"[FAIL] {result.get('error', 'Unknown error')}")

        # 转换为 DataFrame 以便分析
        df = pd.DataFrame([r for r in results if r["status"] == "SUCCESS"])

        return results, df

    def generate_report(self, results: List[Dict], df: pd.DataFrame) -> str:
        """生成回测报告"""
        lines = []
        lines.append("# raycat.substack.com 股票推荐回测报告")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**当前日期**: {self.current_date}")
        lines.append("")

        # 总体统计
        success_count = len([r for r in results if r["status"] == "SUCCESS"])
        total_count = len(results)

        if not df.empty:
            win_count = len(df[df["return_pct"] > 0])
            loss_count = len(df[df["return_pct"] <= 0])
            win_rate = win_count / len(df) * 100
            avg_return = df["return_pct"].mean()
            median_return = df["return_pct"].median()
            best_return = df["return_pct"].max()
            worst_return = df["return_pct"].min()
            avg_holding_days = df["holding_days"].mean()

            lines.append("## 总体统计")
            lines.append("")
            lines.append(f"- **成功获取数据**: {success_count}/{total_count}")
            lines.append(f"- **盈利次数**: {win_count}")
            lines.append(f"- **亏损次数**: {loss_count}")
            lines.append(f"- **胜率**: {win_rate:.1f}%")
            lines.append(f"- **平均收益**: {avg_return:+.2f}%")
            lines.append(f"- **中位数收益**: {median_return:+.2f}%")
            lines.append(f"- **最佳收益**: {best_return:+.2f}%")
            lines.append(f"- **最差收益**: {worst_return:+.2f}%")
            lines.append(f"- **平均持有天数**: {avg_holding_days:.1f} 天")
            lines.append("")

        # 收益分布
        if not df.empty:
            lines.append("## 收益分布")
            lines.append("")

            # 按收益区间统计
            bins = [-float('inf'), -20, -10, 0, 10, 20, float('inf')]
            labels = ["<-20%", "-20%~-10%", "-10%~0%", "0%~10%", "10%~20%", ">20%"]
            df["收益区间"] = pd.cut(df["return_pct"], bins=bins, labels=labels)
            dist = df["收益区间"].value_counts().sort_index()

            for label, count in dist.items():
                pct = count / len(df) * 100
                lines.append(f"- **{label}**: {count} 只 ({pct:.1f}%)")
            lines.append("")

        # TOP 10 表现最好
        if not df.empty:
            lines.append("## TOP 10 表现最好")
            lines.append("")
            lines.append("| 排名 | 股票代码 | 发布日期 | 入场价 | 当前价 | 收益率 | 最高收益率 | 最大回撤 | 持有天数 |")
            lines.append("|------|---------|---------|--------|--------|--------|-----------|---------|---------|")

            top10 = df.nlargest(10, "return_pct")
            for i, (_, row) in enumerate(top10.iterrows(), 1):
                lines.append(
                    f"| {i} | {row['ticker']} | {row['publish_date']} | "
                    f"{row['entry_price']:.2f} | {row['current_price']:.2f} | "
                    f"{row['return_pct']:+.2f}% | {row['max_return_pct']:+.2f}% | "
                    f"{row['max_drawdown_pct']:+.2f}% | {row['holding_days']} |"
                )
            lines.append("")

        # TOP 10 表现最差
        if len(df) >= 10:
            lines.append("## TOP 10 表现最差")
            lines.append("")
            lines.append("| 排名 | 股票代码 | 发布日期 | 入场价 | 当前价 | 收益率 | 最高收益率 | 最大回撤 | 持有天数 |")
            lines.append("|------|---------|---------|--------|--------|--------|-----------|---------|---------|")

            bottom10 = df.nsmallest(10, "return_pct")
            for i, (_, row) in enumerate(bottom10.iterrows(), 1):
                lines.append(
                    f"| {i} | {row['ticker']} | {row['publish_date']} | "
                    f"{row['entry_price']:.2f} | {row['current_price']:.2f} | "
                    f"{row['return_pct']:+.2f}% | {row['max_return_pct']:+.2f}% | "
                    f"{row['max_drawdown_pct']:+.2f}% | {row['holding_days']} |"
                )
            lines.append("")

        # 按股票汇总
        if not df.empty:
            lines.append("## 按股票汇总（多次推荐的股票）")
            lines.append("")

            # 按股票代码分组
            stock_summary = df.groupby("ticker").agg({
                "return_pct": ["count", "mean", "min", "max"],
                "holding_days": "mean"
            }).round(2)
            stock_summary.columns = ["推荐次数", "平均收益%", "最小收益%", "最大收益%", "平均持有天数"]

            # 只显示推荐次数 >= 2 的股票
            multi_recs = stock_summary[stock_summary["推荐次数"] >= 2].sort_values("平均收益%", ascending=False)

            if not multi_recs.empty:
                lines.append("| 股票代码 | 推荐次数 | 平均收益% | 最小收益% | 最大收益% | 平均持有天数 |")
                lines.append("|---------|---------|---------|---------|---------|-------------|")
                for ticker, row in multi_recs.iterrows():
                    lines.append(
                        f"| {ticker} | {int(row['推荐次数'])} | {row['平均收益%']:+.2f}% | "
                        f"{row['最小收益%']:+.2f}% | {row['最大收益%']:+.2f}% | {row['平均持有天数']:.1f} |"
                    )
            else:
                lines.append("*所有股票只被推荐了一次*")
            lines.append("")

        # 详细列表
        lines.append("## 详细回测结果")
        lines.append("")

        # 按发布日期排序
        df_sorted = df.sort_values("publish_date", ascending=False)

        lines.append("| 股票代码 | 发布日期 | 笔记标题 | 入场价 | 当前价 | 收益率 | 最高收益率 | 最大回撤 | 持有天数 |")
        lines.append("|---------|---------|---------|--------|--------|--------|-----------|---------|---------|")

        for _, row in df_sorted.iterrows():
            title_short = row["note_title"][:30] if len(row["note_title"]) > 30 else row["note_title"]
            lines.append(
                f"| {row['ticker']} | {row['publish_date']} | {title_short} | "
                f"{row['entry_price']:.2f} | {row['current_price']:.2f} | "
                f"{row['return_pct']:+.2f}% | {row['max_return_pct']:+.2f}% | "
                f"{row['max_drawdown_pct']:+.2f}% | {row['holding_days']} |"
            )
        lines.append("")

        # 获取数据失败的股票
        failed = [r for r in results if r["status"] != "SUCCESS"]
        if failed:
            lines.append("## 获取数据失败")
            lines.append("")
            for r in failed:
                lines.append(f"- {r['ticker']} ({r['publish_date']}): {r.get('error', 'Unknown error')}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*本报告由 trader-obsidian 系统自动生成*")

        return "\n".join(lines)

    def write_report_to_obsidian(self, report: str) -> str:
        """将回测报告写入 Obsidian"""
        from config import Config
        config = Config()
        wiki_dir = config.get_wiki_dir()

        # 创建回测报告文件
        report_file = wiki_dir / "raycat_backtest_report.md"

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        return str(report_file)


def main(argv: List[str] = None):
    """主函数"""
    parser = argparse.ArgumentParser(description="raycat.substack.com 股票推荐回测")
    parser.add_argument("--report", action="store_true", help="写入 Obsidian 报告（默认开启）")
    parser.parse_args(argv)

    print("=" * 80)
    print("raycat.substack.com 股票推荐回测")
    print("=" * 80)
    print()

    backtester = RaycatBacktester()
    results, df = backtester.run_backtest()

    print()
    print("=" * 80)
    print("回测完成！")
    print("=" * 80)

    if not df.empty:
        print()
        print("【总体统计】")
        print(f"  成功获取数据: {len(df)}/{len(results)}")
        print(f"  胜率: {len(df[df['return_pct'] > 0]) / len(df) * 100:.1f}%")
        print(f"  平均收益: {df['return_pct'].mean():+.2f}%")
        print(f"  最佳: {df['return_pct'].max():+.2f}%")
        print(f"  最差: {df['return_pct'].min():+.2f}%")

    # 生成报告
    print()
    print("生成报告...")
    report = backtester.generate_report(results, df)

    # 写入 Obsidian
    report_path = backtester.write_report_to_obsidian(report)
    print(f"报告已写入: {report_path}")

    return results, df, report


if __name__ == "__main__":
    main()
