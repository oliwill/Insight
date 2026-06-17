import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.report_generator import ReportGenerator
from config import Config


def test_wyckoff_chart_link_uses_configured_charts_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "4_Trader/Analysis")
    charts_dir = tmp_path / "Charts"
    charts_dir.mkdir()
    (charts_dir / "01060_HK_wyckoff.png").write_bytes(b"fake image")

    markdown = ReportGenerator._format_wyckoff_chart("01060.HK")

    assert "../../Charts/01060_HK_wyckoff.png" in markdown


def test_wyckoff_chart_link_is_omitted_when_chart_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "4_Trader/Analysis")

    markdown = ReportGenerator._format_wyckoff_chart("01060.HK")

    assert markdown == ""


def test_report_title_uses_code_then_stock_name():
    markdown = ReportGenerator.generate(
        "AAPL.US",
        {
            "_generated_at": "2026-06-02T14:42:31.574199",
            "stock_info": {
                "code": "AAPL.US",
                "name": "Apple Inc.",
                "price": 190.0,
            }
        },
    )

    assert markdown.startswith("# AAPL.US Apple Inc.\n\n**数据时间**：2026-06-02 14:42")


def test_report_omits_empty_optional_modules():
    markdown = ReportGenerator.generate(
        "EMPTY.US",
        {
            "stock_info": {
                "code": "EMPTY.US",
                "name": "Empty Co",
                "price": 10.0,
            },
            "fundamentals": {},
            "technicals": {},
            "liquidity": {},
            "options": {},
            "web_search": {},
        },
    )

    assert "## 三、基本面与估值" not in markdown
    assert "## 八、市场情绪" not in markdown
    assert "## 五、市场结构" not in markdown
    assert "## 数据缺口" in markdown


def test_report_summary_prioritizes_interpretation_before_details():
    markdown = ReportGenerator.generate(
        "MRVL.US",
        {
            "_generated_at": "2026-06-02T14:42:31.574199",
            "stock_info": {
                "code": "MRVL.US",
                "name": "Marvell Technology",
                "price": 219.43,
                "change_pct": 7.04,
            },
            "fundamentals": {
                "pe_forward": 35.9,
                "ps": 22.0,
                "revenue_growth": 0.276,
                "gross_margin": 0.515,
                "free_cashflow": 2_269_700_096,
                "target_mean_price": 222.55,
            },
            "technicals": {
                "trend_short": "BULLISH",
                "trend_mid": "BULLISH",
                "rsi_14": 72.56,
                "pct_from_high": -2.54,
            },
            "liquidity": {"daily_dollar_volume": 6_051_634_735.55},
            "options": {},
            "earnings": {},
            "web_search": {},
        },
    )

    assert "## 一、本次分析总结" in markdown
    assert "**一句话判断**" in markdown
    assert "### 关键判断" in markdown
    assert "趋势较强，但 RSI 72.6 已过热" in markdown
    assert markdown.index("**数据时间**") < markdown.index("## 一、本次分析总结")
    assert markdown.index("## 三、基本面与估值") < markdown.index("## 四、技术结构与五维分析")
    assert markdown.index("## 六、操作建议") < markdown.index("## 七、催化与风险")


def test_chart_gallery_includes_extra_chart(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "4_Trader/Analysis")
    charts_dir = tmp_path / "Charts"
    charts_dir.mkdir()
    chart_path = charts_dir / "AAPL_US_price.png"
    chart_path.write_bytes(b"fake image")

    markdown = ReportGenerator.generate(
        "AAPL.US",
        {
            "stock_info": {"code": "AAPL.US", "name": "Apple Inc.", "price": 190.0},
            "technicals": {"ma20": 180.0},
            "charts": [{"title": "价格走势", "path": chart_path}],
        },
    )

    assert "### 价格走势" in markdown
    assert "![价格走势](../../Charts/AAPL_US_price.png)" in markdown


def test_report_opens_with_desired_conclusion_sentence_after_data_time():
    markdown = ReportGenerator.generate(
        "MU.US",
        {
            "_generated_at": "2026-06-12T09:30:00",
            "stock_info": {
                "code": "MU.US",
                "name": "Micron Technology",
                "price": 120.0,
                "sector": "Technology",
                "industry": "Semiconductor Memory",
            },
            "fundamentals": {
                "pe_forward": 12.5,
                "pe_ttm": 15.2,
                "pb": 2.1,
                "target_mean_price": 145.0,
            },
            "technicals": {
                "support_20d": 110.0,
                "resistance_20d": 130.0,
            },
            "supply_chain": {
                "status": "available",
                "topic": "hbm",
                "position": "位于 HBM 产业链芯片/器件层。",
                "bottleneck_score": 6,
                "bottleneck_level": "中等瓶颈",
                "target_layer": {
                    "name": "芯片/器件（核心元件）",
                    "bottleneck_score": 6,
                    "bottleneck_level": "中等瓶颈",
                    "supply_demand": "tight",
                },
                "opportunities": ["AI GPU 对 HBM 需求增长"],
                "risks": ["存储周期波动"],
            },
        },
    )

    assert "MU.US Micron Technology" in markdown
    assert "Micron Technology 是一家" in markdown
    assert "当前股价 $120.00" in markdown
    assert "PE 12.50 倍" in markdown or "PE 15.20 倍" in markdown
    assert "PB 2.10 倍" in markdown
    assert "建议" in markdown
    assert markdown.index("**数据时间**") < markdown.index("## 一、本次分析总结")


