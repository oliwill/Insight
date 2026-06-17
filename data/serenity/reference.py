"""Serenity 方法论常量 — 打分规则、提示词模板、层级模板、产业知识库。"""

LAYER_TEMPLATE = [
    "下游需求（终端客户/应用场景）",
    "系统集成（ODM/OEM/品牌商）",
    "芯片/器件（核心元件）",
    "设备（制造设备/测试设备）",
    "材料（晶圆/光刻胶/特种气体等）",
    "封测（封装/测试）",
    "基础设施（云/IDC/电力等）",
]

BOTTLENECK_RULES = {
    "low_supplier_count": {"label": "低供应商数量", "score": 2, "condition": "该层级关键供应商不超过3家"},
    "long_verification": {"label": "长验证周期", "score": 2, "condition": "客户认证/验证周期 >= 18个月"},
    "hard_expansion": {"label": "扩产困难", "score": 2, "condition": "扩产周期 >= 18个月或产能已被长协锁死"},
    "strict_certification": {"label": "客户认证严格", "score": 1, "condition": "进入客户供应链需要严格认证（航空/车规/信创等）"},
    "material_scarcity": {"label": "材料/工艺稀缺", "score": 1, "condition": "核心材料或工艺被少数几家掌控"},
    "geo_restriction": {"label": "地缘限制", "score": 1, "condition": "受出口管制/实体清单/地缘政策影响"},
    "patent_barrier": {"label": "专利壁垒", "score": 1, "condition": "核心专利被少数企业把持，新进入者难以绕过"},
}

SCORING_RULES = {
    "weak": {"max_score": 4, "label": "弱瓶颈"},
    "medium": {"max_score": 6, "label": "中等瓶颈"},
    "strong": {"max_score": 10, "label": "强瓶颈"},
}

EVIDENCE_LEVELS = {
    "order": "订单/合同公告",
    "certification": "客户认证/准入公告",
    "financial": "财报/电话会",
    "analyst": "分析师/行业报告",
    "media": "媒体报道",
    "none": "无公开来源",
}

SERENITY_PROMPT = """你是一个产业链研究分析师。你的任务是：给定一个热点主题，拆解其产业链结构，找出瓶颈环节，筛选出最值得优先研究的公司。

# 步骤
1. 理解主题：这个热点是什么？真实需求驱动来自哪里？
2. 拆解产业链：按从下游到上游的顺序列出关键层级。
3. 瓶颈判断：对每个层级评估供需紧张度、扩产难度、客户认证壁垒、材料稀缺程度。
4. 候选筛选：在瓶颈层级中找关键公司，按离瓶颈距离、证据强度、风险收益排序。

# 产业链默认层级
{layers}

# 输出格式
返回 JSON，字段：
- topic: 输入的主题词
- depth: "normal" 或 "deep"
- summary: {{"description": "一句话定位", "demand_driver": "真实需求来源"}}
- layers: 列表，每项 "name", "key_companies_cn", ...
- candidates: 列表，每项 "company", "layer", ...

每个层级最多列 3-5 家代表性公司。candidates 按 priority 1-5 排序。"""


def classify_bottleneck(score: int) -> str:
    for key, rule in sorted(SCORING_RULES.items(), key=lambda x: x[1]["max_score"]):
        if score <= rule["max_score"]:
            return rule["label"]
    return "强瓶颈"


# ============================================================
# 别名映射：用户输入的各种写法 → 知识库规范 key
# ============================================================
LAYER_MAP: dict[str, str] = {
    "mram": "mram",
    "mrams": "mram",
    "mram.us": "mram",
    "ai半导体": "ai 半导体",
    "ai 半导体": "ai 半导体",
    "人工智能半导体": "ai 半导体",
    "cpo": "cpo",
    "共封装光学": "cpo",
    "机器人": "机器人",
    "减速器": "机器人减速器",
    "机器人减速器": "机器人减速器",
    "固态电池": "固态电池",
    "hbm": "hbm",
    "先进封装": "先进封装",
    "gpu": "gpu",
    "gpus": "gpu",
    "mnts": "space infrastructure",
    "mnts.us": "space infrastructure",
    "momentus": "space infrastructure",
    "space infrastructure": "space infrastructure",
}


