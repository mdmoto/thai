# Thailand Market Twin

面向进入泰国市场的消费品牌，用版本化人口、竞品证据、离散选择模型和
Monte Carlo 情景模拟，比较产品、价格、目标人群和竞品方案。

当前公开产品只销售已经验证可运行的三个等级：

| 等级 | 人口 | Monte Carlo | 竞品上限 | 积分 |
|---|---:|---:|---:|---:|
| Preview | 100 | 40 | 1 | 0（每账号一次） |
| Standard | 10,000 | 80 | 3 | 5 |
| Professional | 30,000 | 150 | 5 | 20 |

Deep / Enterprise 算法配置仍作为内部研发配置保留，不在当前公开目录中
销售，也不会伪装成已经接入 Cloud Batch 的产品能力。

## 已交付的产品链路

- 真实注册、登录、签名令牌与账号隔离
- 项目创建、事实确认、模拟运行、报告保存与重新读取
- 运行幂等、原子积分预留、失败自动退款
- 待付款订单、受保护的到账确认和不可由前端伪造的积分流水
- 泰国 77 府人口与家庭收入官方聚合校准
- 焦点产品、竞品和“不购买”选项的离散选择模型
- 宠物智能饮水机公开竞品面板与通用消费品先验
- 报告中的数据版本、模型版本、先验预测区间和限制披露
- 静态销售站、工作区、定价、条款、隐私与方法页面

## 方法边界

当前消费品档案标记为
`official_macro_calibrated_choice_prior`。人口、地区、家庭收入/支出与家庭
规模来自带哈希快照的泰国 NSO 公开数据；选择系数、WTP、品类渗透、
品牌认知和复购仍可能是先验。

因此报告用于方案筛选，不是销量、市场份额或收入保证。LLM 只生成有
权重上限的结构化弱信号；供应商不可用时权重为零，不会替换成固定
Persona。

完整方法见 [docs/model_methodology_v2.md](docs/model_methodology_v2.md)。

## 本地运行

最接近生产的方式：

```bash
docker compose up --build
```

或分别运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r apps/api/requirements.txt

PYTHONPATH=apps/api:packages \
  DATABASE_URL=sqlite:////tmp/market_twin.db \
  JWT_SECRET_KEY=local-development-secret \
  uvicorn app.main:app --app-dir apps/api --reload --port 8080
```

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

前端：http://localhost:3000

API：http://localhost:8080

健康检查：http://localhost:8080/healthz

## 验证

```bash
source .venv/bin/activate
PYTHONPATH=apps/api:packages python -m unittest discover -s tests -v
cd apps/web && npm audit && npm run build
```

测试覆盖模型方向性、人口校准、公开数据血缘、账号归属、订单入账、
运行幂等与失败退款。生产发布前还应执行
[docs/release-checklist.md](docs/release-checklist.md)。

## 生产部署

- 前端：静态 Next.js 导出，可部署至 Cloudflare Pages 或 Sites。
- API：Cloud Run 容器。
- 数据库：PostgreSQL，`APP_ENV=production` 时为必填。
- 秘钥：JWT、管理接口和数据库连接只从云端 Secret Manager 注入。

所需环境变量见：

- `apps/api/.env.example`
- `apps/web/.env.example`

发布与恢复步骤见 [docs/production-runbook.md](docs/production-runbook.md)；
收款与积分入账见 [docs/sales-operations.md](docs/sales-operations.md)。

## 主要目录

```text
apps/web/                   销售站与客户工作区
apps/api/                   FastAPI、认证、订单与持久化
packages/simulation_core/   选择模型、校准、估计与情景模拟
packages/world_model/       合成人口与品类资格
packages/agents/            Gemini 结构化弱信号
packages/data_pipeline/     NSO 与公开商品页采集
data_catalog/               版本化快照、来源、面板与档案
tests/                      模型、数据与业务链路测试
```

生产域名目标：https://ai.lazzor.com
