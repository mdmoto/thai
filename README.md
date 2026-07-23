# Thailand Digital Market Twin Platform

把产品、门店或经营方案放入一个由泰国合成消费者构成的数字市场中，比较不同方案可能产生的购买、到店、复购和传播结果。

## 仓库结构

```
market-twin/
  apps/
    web/          # Next.js 前端 (TypeScript + Tailwind)
    api/          # Python 后端 (Cloud Run)
    worker/       # Simulation Worker (Google Cloud Batch)
  packages/
    schemas/      # 版本化数据契约
  prompts/        # LLM Prompt 版本管理
  data_catalog/   # 数据源登记
  infra/          # Terraform
  tests/          # 集成和端到端测试
  docs/           # 开发文档
```

## 快速开始

```bash
cd apps/web
npm install
npm run dev
```

前端运行在 http://localhost:3000

## 技术栈

- **前端**: Next.js 15, TypeScript, Tailwind CSS, React Query
- **后端**: Python, FastAPI, Pydantic
- **数据库**: PostgreSQL, Redis
- **计算**: Google Cloud Batch, Spot VM
- **存储**: Google Cloud Storage
- **LLM**: Gemini
- **CDN**: Cloudflare

## 目标域名

- 生产: https://ai.lazzor.com
- 开发: http://localhost:3000

## GitHub

https://github.com/mdmoto/thai