# ============================================================
# 产业知识库 — 每个主题对应分析数据
# ============================================================
INDUSTRY_KNOWLEDGE: dict[str, dict] = {
    "ai 半导体": {
        "summary": {
            "description": "AI 半导体是支撑大模型训练和推理的核心硬件产业链",
            "demand_driver": "大模型参数持续增长驱动算力需求，带动芯片、HBM、先进封装、设备投资"
        },
        "layers": [
            {
                "name": "下游需求（终端客户/应用场景）",
                "key_companies_cn": ["字节跳动", "腾讯", "阿里巴巴"],
                "key_companies_global": ["Google", "Microsoft", "Meta"],
                "supply_demand": "tight",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            },
            {
                "name": "系统集成（ODM/OEM/品牌商）",
                "key_companies_cn": ["浪潮信息", "中科曙光"],
                "key_companies_global": ["Dell", "HP", "Super Micro"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": False,
                "scarcity": "low"
            },
            {
                "name": "芯片/器件（核心元件）",
                "key_companies_cn": ["海光信息", "寒武纪", "华为海思"],
                "key_companies_global": ["NVIDIA", "AMD", "Intel"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "设备（制造设备/测试设备）",
                "key_companies_cn": ["北方华创", "中微公司", "上海微电子"],
                "key_companies_global": ["ASML", "Applied Materials", "Lam Research"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "材料（晶圆/光刻胶/特种气体等）",
                "key_companies_cn": ["沪硅产业", "安集科技"],
                "key_companies_global": ["信越化学", "SUMCO", "陶氏"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "封测（封装/测试）",
                "key_companies_cn": ["长电科技", "华天科技", "通富微电"],
                "key_companies_global": ["ASE", "Amkor", "JCET"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": False,
                "scarcity": "low"
            },
            {
                "name": "基础设施（云/IDC/电力等）",
                "key_companies_cn": [],
                "key_companies_global": ["AWS", "Azure", "GCP"],
                "supply_demand": "balanced",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            }
        ],
        "candidates": [
            {
                "company": "北方华创", "layer": "设备（制造设备/测试设备）",
                "rationale": "国产设备龙头，受益于晶圆厂国产替代扩产",
                "evidence": "financial", "valuation_pressure": "high",
                "risks": ["ASML 光刻机出口管制", "美国实体清单升级"], "priority": 1
            },
            {
                "company": "海光信息", "layer": "芯片/器件（核心元件）",
                "rationale": "国产 x86 CPU，AI 推理场景需求增长",
                "evidence": "financial", "valuation_pressure": "high",
                "risks": ["AMD IP 授权限制", "Fab 产能瓶颈"], "priority": 2
            },
            {
                "company": "沪硅产业", "layer": "材料（晶圆/光刻胶/特种气体等）",
                "rationale": "大硅片国产化稀缺标的",
                "evidence": "media", "valuation_pressure": "high",
                "risks": ["良率爬坡不及预期", "海外巨头价格战"], "priority": 3
            }
        ]
    },

    "mram": {
        "summary": {
            "description": "MRAM（磁阻随机存取存储器）是一种非易失性存储技术，兼具 SRAM 的速度和 Flash 的非易失性，正在取代嵌入式 Flash 和部分 SRAM 应用",
            "demand_driver": "IoT 边缘设备、汽车电子、工业 MCU 对低功耗高可靠性存储需求增长；嵌入式 eFlash 在先进制程下缩放困难，MRAM 成为理想替代方案"
        },
        "layers": [
            {
                "name": "下游需求（终端客户/应用场景）",
                "key_companies_cn": [],
                "key_companies_global": ["NXP (MCU)", "STMicroelectronics (MCU)", "Infineon (汽车/工业)", "瑞萨 (R-Car/车用)"],
                "supply_demand": "tight",
                "expansion_difficulty": "medium",
                "certification_barrier": True,
                "scarcity": "medium"
            },
            {
                "name": "芯片/器件（核心元件）",
                "key_companies_cn": [],
                "key_companies_global": ["Everspin Technologies (MRAM 独立芯片)", "TSMC (eMRAM 代工)", "Samsung (eMRAM)", "GlobalFoundries (eMRAM)", "台积电 (22nm eMRAM)"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "设备（制造设备/测试设备）",
                "key_companies_cn": [],
                "key_companies_global": ["Applied Materials (MTJ 沉积)", "Canon (光刻)", "Tokyo Electron (蚀刻)"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "材料（晶圆/光刻胶/特种气体等）",
                "key_companies_cn": [],
                "key_companies_global": ["信越化学 (硅晶圆)", "JSR (光刻胶)", "SUMCO (硅晶圆)"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": False,
                "scarcity": "medium"
            },
            {
                "name": "封测（封装/测试）",
                "key_companies_cn": [],
                "key_companies_global": ["ASE", "Amkor"],
                "supply_demand": "balanced",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            },
            {
                "name": "基础设施（云/IDC/电力等）",
                "key_companies_cn": [],
                "key_companies_global": [],
                "supply_demand": "unknown",
                "expansion_difficulty": "unknown",
                "certification_barrier": False,
                "scarcity": "unknown"
            }
        ],
        "candidates": [
            {
                "company": "Everspin Technologies (MRAM)", "layer": "芯片/器件（核心元件）",
                "rationale": "全球唯一量产独立 MRAM 芯片供应商，拥有最完整的 MRAM 产品组合（STT-MRAM），直接受益于替代 eFlash 趋势",
                "evidence": "financial", "valuation_pressure": "medium",
                "risks": ["客户集中度高", "先进制程竞争（台积电 eMRAM）", "收入规模小"], "priority": 1
            },
            {
                "company": "TSMC (eMRAM)", "layer": "芯片/器件（核心元件）",
                "rationale": "拥有最先进的 22nm eMRAM 工艺，已获多家客户流片，未来 eFlash 替代的核心平台",
                "evidence": "media", "valuation_pressure": "medium",
                "risks": ["eMRAM 目前收入占比极小", "NVM 技术路线竞争（RRAM/PCM）"], "priority": 2
            },
            {
                "company": "NXP", "layer": "下游需求（终端客户/应用场景）",
                "rationale": "MRAM 最大的潜在替代市场是 MCU 嵌入式存储，NXP 是全球最大汽车 MCU 供应商",
                "evidence": "analyst", "valuation_pressure": "medium",
                "risks": ["eFlash 技术转型周期慢", "对 MRAM 投入进度不确定"], "priority": 3
            }
        ]
    },

    "cpo": {
        "summary": {
            "description": "CPO（共封装光学/Co-Packaged Optics）是将光引擎与交换芯片共封装的下一代互联技术，旨在突破传统可插拔光模块的带宽和功耗瓶颈",
            "demand_driver": "AI 集群和数据中心内部带宽需求从 800G 向 1.6T/3.2T 演进，传统可插拔光模块功耗和密度已无法满足"
        },
        "layers": [
            {
                "name": "下游需求（终端客户/应用场景）",
                "key_companies_cn": [],
                "key_companies_global": ["Google", "Microsoft", "Meta", "AWS"],
                "supply_demand": "tight",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            },
            {
                "name": "系统集成（ODM/OEM/品牌商）",
                "key_companies_cn": [],
                "key_companies_global": ["Cisco", "Juniper", "Arista"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": True,
                "scarcity": "medium"
            },
            {
                "name": "芯片/器件（核心元件）",
                "key_companies_cn": [],
                "key_companies_global": ["Broadcom (交换机芯片)", "Marvell (DSP)", "NVIDIA (交换机芯片)", "Intel (硅光)"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "设备（制造设备/测试设备）",
                "key_companies_cn": [],
                "key_companies_global": ["ASML", "Applied Materials"],
                "supply_demand": "balanced",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "材料（晶圆/光刻胶/特种气体等）",
                "key_companies_cn": [],
                "key_companies_global": ["Lumentum (激光器)", "Coherent (激光器)"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "封测（封装/测试）",
                "key_companies_cn": [],
                "key_companies_global": ["ASE", "Amkor"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": True,
                "scarcity": "medium"
            },
            {
                "name": "基础设施（云/IDC/电力等）",
                "key_companies_cn": [],
                "key_companies_global": ["AWS", "Azure", "GCP", "Equinix"],
                "supply_demand": "balanced",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            }
        ],
        "candidates": [
            {
                "company": "Broadcom", "layer": "芯片/器件（核心元件）",
                "rationale": "全球最大交换芯片供应商，CPO 核心推动者，已推出 Tomahawk 5 并规划内建光学方案",
                "evidence": "financial", "valuation_pressure": "low",
                "risks": ["技术路线不确定性", "竞争对手追赶"], "priority": 1
            },
            {
                "company": "Intel (硅光)", "layer": "材料（晶圆/光刻胶/特种气体等）",
                "rationale": "Intel 在硅光集成领域积累最深，拥有完整的 300mm 硅光产线",
                "evidence": "media", "valuation_pressure": "high",
                "risks": ["Intel 代工业务持续亏损", "硅光良率风险"],
                "priority": 2
            }
        ]
    },

    "gpu": {
        "summary": {
            "description": "GPU（图形处理器）是 AI 训练和推理的核心计算单元，也是游戏和图形渲染的基础芯片",
            "demand_driver": "大模型训练推理需求爆发、游戏显卡升级周期、自动驾驶和工业模拟对并行计算的需求"
        },
        "layers": [
            {
                "name": "下游需求（终端客户/应用场景）",
                "key_companies_cn": ["字节跳动", "腾讯", "阿里巴巴", "百度"],
                "key_companies_global": ["Google", "Microsoft", "Meta", "Amazon", "OpenAI"],
                "supply_demand": "tight",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            },
            {
                "name": "系统集成（ODM/OEM/品牌商）",
                "key_companies_cn": [],
                "key_companies_global": ["Dell", "HP", "Super Micro", "联想"],
                "supply_demand": "balanced",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            },
            {
                "name": "芯片/器件（核心元件）",
                "key_companies_cn": ["景嘉微", "壁仞科技", "摩尔线程"],
                "key_companies_global": ["NVIDIA", "AMD", "Intel"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "设备（制造设备/测试设备）",
                "key_companies_cn": ["北方华创", "中微公司"],
                "key_companies_global": ["ASML", "Applied Materials", "Lam Research", "KLA"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "封测（封装/测试）",
                "key_companies_cn": ["长电科技", "通富微电"],
                "key_companies_global": ["ASE", "Amkor"],
                "supply_demand": "tight",
                "expansion_difficulty": "medium",
                "certification_barrier": False,
                "scarcity": "medium"
            },
            {
                "name": "基础设施（云/IDC/电力等）",
                "key_companies_cn": [],
                "key_companies_global": ["AWS", "Azure", "GCP"],
                "supply_demand": "balanced",
                "expansion_difficulty": "low",
                "certification_barrier": False,
                "scarcity": "low"
            }
        ],
        "candidates": [
            {
                "company": "NVIDIA", "layer": "芯片/器件（核心元件）",
                "rationale": "AI GPU 绝对龙头，占训练市场 80%+ 份额，CUDA 生态壁垒极高",
                "evidence": "financial", "valuation_pressure": "high",
                "risks": ["估值过高", "AMD/专用芯片竞争加剧", "出口管制影响收入"],
                "priority": 1
            },
            {
                "company": "ASML", "layer": "设备（制造设备/测试设备）",
                "rationale": "唯一供应先进 EUV 光刻机，GPU 和高带宽存储器的制造瓶颈",
                "evidence": "financial", "valuation_pressure": "medium",
                "risks": ["出口管制升级", "技术路线风险"],
                "priority": 2
            }
        ]
    },

    "hbm": {
        "summary": {
            "description": "HBM（高带宽存储器）是 3D 堆叠 DRAM，通过 TSV 和微凸块实现远超传统 DDR 的带宽，是 AI GPU 最关键的配套芯片",
            "demand_driver": "AI GPU（H100/B200/GB200）对 HBM 需求持续激增，2024-2026 年供需持续紧张"
        },
        "layers": [
            {
                "name": "下游需求（终端客户/应用场景）",
                "key_companies_cn": [],
                "key_companies_global": ["NVIDIA", "AMD", "Intel"],
                "supply_demand": "tight",
                "expansion_difficulty": "low",
                "certification_barrier": True,
                "scarcity": "medium"
            },
            {
                "name": "芯片/器件（核心元件）",
                "key_companies_cn": [],
                "key_companies_global": ["SK Hynix", "Samsung", "Micron"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "设备（制造设备/测试设备）",
                "key_companies_cn": [],
                "key_companies_global": ["ASML", "Applied Materials", "Tokyo Electron"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "封测（封装/测试）",
                "key_companies_cn": ["长电科技"],
                "key_companies_global": ["ASE", "Amkor"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": False,
                "scarcity": "medium"
            }
        ],
        "candidates": [
            {
                "company": "SK Hynix", "layer": "芯片/器件（核心元件）",
                "rationale": "HBM3/HBM3E 领先供应商，率先进入 NVIDIA 供应链",
                "evidence": "financial", "valuation_pressure": "medium",
                "risks": ["Samsung 追赶竞争", "产能扩张资本开支巨大"],
                "priority": 1
            }
        ]
    },
    "space infrastructure": {
        "summary": {
            "description": "太空基础设施是支撑卫星运营、在轨服务、太空运输和太空制造的技术与产业链",
            "demand_driver": "低轨卫星星座爆发式增长，在轨服务与太空制造需求兴起；国防/情报卫星需求稳定增长；商业太空运输成本持续下降打开新应用场景"
        },
        "layers": [
            {
                "name": "下游需求（终端客户/应用场景）",
                "key_companies_cn": [],
                "key_companies_global": ["SpaceX", "Amazon", "OneWeb", "US DoD/USSF", "Planet Labs"],
                "supply_demand": "tight",
                "expansion_difficulty": "low",
                "certification_barrier": True,
                "scarcity": "medium"
            },
            {
                "name": "系统集成（ODM/OEM/品牌商）",
                "key_companies_cn": ["中国卫星", "航天科技"],
                "key_companies_global": ["Momentus", "Northrop Grumman", "Maxar", "Airbus Defence"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "芯片/器件（核心元件）",
                "key_companies_cn": [],
                "key_companies_global": ["BAE Systems", "Microchip", "Honeywell", "Collins Aerospace"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "设备（制造设备/测试设备）",
                "key_companies_cn": [],
                "key_companies_global": ["Rocket Lab", "SpaceX", "ULA", "Arianespace"],
                "supply_demand": "tight",
                "expansion_difficulty": "high",
                "certification_barrier": True,
                "scarcity": "high"
            },
            {
                "name": "材料（航天级材料/推进剂/特种合金等）",
                "key_companies_cn": [],
                "key_companies_global": ["SolAero", "Deployable Space Systems", "Mynaric"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": True,
                "scarcity": "medium"
            },
            {
                "name": "封测（卫星总装/集成/测试）",
                "key_companies_cn": [],
                "key_companies_global": ["York Space Systems", "EnduroSat", "Tyvak International"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": True,
                "scarcity": "low"
            },
            {
                "name": "基础设施（地面站/发射场/测控网络）",
                "key_companies_cn": [],
                "key_companies_global": ["AWS Ground Station", "Azure Space", "KSAT", "SSC"],
                "supply_demand": "balanced",
                "expansion_difficulty": "medium",
                "certification_barrier": False,
                "scarcity": "low"
            }
        ],
        "candidates": [
            {
                "company": "Momentus", "layer": "系统集成（ODM/OEM/品牌商）",
                "rationale": "提供 Vigoride 在轨运输和 Servicer 在轨服务平台，独特的微波等离子推进技术，已获多个商业/政府合同",
                "evidence": "financial", "valuation_pressure": "medium",
                "risks": ["收入规模小/现金流紧张", "发射依赖第三方火箭", "竞争者资源雄厚"],
                "priority": 1
            },
            {
                "company": "Rocket Lab", "layer": "设备（制造设备/测试设备）",
                "rationale": "小型运载火箭龙头，Electron 已高频发射，Neutron 中型火箭开发中，垂直整合卫星组件业务",
                "evidence": "financial", "valuation_pressure": "high",
                "risks": ["Neutron 开发进度风险", "SpaceX 价格竞争", "尚未实现持续盈利"],
                "priority": 2
            },
            {
                "company": "Northrop Grumman", "layer": "系统集成（ODM/OEM/品牌商）",
                "rationale": "Mission Extension Vehicle 在轨服务已验证成功，国防太空合同龙头",
                "evidence": "order", "valuation_pressure": "low",
                "risks": ["在轨服务收入占比小", "大型国防承包商增长缓慢"],
                "priority": 3
            }
        ]
    },
}


def classify_bottleneck(score: int) -> str:
    for key, rule in sorted(SCORING_RULES.items(), key=lambda x: x[1]["max_score"]):
        if score <= rule["max_score"]:
            return rule["label"]
    return "强瓶颈"
