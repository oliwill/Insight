# Serenity 产业链扫描集成文档

## 概述

Serenity 产业链扫描现已完整集成到 Obsidian 分析框架中。当执行产业链扫描时，系统会自动将分析结果填充到 Wiki 页面的多个关键 section，而不仅仅是追加到研究笔记。

## 集成方式

### 1. 综合评估 — 行业/TAM 维度
- **内容**：产业链主题描述 + 目标公司所在层级的供需状态 + 瓶颈分 + 需求驱动
- **示例**：`MRAM（磁阻随机存取存储器）是一种非易失性存储技术... | 芯片/器件（核心元件供需紧张 | 瓶颈分6/10 | 驱动: IoT 边缘设备...`

### 2. 五维打分
基于产业链分析自动计算三个维度：

| 维度 | 评分逻辑 | 示例 |
|------|---------|------|
| **行业/TAM** | 基础分5 + 供需紧张层级数 + 目标层级瓶颈分 | 8/10 (赛道方向:上行, TAM规模:大) |
| **护城河** | 基于所在层级的瓶颈分（技术壁垒、认证壁垒、稀缺性） | 6/10 (技术/IP:6/10, 客户锁定:强, 规模:稀缺) |
| **增长质量** | 基于需求驱动清晰度 + 供需紧张度 + 扩产难度 | 9/10 (需求驱动:清晰, 供需:tight) |
| 估值 | 保留给财务数据 | - |
| 团队/治理 | 保留给其他数据 | - |
| **综合** | 三维度平均 | 7.7/10 产业链位置优越 |

### 3. 证据表
将产业链候选公司作为证据条目：
- **证据**：公司名称 + 所在层级 + 投资逻辑
- **类型**：产业链
- **来源**：财报/电话会、媒体报道、分析师报告等
- **可信度**：高/中
- **影响维度**：目标公司标记为"行业/TAM, 护城河"，其他标记为"交叉引用"
- **影响**：优先级1-2为+3，其他为+1
- **备注**：主要风险

### 4. 交叉引用
自动生成产业链相关公司列表：
- **产业链候选公司**：所有候选公司及其所在层级
- **产业链关键玩家**：各层级的中国/海外关键公司

### 5. 研究笔记
保留原有的完整产业链分析 Markdown（主题定位、产业链拆解、瓶颈判断、优先研究清单、检查清单）

### 6. 分析时间线
追加产业链扫描记录：
```
- **2026-06-12 14:00** | 类型: Serenity 产业链扫描 (mram)
  - 位于「芯片/器件（核心元件）」
```

## 使用方法

### 命令行

```bash
# 分析 MRAM 产业链并写入 Obsidian（自动填充所有 section）
python scripts/serenity_scan.py MRAM

# 分析特定股票（如 Everspin）
python scripts/serenity_scan.py MRAM --stock-code MRAM

# 仅打印 Markdown（不写入）
python scripts/serenity_scan.py MRAM --dry-run

# 输出 JSON 格式
python scripts/serenity_scan.py MRAM --dry-run --json
```

### Python API

```python
from data.serenity.chain_analyzer import ChainAnalyzer
from data.serenity.bottleneck_scorer import BottleneckScorer
from data.serenity.integrator import SerenityIntegrator
from memory.manager import MemoryManager

# 1. 执行产业链分析
analyzer = ChainAnalyzer()
result = analyzer.analyze('MRAM', 'normal')

# 2. 瓶颈评分
scorer = BottleneckScorer()
scorer.score_layers(result.get('layers', []))
scorer.rank_candidates(result.get('candidates', []))

# 3. 集成到 Obsidian
mm = MemoryManager()
integrator = SerenityIntegrator()
updated_sections = integrator.integrate('MRAM', result, mm)

print(f"已更新 sections: {', '.join(updated_sections)}")
# 输出: 已更新 sections: 综合评估, 五维打分, 证据表, 交叉引用, 研究笔记, 分析时间线
```

## 支持的产业主题

当前知识库已内置以下产业链数据：

| 主题 | 别名 | 描述 |
|------|------|------|
| **MRAM** | mram, mrams | 磁阻随机存取存储器，替代嵌入式 Flash |
| **AI 半导体** | ai半导体, 人工智能半导体 | 支撑大模型训练和推理的核心硬件 |
| **CPO** | cpo, 共封装光学 | 光引擎与交换芯片共封装的下一代互联技术 |
| **GPU** | gpu, gpus | AI 训练和推理的核心计算单元 |
| **HBM** | hbm | 3D 堆叠 DRAM，AI GPU 关键配套芯片 |
| **机器人减速器** | 减速器, 机器人减速器 | 机器人核心传动部件 |
| **固态电池** | 固态电池 | 下一代电池技术 |
| **先进封装** | 先进封装 | Chiplet/2.5D/3D 封装技术 |

## 技术细节

### 公司定位逻辑
`SerenityIntegrator._find_company_position()` 按以下优先级定位目标公司：
1. 精确匹配：stock_code 在候选公司名称中
2. 模糊匹配：使用第一个候选公司
3. 兜底：返回瓶颈分最高的层级

### 评分算法
- **行业/TAM**：基础分5 + 供需紧张层级数（≥4层+2，≥2层+1）+ 目标层级瓶颈分（≥5+1）+ 供需紧张（+1）
- **护城河**：直接等于目标层级的瓶颈分（0-10）
- **增长质量**：基础分5 + 需求驱动清晰（+2）+ 供需紧张（+1）+ 扩产困难（+1）

