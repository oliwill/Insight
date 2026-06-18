"""_infer_business_model 业务模式归类的单元测试。

重点验证：
- 词边界匹配：'platform data storage'/'networking equipment' 不再误判为平台
- 优先级：资源型/基础设施（强信号）优先于平台/渠道
- 'and' 不再作为多种模式叠加的信号
- 真实样本回归：AMKR/01060/603906/MRAAY 的归类符合阶段一样本评估结论
"""
from analyzer.fundamental import _infer_business_model


def _model(business_summary: str = "", sector: str = "", industry: str = "") -> str:
    return _infer_business_model(
        {"business_summary": business_summary, "sector": sector, "industry": industry},
        {},
    )


# ========== 真实样本回归（阶段一评估时的结论） ==========

def test_amkr_semiconductor_packaging_is_infrastructure_not_platform():
    # AMKR 真实 business_summary 含 'platform data storage' 和 'networking'，
    # 原逻辑误判为平台公司；正确应为基础设施公司（封测制造）。
    summary = (
        "Amkor Technology, Inc. provides outsourced semiconductor packaging and "
        "test services in the United States, Japan, Europe, and the Asia Pacific. "
        "It offers turnkey packaging and test services, including semiconductor "
        "wafer bump, wafer probe, wafer back-grind, package design, packaging, "
        "burn-in, system-level and final test, and drop shipment services; flip "
        "chip scale package products for smartphones, tablets, and other mobile "
        "consumer electronic devices; flip chip stacked chip scale packages for "
        "products for system memory or platform data storage."
    )
    assert _model(summary, "Technology", "Semiconductor Equipment & Materials") == "基础设施公司"


def test_mraay_electronic_components_is_infrastructure():
    summary = (
        "Murata Manufacturing Co., Ltd. develops, manufactures, and sells "
        "ceramic-based passive electronic components and solutions in Japan and "
        "internationally. It offers capacitors; inductors; high frequency devices."
    )
    assert _model(summary, "Technology", "Electronic Components") == "基础设施公司"


def test_damai_entertainment_is_platform():
    # 01060 大麦娱乐：文娱内容+IP 商业化，确实是平台型
    summary = (
        "Damai Entertainment Holdings Limited operates content, technology, and "
        "IP merchandising and commercialization businesses. The company operates "
        "a ticketing platform and entertainment ecosystem."
    )
    assert _model(summary, "Communication Services", "Entertainment") == "平台公司"


def test_lopal_resource_chemicals_is_resource():
    # 603906 龙蟠科技：锂电正极材料 + 车用环保精细化工
    summary = (
        "Jiangsu Lopal Tech. Group Co., Ltd. engages in the research and "
        "development, production, and sale of lithium iron phosphate cathode "
        "materials and environmental protection fine chemicals for vehicles."
    )
    assert _model(summary, "Energy", "Oil & Gas Refining & Marketing") == "资源型公司"


# ========== 词边界匹配专项 ==========

def test_platform_substring_resolves_to_infrastructure_when_equipment_present():
    # 'platform data storage' 单独看是歧义的（platform 确实是独立词）；
    # 真正的保障是优先级：当同时有 equipment/packaging 这类基础设施强信号时，
    # 设备制造才是主业务，不应归平台。AMKR 的真实场景正是如此。
    summary = "makes memory products and platform data storage equipment"
    assert _model(summary, "Technology", "Semiconductor Equipment") == "基础设施公司"


def test_networking_substring_not_treated_as_platform():
    # 'networking equipment' 是设备/基础设施语境
    assert _model("sells networking equipment and switches", "Technology", "Communication Equipment") != "平台公司"


def test_cross_platform_not_treated_as_platform():
    assert _model("builds cross-platform mobile applications", "Technology", "Software") != "平台公司"


def test_real_platform_keyword_still_classified_as_platform():
    # 真正的平台型描述（two-sided marketplace）仍应识别
    assert _model("operates a two-sided marketplace connecting buyers and sellers", "Consumer Cyclical", "Internet Retail") == "平台公司"


def test_ecosystem_keyword_still_classified_as_platform():
    # 注意：industry='Software' 会把 SaaS 信号提到 ecosystem 之前，所以这里用一个
    # 不会被软件关键词盖过的 industry，验证 ecosystem 真正触发平台归类。
    assert _model("runs a developer ecosystem with app marketplace", "Technology", "Communication Services") == "平台公司"


# ========== 优先级专项 ==========

def test_equipment_takes_priority_over_platform_substring():
    # 同时含 'equipment'（基础设施强信号）和 'platform'（子串弱信号），应归基础设施
    summary = "manufactures semiconductor test equipment for platform servers"
    assert _model(summary, "Technology", "Semiconductor Equipment") == "基础设施公司"


def test_oil_gas_takes_priority():
    summary = "explores and produces oil and gas with distribution network"
    assert _model(summary, "Energy", "Oil & Gas E&P") == "资源型公司"


def test_saas_software_classification():
    assert _model("provides a saas subscription for analytics", "Technology", "Software") == "产品/订阅型公司"


# ========== 'and' 不再作为多种模式叠加信号 ==========

def test_lone_and_does_not_trigger_hybrid():
    # 旧逻辑：任何含 'and' 的句子都归 '多种模式叠加'，几乎全错
    # 新逻辑：'and' 不再单独触发叠加
    assert _model("designs and manufactures widgets", "Industrials", "Machinery") != "多种模式叠加"


def test_hybrid_keyword_still_works():
    # 明确的 hybrid/叠加 描述仍可识别
    assert _model("operates a hybrid model combining manufacturing and platform services", "Industrials", "Conglomerates") == "多种模式叠加"


# ========== 降级与默认 ==========

def test_empty_inputs_returns_product_default():
    assert _model("", "", "") == "产品公司"


def test_generic_product_company():
    assert _model("makes consumer electronics gadgets", "Consumer Cyclical", "Consumer Electronics") == "产品公司"


def test_channel_retail_classification():
    assert _model("operates retail stores and distribution channels", "Consumer Defensive", "Retail") == "渠道公司"
