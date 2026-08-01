# 生产依赖与构建权限加固报告

日期：2026-08-01

状态：非 OASIS 运行环境已完成依赖升级、漏洞复扫和 Linux 候选镜像验收；候选镜像尚未部署，正式 API 仍为 `market-twin-api-00035-psh`。

## OASIS 隔离

- Cloud Run Job `market-twin-oasis-research` 已移除 `GEMINI_API_KEY` 密钥挂载。
- 研究服务账号已撤销备用 Gemini 密钥的 `secretAccessor` 权限。
- 默认命令继续是零 LLM 技术自检，`ENABLE_OASIS=false`。
- 隔离后执行 `market-twin-oasis-research-lzs7v` 成功。
- OASIS 依赖锁仍有阻塞漏洞，因此不进入本次候选发布。

## 依赖升级

正式 API 与 native Runner 更新为：

- FastAPI 0.141.1
- Starlette 1.3.1
- cryptography 49.0.0
- pyOpenSSL 26.3.0
- python-multipart 0.0.32
- PyArrow 25.0.0

Choice-Learn、PopulationSim 和 TinyTroupe 的独立锁文件也更新了各自受影响依赖。PopulationSim 固定 Protobuf 6.33.5。

使用 `pip-audit 2.10.0` 对以下五个完整锁文件复扫，均未发现已知漏洞：

- `requirements-api.lock`
- `requirements-runner-native.lock`
- `requirements-choice-job.lock`
- `requirements-population-job.lock`
- `requirements-tinytroupe-job.lock`

OASIS 锁文件被明确排除在合格集合外，并继续隔离。

## 构建权限

新增两个用户管理的服务账号：

- `market-twin-security-build`：只读构建源、写指定 Artifact Registry 仓库和 Cloud Logging；不能部署 Cloud Run、读取密钥或访问数据库。
- `market-twin-release-build`：在上述构建权限之外，仅增加 Cloud Run 管理，以及对 `market-twin-api` 运行账号的 `serviceAccountUser`。

默认 Compute Engine 服务账号原有的 Editor、Run Admin、项目级 Service Account User、Artifact Registry Writer、Logging Writer 和 Cloud Build Builder 均已撤销。项目当前没有使用该账号的 Compute Engine 实例。

所有仓库内 Cloud Build 配置现在显式使用专用账号，并将日志写入 Cloud Logging。`cloudbuild.security.yaml` 在重量级构建前对五个非 OASIS 锁文件执行失败关闭的漏洞扫描。

## 验证

- 安全候选 Cloud Build：`b0065021-7c91-4500-9a08-fa7f4b6ec044`，状态 `SUCCESS`。
- API 候选镜像：`sha256:a0fc54f3fa7bf18f3e15dc8f1e76ee42b5e05590193a22b63dde2df67d92ac41`。
- Runner 候选镜像：`sha256:0b6deeb251f1fe3b17f96769f7e5224ad8051a60dd0c46ad501eb29fa9ee4277`。
- Linux API 镜像全量后端回归通过。
- 本地最终回归：137 项通过。
- Next.js 生产构建通过，18 个静态页面生成成功。
- 修复三项只在 Linux 大小写敏感文件系统暴露的 Dockerfile 路径测试错误。

## 当前发布决定

候选版本具备进入正式发布流程的技术条件，但本阶段未切换生产流量。发布时仍需先创建 Cloud SQL 备份，使用新的 `market-twin-release-build` 流程部署，再执行健康、注册、计费、管理、异步 Runner 和报告读取检查。
