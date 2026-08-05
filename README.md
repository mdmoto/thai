# 🇹🇭 Thailand Digital Market Twin (泰国数字市场孪生决策平台)

[![FastAPI](https://img.shields.io/badge/FastAPI-2.1.0-009688.svg?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.2--Turbopack-000000.svg?style=flat-square&logo=next.js)](https://nextjs.org/)
[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare_Pages-Deployed-F38020.svg?style=flat-square&logo=cloudflare)](https://ai.lazzor.com)
[![Google Cloud Run](https://img.shields.io/badge/Google_Cloud_Run-Asia_Southeast1-4285F4.svg?style=flat-square&logo=googlecloud)](https://cloud.google.com/run)
[![License](https://img.shields.io/badge/License-Proprietary-gold.svg?style=flat-square)](#)

> 面向出海东南亚（泰国）的消费品牌、跨境电商与餐饮零售企业。基于泰国国家统计局（NSO）77 府真实人口微观数据、多项式离散选择模型（MNL Choice Model）、蒙特卡洛风险模拟与 LLM 结构化消费者声浪，提供极高可信度的产品出海验证、客单价弹性响应、商圈选址与全渠道策略。

---

## 🌐 线上环境与访问端点

- **🌐 生产主站**: [https://ai.lazzor.com](https://ai.lazzor.com) *(部署于 Cloudflare Pages)*
- **⚡ 云端 API 服务**: [https://market-twin-api-100282158973.asia-southeast1.run.app](https://market-twin-api-100282158973.asia-southeast1.run.app) *(部署于 Google Cloud Run - 曼谷/东南亚节点)*
- **📘 健康检查**: `GET /v1/health`
- **📚 演示报告**: [https://ai.lazzor.com/demo/pet-water](https://ai.lazzor.com/demo/pet-water) *(泰国宠物智能饮水机大盘模拟示范)*

---

## 🚀 核心特色与商业价值

### 1. 📊 真实官方数据校准 (Official Macro Calibration)
- 结合泰国国家统计局（NSO）Household Socio-Economic Survey 官方统计微观抽样（带 SHA256 快照）。
- 涵盖曼谷都市圈、清迈、普吉岛、芭提雅/春武里（EEC）、孔敬/呵叻（伊森）等全泰 77 府 300,000 人规模的合成居民人口、家庭收入层级与消费支出基线。

### 2. 🧮 离散选择模型与支付意愿 (MNL Choice Model & WTP)
- 严谨的多项式 Logit 选择模型，综合评估焦点产品、多个竞品及“不购买”选项的效用函数。
- 计算消费者的边际支付意愿 (Implied WTP)，消除单一问卷失真。

### 3. 📈 10 大商业级评估报告模块
- **泰国合成样本点状图**：自带泰国国界矢量底图与 7 大核心城市（曼谷、清迈、普吉岛、芭提雅、孔敬、呵叻、合艾）高对比标注。
- **价格 / 客单价响应曲线**：**双 Y 轴 (Dual Y-Axes)** 架构（左轴：购买意向率 %，右轴：相对收入指数），配合 80 以下无意义空白的自适应截断，消除平缓低对比。
- **产品与定价情景对比**：支持降价、品质增强与溢价多情景对比。
- **地理需求与小时经营模型**：包含 15 分钟步行商圈常住人口覆盖与客流到店机会指数。
- **渠道适配与履约诊断**：Shopee、Lazada、TikTok Shop、7-Eleven 渠道匹配度与 COD / 运费履约阻力评估。
- **LLM 消费者声浪面板**：整合结构化弱信号推理，还原泰国不同收入与年龄段消费者的真实顾虑与买点。

### 4. 💳 商业级鉴权与积分计费系统 (Auth & Credits System)
- 基于 JWT 签名令牌的注册与登录系统（新用户注册即赠 5 体验积分）。
- 原子化积分扣减、预留与模拟失败自动退款保障。
- 订单生成与受保护的离线财务入账流。

### 5. 🖨️ 高清离线 PDF 导印支持 (PDF Print Styling)
- 针对报告定制的 `@media print` 样式表，一键将深色极简 UI 转换为高对比度纸质导印排版，满足企业汇报与客户交付需求。

---

## ⚡ 算力等级与配额矩阵

| 方案等级 | AI 模拟人群 | 蒙特卡洛风险轮次 | 竞品上限 | 消耗积分 | 响应耗时 | 推荐使用场景 |
|---|---:|---:|---:|---:|---:|---|
| **Free Preview** | 100 人 | 40 轮 | 1 个 | 0 积分 | < 1 秒 | 快速检查项目输入与基本方向（每账号赠 1 次） |
| **Standard 标准版** | 10,000 人 | 80 轮 | 3 个 | 5 积分 | ~ 5 秒 | 单品初筛、基础价格响应与渠道适配评估 |
| **Professional 专业版** | 30,000 人 | 150 轮 | 5 个 | 20 积分 | ~ 15 秒 | 完整竞品选择集、WTP 弹性、多情景与商圈分析 |
| **Enterprise 深度版** | 300,000 人 | 220 轮 | 10+ 个 | 销售协助 | 超大样本微观分层、Gemini 1.5 Pro 深级 CoT 推理 |

---

## 🏗️ 平台架构与目录结构

```text
Thailand-Market-Twin/
├── apps/
│   ├── web/                    # Next.js 16 (Turbopack) 极简商业前端
│   │   ├── app/                # App Router (Dashboard, Studies, Billing, Methodology)
│   │   ├── components/         # 模块化 UI、AuthModal、RechargeModal 与 AppShell 容器
│   │   ├── lib/                # API 客户端 (带公网 HTTPS 动态解析)、Token 存储与产品目录
│   │   └── public/             # 静态资源与 Cloudflare Pages 标头 (_headers)
│   └── api/                    # FastAPI 2.1 生产级后端 API
│       └── app/
│           ├── db/             # SQLAlchemy 数据库、User/Transaction 模型、JWT 鉴权与计费
│           ├── schemas/        # Pydantic 数据结构校验
│           └── services/       # 模拟运行调度器、10 大报告模块组装器
├── packages/
│   ├── simulation_core/        # 离散选择模型、估计器 (Estimation) 与 Monte Carlo 引擎
│   ├── world_model/            # 泰国 77 府人口分布、合成居民生成器与资格审查
│   ├── agents/                 # Gemini 1.5 Pro / Flash 结构化弱信号推理网关
│   └── data_pipeline/          # NSO 官方统计清洗与电商商品页采集器
├── data_catalog/               # 带 SHA256 校验快照的官方统计数据与类目先验
├── docs/                       # 架构规范、方法论文档 (V2)、部署 Runbook 与发布检查清单
│   ├── model_methodology_v2.md # 模型与统计校准详细方法论说明
│   ├── production-runbook.md   # 云端部署与应急恢复手册
│   └── sales-operations.md     # 收款与积分入账流
└── tests/                      # 模型方向性、数据血缘、账号隔离与退款逻辑测试
```

---

## 💻 本地运行指南

### 方式一：Docker Compose（推荐，最接近生产环境）

```bash
docker compose up --build
```

### 方式二：手动分步启动

#### 1. 启动后端 API 服务 (Python 3.10+)

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r apps/api/requirements.txt

# 启动 FastAPI 服务
PYTHONPATH=apps/api:packages \
  DATABASE_URL=sqlite:////tmp/market_twin.db \
  JWT_SECRET_KEY=local-dev-secret-key-change-in-prod \
  uvicorn app.main:app --app-dir apps/api --reload --port 8080
```
- API 服务运行于: `http://127.0.0.1:8080`
- 健康检查地址: `http://127.0.0.1:8080/v1/health`

#### 2. 启动前端工作区 (Node.js 18+)

```bash
cd apps/web
npm install
npm run dev
```
- 前端运行于: `http://localhost:3000`

---

## 🧪 自动化测试与质量校验

本地研发与发布前，请运行完整测试套件：

```bash
# 运行后端逻辑与算法测试
source .venv/bin/activate
PYTHONPATH=apps/api:packages python -m unittest discover -s tests -v

# 运行前端类型检查与静态导出构建
cd apps/web
npm run build
```

---

## ☁️ 生产部署与运维

- **前端 (Cloudflare Pages)**:
  - 构建命令: `npm run build`
  - 产物输出目录: `out`
  - 域名绑定: `ai.lazzor.com`
- **后端 (Google Cloud Run)**:
  - 部署指令:
    ```bash
    gcloud run deploy ai \
      --source . \
      --region asia-southeast1 \
      --allow-unauthenticated \
      --project thai-503312
    ```
- **环境变量要求**:
  - `GEMINI_API_KEY`: Google AI Studio 接口秘钥。
  - `DATABASE_URL`: PostgreSQL 连接字符串（生产必须）。
  - `JWT_SECRET_KEY`: 高强度加密哈希密钥。

---

## 🛡️ 方法边界与合规声明

当前消费品档案标记为 `official_macro_calibrated_choice_prior`：
1. 人口、地区、家庭收入/支出与规模数据均来自于带 SHA256 哈希快照的泰国国家统计局（NSO）公开数据。
2. 选择系数与支付意愿 (WTP) 基于选择效用建模。报告用于**商业方案筛选与风险防范**，不构成对销量的绝对担保。
3. 大语言模型（LLM）仅生成有权重上限的结构化弱信号；在 API 不可用时权重自动归零，切勿替代真实验证。

完整方法论详见 [docs/model_methodology_v2.md](docs/model_methodology_v2.md)。

---

## 📄 License & 版权

© 2026 Thailand Market Twin Project (Lazzor AI). All Rights Reserved.