### 文件位置
- **集成器**：`data/serenity/integrator.py`
- **CLI 入口**：`scripts/serenity_scan.py`
- **知识库**：`data/serenity/reference.py` (INDUSTRY_KNOWLEDGE)
- **测试**：`tests/test_serenity/test_integrator.py`

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 仅测试 Serenity 模块
python -m pytest tests/test_serenity/ -v

# 验证 MRAM 集成
python scripts/serenity_scan.py MRAM
# 然后检查 Obsidian: 4_Trader/Analysis/MRAM.md
```

## 示例输出

执行 `python scripts/serenity_scan.py MRAM` 后，Obsidian 中 MRAM.md 的更新：

### 综合评估表
```
| 维度 | 当前判断 | 上次判断 | 变化 | 更新时间 |
|------|----------|----------|------|----------|
| 行业/TAM | MRAM（磁阻随机存取存储器）是一种非易失性存储技术... | - | 新增 | 2026-06-12 14:00 |
| 护城河 | - | - | - | - |
| ... |
```

### 五维打分
```
| 维度 | 得分 | 子维度评分 | 更新时间 |
|------|------|-----------|----------|
| 行业/TAM | 8/10 | 赛道方向:上行, TAM规模:大, 资金流向:- | 2026-06-12 14:00 |
| 护城河 | 6/10 | 技术/IP:6/10, 客户锁定:强, 规模:稀缺 | 2026-06-12 14:00 |
| 增长质量 | 9/10 | 需求驱动:清晰, 供需:tight | 2026-06-12 14:00 |
| 估值 | - | PSG:-, 同行溢价:-, 安全边际:- | - |
| 团队/治理 | - | CEO:-, 董事会:-, 内部人:-, SBC:- | - |
| **综合** | 7.7/10 产业链位置优越 | 判定:Serenity产业链分析 | 2026-06-12 14:00 |
```

### 证据表
```
| 证据 | 类型 | 来源 | 可信度 | 影响维度 | 影响 | 备注 |
|---|---|---|---|---|---|---|
| Everspin Technologies (MRAM)(芯片/器件): 全球唯一量产独立 MRAM... | 产业链 | 财报/电话会 | 高 | 行业/TAM, 护城河 | +3 | 风险:客户集中度高... |
| TSMC (eMRAM)(芯片/器件): 拥有最先进的 22nm eMRAM 工艺... | 产业链 | 媒体报道 | 中 | 行业/TAM, 护城河 | +3 | 风险:eMRAM 目前收入占比极小... |
| NXP(下游需求): MRAM 最大的潜在替代市场是 MCU... | 产业链 | 分析师/行业报告 | 中 | 交叉引用 | +1 | 风险:eFlash 技术转型周期慢... |
```

### 交叉引用
```
> Serenity 产业链扫描自动生成的交叉引用

### 产业链候选公司
- **Everspin Technologies (MRAM)** — 芯片/器件（核心元件）
- **TSMC (eMRAM)** — 芯片/器件（核心元件）
- **NXP** — 下游需求（终端客户/应用场景）

### 产业链关键玩家
- **下游需求**: NXP (MCU), STMicroelectronics (MCU), Infineon (汽车/工业)...
- **芯片/器件**: Everspin Technologies (MRAM 独立芯片), TSMC (eMRAM 代工)...
- **设备**: Applied Materials (MTJ 沉积), Canon (光刻)...
```

## 未来扩展

### 添加新产业主题
在 `data/serenity/reference.py` 的 `INDUSTRY_KNOWLEDGE` 字典中添加新条目：

```python
INDUSTRY_KNOWLEDGE = {
    "新主题": {
        "summary": {
            "description": "一句话描述",
            "demand_driver": "真实需求来源"
        },
        "layers": [
            {
                "name": "下游需求（终端客户/应用场景）",
                "key_companies_cn": ["中国公司1", "中国公司2"],
                "key_companies_global": ["海外公司1", "海外公司2"],
                "supply_demand": "tight",  # tight/balanced/loose/unknown
                "expansion_difficulty": "high",  # high/medium/low/unknown
                "certification_barrier": True,
                "scarcity": "high"  # high/medium/low/unknown
            },
            # ... 其他层级
        ],
        "candidates": [
            {
                "company": "公司名称",
                "layer": "所在层级名称",
                "rationale": "投资逻辑",
                "evidence": "financial",  # order/certification/financial/analyst/media/none
                "valuation_pressure": "medium",  # high/medium/low
                "risks": ["风险1", "风险2"],
                "priority": 1
            }
        ]
    }
}
```

### 别名映射
在 `LAYER_MAP` 中添加别名：

```python
LAYER_MAP = {
    "新别名": "规范主题名",
}
```

## 故障排查

### 问题：Obsidian 未更新
- 检查 `.env` 中的 `WIKI_BASE_DIR` 和 `WIKI_SUBDIR` 配置
- 确认 `4_Trader/Analysis/` 目录存在
- 检查文件权限

### 问题：五维打分为空
- 确认产业链分析返回了有效的 `layers` 和 `candidates`
- 检查目标公司是否在候选列表中

### 问题：交叉引用为空
- 确认 `candidates` 或 `layers` 不为空
- 检查层级中是否有 `key_companies_cn` 或 `key_companies_global`

## 版本历史

- **2026-06-12**: 完成 SerenityIntegrator 实现，集成到 Obsidian 分析框架
- **2026-06-12**: 移除错误的 MNTS 别名映射（MNTS 是 Momentus，非 MRAM）
- **2026-06-12**: 添加完整的集成测试

## 参考

- [Serenity 原始 README](https://github.com/muxuuu/serenity-skill/blob/main/README.md)
- [Obsidian Wiki 结构](memory/manager.py)
- [报告生成器](data/serenity/report_builder.py)
