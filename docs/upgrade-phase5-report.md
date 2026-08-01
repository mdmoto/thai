# 第五阶段 OASIS 隔离研发报告

日期：2026-08-01

状态：小规模隔离实验与 prior diffusion 对照完成；不批准进入生产，生产继续使用 `SOCIAL_SIMULATION_BACKEND=prior`、`ENABLE_OASIS=false`。

## 完成内容

1. 建立独立 Python 3.11 研究镜像；生产 API 与原生 Runner 不包含 CAMEL、OASIS、Torch 或相关大型依赖。
2. 固定 CAMEL AI 0.2.78、MCP 1.9.4 和 OASIS 0.2.5 提交 `e97a1d83761605a24a7dc91fa4d4e9defffa7e23`，保留 Apache-2.0 许可证。
3. 使用独立 Cloud Run Job 和最小权限服务账号；该账号没有生产数据库权限，仅可读取研究所需的 Gemini 密钥。
4. Gemini 2.5 Flash 已通过官方 OpenAI 兼容接口接入 CAMEL/OASIS，调用为零重试、30 秒单次超时。
5. 每次实验冻结并硬限制 Agent 数、激活概率、时间步、输入 token、含思考输出 token、美元成本和总墙钟时间。
6. 模型原文、Persona 原文和帖子内容不写入 Cloud Logging 或研究产物；只保留聚合指标与用量。
7. 指标严格限定为 `simulated_social_exposure`、`simulated_interaction`、`simulated_diffusion` 和 `simulated_sentiment`，禁止输出购买率、销售额、真实触达或预测准确率。

## 实验配置

| 项目 | 冻结值 |
|---|---:|
| Persona | 8 个纯合成泰国 Persona |
| 客户数据 | 0 |
| 外部社交平台调用 | 0 |
| 激活概率 | 0.125 |
| 时间步 | 1 |
| 最大输入 token | 40,000 |
| 最大含思考输出 token | 1,000 |
| 最大模型成本 | US$0.10 |
| 最大运行墙钟时间 | 180 秒 |
| seed | 20260801 |

模型价格按 Gemini Developer API 当前标准价格计算：文本输入 US$0.30/百万 token，输出（包含思考 token）US$2.50/百万 token。官方价格：<https://ai.google.dev/gemini-api/docs/pricing>

## 云端实测

两次相同输入与 seed 的结果如下：

| 项目 | 第一次 | 第二次 |
|---|---:|---:|
| Gemini 调用 | 1 | 1 |
| 输入 token | 753 | 753 |
| 含思考输出 token | 267 | 187 |
| 总 token | 1,020 | 940 |
| 模型阶段用时 | 7.726 秒 | 7.844 秒 |
| Cloud Run 任务用时 | 63.55 秒 | 51.50 秒 |
| 估算模型费用 | US$0.000893 | US$0.000693 |

相同 seed 的聚合行为结果一致，但隐藏思考 token 不一致，证明托管 LLM 即使温度为 0 也不能保证逐 token 重现。费用预算必须按实际总用量结算，不能只看可见输出。

## 与 prior diffusion 对照

首次抓取时曾把 OASIS `trace` 表里的注册记录误当作扩散参与者，导致 8 个已创建 Persona 全被算作扩散。该口径已被测试拦截并修正为“种子发布者 + 实际点赞、点踩或评论的唯一 Agent”。修正后的对照为：

| 模拟指标 | OASIS | prior | 差值 |
|---|---:|---:|---:|
| exposure | 8 | 7 | +1 |
| interaction | 1 | 1 | 0 |
| diffusion | 2 | 2 | 0 |
| sentiment | 0 | 0 | 0 |

在这次极小样本中，OASIS 没有显示出优于 prior 的稳定定量增益。它的潜在价值在于后续多步、异质 Persona、推荐机制与口碑冲击情景，而不是直接提高购买率或销量预测。

## 成本、延迟与运维结论

- 模型调用费用很低，当前不是主要问题。
- Cloud Run 冷启动与任务准备约占绝大部分端到端时间。
- 研究镜像约 3.03 GB，主要来自 Torch/CUDA 和 OASIS 的大型可选依赖；每次云构建拉取基础层约 4 分钟。
- 正式扩大实验前应先生成 CPU-only 最小依赖镜像，否则构建、分发、冷启动和漏洞面都不理想。
- 最终镜像摘要为 `sha256:52a5b87ce6aa7b3acbf444d22c0bd1f503f29951039ff4c59479e04d19fe0a4e`，Cloud Build 编号 `92d127aa-823a-4065-a28a-c377975b82c8`，构建来源为 SLSA 3。
- Artifact Registry 查询未返回已知漏洞条目；本地 `pip-audit` 因审计工具临时 Python 环境崩溃未形成有效结果，因此不能把本次结果表述为“零漏洞”。

## 可解释性与法律边界

- prior 模型简单、稳定、容易说明；OASIS 能产生更丰富的行为轨迹，但依赖 LLM 工具选择，解释成本更高。
- OASIS 使用 Apache-2.0 许可证；仍需持续保留第三方声明和固定版本。
- 本次只使用合成 Persona，不向模型发送客户、付款、密码、令牌或真实个人资料。
- OASIS 不登录 Facebook、TikTok、Shopee、Lazada 等真实平台，也不代表这些平台的真实推荐算法或实际用户。
- 若未来处理客户内容或真实人群资料，必须另行完成隐私告知、供应商数据处理、保存期限和跨境传输评估；开源代码不等于客户数据自动公开。

## 当前决定

OASIS 保持研发状态，不进入客户付费报告。下一轮只有在以下条件满足后才扩大到 24–48 个 Agent、多时间步实验：

1. 完成 CPU-only 最小镜像与有效依赖漏洞审计。
2. 把阶段性聚合产物写入私有、版本化 artifact store，并验证取消和预算超限诊断。
3. 预先定义至少三类传播情景和评价指标，连续重复运行以测量结果方差。
4. 证明相对 prior 能提供可解释、可复现且对报告决策有增量价值。
5. 仍不得让 OASIS 直接修改购买率、销量、收入或选址核心结果。

## 验证

- 后端与全项目回归：136 项测试全部通过。
- 最终研究镜像零 LLM 自检：Cloud Run Execution `market-twin-oasis-research-xsk6m` 成功。
- 研究 Job 当前默认命令为零 LLM 技术自检；误执行不会产生模型调用。
- 生产 API 和 Runner 未部署本阶段代码，生产 OASIS 开关保持关闭。
