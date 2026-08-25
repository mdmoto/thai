# 泰国行为校准数据交接规范 v1

## 目标

本规范把客户数据分为五类，先脱敏、校验，再决定能否进入模型。原始姓名、电话、邮箱、详细地址、身份证、设备 ID、IP 地址和社交账号不得上传。

## 文件与最低门槛

| 数据集 | 模板 | 最低门槛 | 可支持的结论 |
|---|---|---:|---|
| 真实选择组 | `observed_choices_v1.csv` | 至少 `max(20, 可用特征数 × 5)` 个选择组，建议 100+；每组至少 2 个备选且恰好 1 个 chosen | 条件选择模型、WTP/属性权重 |
| 曝光—转化漏斗 | `conversion_funnel_v1.csv` | 200 行，建议覆盖 8–12 周 | 转化率、价格/折扣/运费响应 |
| 成交订单 | `customer_transactions_v1.csv` | 100 行，建议覆盖 6–12 个月 | 销售、客单、复购、渠道和地区描述；不能单独估计转化率 |
| 门店历史 | `venue_history_v1.csv` | 30 行，建议逐小时覆盖 8–12 周 | 到店、收入、服务时间回测 |
| 真人调查 | `human_survey_v1.csv` | 100 行；重要分层每格建议 30+ | 态度、平台使用、品牌偏好、真人验证 |

## 必须遵守

1. `customer_hash` / `respondent_id` 必须是客户方生成的不可逆随机标识，不能使用手机号或邮箱直接哈希；建议带客户私有 salt 或使用随机映射表，映射表不交付。
2. 时间使用 ISO 8601 并保留泰国时区 `+07:00`；金额使用泰铢，不混入字符串或货币符号。
3. 订单表只有购买者，缺少未购买曝光，因此只能描述成交；要估计转化率必须另交曝光—转化漏斗。
4. 选择数据必须包含未购买/不选择选项（若真实任务中存在），避免高估购买率。
5. 首次交付可为 CSV；正式持续接入再切换到只读数据库视图或对象存储的定时文件。
6. 模板中的 `example-*` 行仅用于说明格式；正式交付前请删除并替换为真实脱敏记录。

## 本地校验

```bash
PYTHONPATH=packages .venv/bin/python -m data_pipeline.cli validate-customer-data \
  --dataset-type observed_choices \
  --input /path/to/observed_choices.csv \
  --output /path/to/validation-report.json
```

校验器会检查必填字段、最低样本、选择组完整性以及直接身份信息。`safe_to_import=false` 时不得进入系统。

## 官方公开数据刷新

商务部 CPI 与消费者信心无需密钥：

```bash
PYTHONPATH=packages .venv/bin/python -m data_pipeline.cli refresh-moc \
  --from-year 2025 --to-year 2026
```

日度农产品价格先搜索官方商品代码，再采集所需日期区间：

```bash
PYTHONPATH=packages .venv/bin/python -m data_pipeline.cli search-moc-products \
  --keyword "rice" --sell-type retail

PYTHONPATH=packages .venv/bin/python -m data_pipeline.cli \
  refresh-moc-agricultural-price --product-id P11001 \
  --from-date 2026-08-01 --to-date 2026-08-25
```

泰国央行系列搜索需要在运行环境设置 `BOT_API_KEY`，密钥不会写入快照：

```bash
BOT_API_KEY=... PYTHONPATH=packages .venv/bin/python -m data_pipeline.cli \
  search-bot-series --keyword "household debt"
```

先搜索并确认系列代码、频率、单位和修订规则，再将观测值接入生产；系列发现结果本身不改变模型参数。
