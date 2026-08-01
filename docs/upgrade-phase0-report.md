# Upgrade Phase 0 Report

## 阶段

Phase 0 — 基线冻结与原生后端适配器骨架

## 完成内容

- 冻结三类完整报告：宠物智能饮水机、通用商品定价、宁曼路咖啡馆。
- 固定输入、`seed=42`、100 行合成人口和 40 轮风险测试。
- 建立人口合成、选择模型、代表性研究、社会传播四类后端契约。
- 将现有 PopulationGenerator、ConditionalLogitEstimator、Gemini gateway
  和 prior diffusion 包装为 native 后端。
- StudyService 通过后端契约调用人口、选择拟合和代表性研究。
- SimulationEngine 通过社会传播后端契约调用现有 prior diffusion。
- 默认后端和报告结构保持不变。

## 基线

| 案例 | 购买/到店率 | P10 | P90 | 最优方案 |
|---|---:|---:|---:|---|
| 宠物智能饮水机产品验证 | 2.1654% | 1.4503% | 2.9596% | 首发降价 12% |
| 通用消费品定价研究 | 6.0055% | 3.6236% | 8.5396% | 首发降价 12% |
| 宁曼路咖啡馆研究 | 10.1653% | 3.7823% | 16.8772% | 基准经营方案 |

完整报告与 SHA-256 见 `docs/baselines/phase0/manifest.json`。

## 验证

- 改动前：75/75 后端测试通过。
- 改动后：81/81 后端测试通过。
- 三份冻结报告逐字段一致。
- Next.js 生产构建通过，18 个静态页面生成成功。

## 实际使用的第三方组件

本阶段没有安装新的第三方模型组件。Choice-Learn、PopulationSim、
TinyTroupe 和 OASIS 均未启用。

## 已知限制

- 本阶段只建立契约和原生适配器，没有改变模型精度。
- Python 3.12 测试中存在已有的 `datetime.utcnow()` 弃用警告，不影响结果。
- 外部市场研究和 LLM 在冻结报告中关闭，以保证基线可重复。

## 生产开关状态

- `POPULATION_BACKEND=native`
- `CHOICE_MODEL_BACKEND=native`
- `REPRESENTATIVE_AGENT_BACKEND=gemini`
- `SOCIAL_SIMULATION_BACKEND=prior`
- 所有第三方后端保持未安装、未启用。

## 下一阶段

Phase 0.5 — 独立计算镜像与不可变产物管理基础。