def test_supply_chain_is_rendered_inside_fundamental_section_not_independent_section():
    markdown = ReportGenerator.generate(
        "MU.US",
        {
            "stock_info": {
                "code": "MU.US",
                "name": "Micron Technology",
                "price": 120.0,
                "sector": "Technology",
                "industry": "Semiconductor Memory",
            },
            "fundamentals": {
                "pe_forward": 12.5,
                "pb": 2.1,
                "gross_margin": 0.38,
            },
            "supply_chain": {
                "status": "available",
                "topic": "hbm",
                "position": "位于 HBM 产业链芯片/器件层。",
                "bottleneck_score": 6,
                "bottleneck_level": "中等瓶颈",
                "target_layer": {
                    "name": "芯片/器件（核心元件）",
                    "bottleneck_score": 6,
                    "bottleneck_level": "中等瓶颈",
                    "supply_demand": "tight",
                },
                "opportunities": ["AI GPU 对 HBM 需求增长"],
                "risks": ["存储周期波动"],
            },
        },
    )

    assert "## 三、基本面与估值" in markdown
    assert "### 产业链位置" in markdown
    assert "位于 HBM 产业链芯片/器件层" in markdown
    assert not any(line == "## 产业链位置" for line in markdown.splitlines())
    assert markdown.index("## 三、基本面与估值") < markdown.index("### 产业链位置")


def test_report_order_matches_company_fundamental_chain_technical_score_operation_flow():
    markdown = ReportGenerator.generate(
        "MU.US",
        {
            "stock_info": {
                "code": "MU.US",
                "name": "Micron Technology",
                "price": 120.0,
                "sector": "Technology",
                "industry": "Semiconductor Memory",
            },
            "fundamentals": {
                "pe_forward": 12.5,
                "pb": 2.1,
                "gross_margin": 0.38,
                "target_mean_price": 145.0,
            },
            "technicals": {
                "ma20": 118.0,
                "ma50": 110.0,
                "trend_short": "BULLISH",
                "trend_mid": "BULLISH",
                "rsi_14": 55.0,
                "support_20d": 110.0,
                "resistance_20d": 130.0,
            },
            "liquidity": {"daily_dollar_volume": 50_000_000},
            "supply_chain": {
                "status": "available",
                "topic": "hbm",
                "position": "位于 HBM 产业链芯片/器件层。",
                "target_layer": {
                    "name": "芯片/器件（核心元件）",
                    "bottleneck_score": 6,
                    "bottleneck_level": "中等瓶颈",
                    "supply_demand": "tight",
                },
                "opportunities": ["AI GPU 对 HBM 需求增长"],
                "risks": ["存储周期波动"],
            },
        },
    )

    expected_order = [
        "## 一、本次分析总结",
        "## 二、公司与证据概览",
        "## 三、基本面与估值",
        "### 产业链位置",
        "## 四、技术结构与五维分析",
        "## 五、市场结构",
        "## 六、操作建议",
    ]

    for earlier, later in zip(expected_order, expected_order[1:]):
        assert earlier in markdown
        assert later in markdown
        assert markdown.index(earlier) < markdown.index(later)


def test_supply_chain_only_does_not_hide_missing_core_fundamentals():
    markdown = ReportGenerator.generate(
        "CHAIN.US",
        {
            "stock_info": {
                "code": "CHAIN.US",
                "name": "Chain Only Co",
                "price": 12.0,
                "sector": "Technology",
                "industry": "Semiconductors",
            },
            "fundamentals": {
                "supply_chain": {
                    "status": "available",
                    "topic": "gpu",
                    "position": "位于 GPU 产业链设备层。",
                    "target_layer": {
                        "name": "设备（制造设备/测试设备）",
                        "bottleneck_score": 6,
                        "bottleneck_level": "中等瓶颈",
                        "supply_demand": "tight",
                    },
                }
            },
            "technicals": {},
            "liquidity": {},
            "options": {},
            "earnings": {},
            "web_search": {},
        },
    )

    assert "### 产业链位置" in markdown
    assert "## 数据缺口" in markdown
    assert "**基本面**" in markdown


def test_moat_stress_test_is_rendered_inside_fundamental_section_not_independent_section():
    markdown = ReportGenerator.generate(
        "MU.US",
        {
            "stock_info": {
                "code": "MU.US",
                "name": "Micron Technology",
                "price": 120.0,
                "sector": "Technology",
                "industry": "Semiconductor Memory",
                "business_summary": "Micron makes DRAM, NAND and HBM.",
            },
            "fundamentals": {
                "pe_forward": 12.5,
                "pb": 2.1,
                "gross_margin": 0.38,
                "moat_stress_test": {
                    "subject": {
                        "company": "Micron Technology",
                        "code": "MU.US",
                        "sector": "Technology",
                        "industry": "Semiconductor Memory",
                        "business_model": "产品公司",
                        "peer_count": 3,
                    },
                    "confirmed_facts": [
                        {"claim": "毛利率约 38.0%", "source": "gross_margin", "confidence": "confirmed"},
                    ],
                    "reasonable_inferences": [
                        {"claim": "毛利率显示存在一定定价权。", "basis": "gross_margin", "confidence": "inferred"},
                    ],
                    "assumptions_to_verify": [
                        {"hypothesis": "客户集中度是否过高", "verification_path": "查年报", "risk_if_false": "客户流失风险", "key": "customer_concentration", "priority": "high"},
                    ],
                    "peer_relative_strength": {
                        "available": True,
                        "peer_sample_size": 2,
                        "comparisons": [
                            {"metric": "gross_margin", "target": 0.38, "peer_median": 0.29, "diff_percentage_points": 9.0, "direction": "above"},
                        ],
                        "summary": "毛利率高于同行中位数约 9.0 个百分点。",
                    },
                    "attack_budget_tiers": {
                        "available": True,
                        "target_market_cap": 120e9,
                        "tiers": {
                            "low": {"budget": 1.2e9, "first_year_focus": "复制标准化功能", "realistic_3_year_reach": "追平边缘渠道", "recommended_angle": "绕开核心市场"},
                            "mid": {"budget": 6e9, "first_year_focus": "建立产能", "realistic_3_year_reach": "追上部分产品线", "recommended_angle": "局部正面试探"},
                            "high": {"budget": 24e9, "first_year_focus": "全链路复制", "realistic_3_year_reach": "正面争夺份额", "recommended_angle": "可正面进攻核心市场"},
                        },
                        "note": "预算量级基于目标公司市值推断。",
                    },
                    "perspectives": {
                        "founder_competitor": {
                            "prompt_role": "创业者/竞争对手",
                            "attack_vectors": ["价格战"],
                            "defense_signals": ["已有规模"],
                            "unknowns": ["客户集中度"],
                        },
                        "industry_researcher": {
                            "prompt_role": "产业研究员",
                            "structure_observations": ["利润池在瓶颈环节"],
                            "profit_pool_hypotheses": ["利润池可能在产能和认证"]
                        },
                        "long_term_investor": {
                            "prompt_role": "长期投资者",
                            "durability_signals": ["现金流为正"],
                            "fragility_signals": ["估值偏高"],
                            "unknowns": ["替代技术"],
                            "conclusion": "正在把投入转化为长期壁垒的公司",
                        },
                    },
                    "conclusion": {
                        "one_line_business": "Micron 的真正生意是产品公司，而不是简单的行业标签。",
                        "one_line_moat": "最核心的护城河目前更像是产能和认证。",
                        "one_line_hardest_to_copy": "竞争对手最难复制的是供应链卡位。",
                        "one_line_market_fear": "市场担心估值先于壁垒兑现。",
                        "one_line_verification": "客户集中度是否过高",
                        "classification": "正在把投入转化为长期壁垒的公司",
                        "rationale": "护城河、现金流和利润率至少有两项同时指向可持续性。",
                        "cyclical_caveat": "该公司处于周期性行业，当前利润率可能反映周期位置而非稳态。",
                    },
                },
            },
        },
    )

    assert "### 护城河压力测试" in markdown
    assert "## 三、基本面与估值" in markdown
    assert markdown.index("## 三、基本面与估值") < markdown.index("### 护城河压力测试")
    assert "#### 创业者/竞争对手视角" in markdown
    assert "#### 已确认事实" in markdown
    assert "#### 合理推断" in markdown
    assert "#### 需要验证的假设" in markdown
    assert "#### 同行相对强弱" in markdown
    assert "#### 竞争对手攻击模拟（三档预算）" in markdown
    assert "[高]" in markdown  # 优先级标签
    assert "周期性提示" in markdown
    assert "最终判断" in markdown
    assert not any(line == "## 护城河压力测试" for line in markdown.splitlines())
