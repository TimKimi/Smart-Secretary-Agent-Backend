# SSA

FastAPI 异步响应请求服务。

## 项目架构

```
                                ┌─────────────────────────┐
                                │       HTTP Request       │
                                └───────────┬─────────────┘
                                            │
                                            ▼
                                ┌─────────────────────────┐
                                │     Uvicorn (ASGI)       │
                                └───────────┬─────────────┘
                                            │
                                            ▼
                                ┌─────────────────────────┐
                                │  FastAPI Application     │
                                │  (src/ssa/main.py)       │
                                └───────────┬─────────────┘
                                            │
                        ┌───────────────────┼───────────────────┐
                        │                   │                   │
                        ▼                   ▼                   ▼
                ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
                │   api/        │   │   core/       │   │   services/   │
                │  (路由层)      │   │  (核心逻辑)    │   │  (业务服务)    │
                └───────┬───────┘   └───────────────┘   └───────────────┘
                        │
                        ▼
                ┌───────────────┐
                │   models/     │
                │  (数据模型)    │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │   db/         │
                │  (数据库层)    │
                └───────────────┘
```

### 分层职责

| 层 | 目录 | 职责 |
|---|---|---|
| **API 层** | `src/ssa/api/` | 路由定义、请求响应处理、参数校验。只做协议适配，不写业务逻辑。 |
| **Services 层** | `src/ssa/services/` | 业务逻辑编排。组合 core 和 db 完成具体用例。 |
| **Core 层** | `src/ssa/core/` | 纯函数、领域逻辑、不依赖 IO。可被 services 和 api 调用。 |
| **Models 层** | `src/ssa/models/` | Pydantic 模型：请求体、响应体、ORM 模型。 |
| **DB 层** | `src/ssa/db/` | 数据库连接、session 管理。当前规划使用 SQLite。 |

### 目录结构

```
.
├── src/ssa/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口，lifespan 管理
│   ├── config.py            # 配置中心，读取 .env
│   ├── api/                 # API 路由层
│   │   ├── __init__.py
│   │   ├── router.py        # 顶层路由聚合
│   │   └── v1/              # API v1 版本
│   │       ├── __init__.py
│   │       └── health.py    # 健康检查端点
│   ├── core/                # 核心逻辑层（纯函数）
│   │   └── __init__.py
│   ├── services/            # 业务服务层
│   │   └── __init__.py
│   ├── models/              # 数据模型
│   │   └── __init__.py
│   └── db/                  # 数据库层（SQLite 待接入）
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures（app, client）
│   └── test_health.py       # 健康检查测试
├── pyproject.toml           # 项目元数据和依赖
├── Makefile                 # 常用命令集合
├── .env.example             # 环境变量模板
└── README.md
```

### 设计原则

- **分层解耦**：API 层不直接操作数据库，通过 services 层编排。单一路由文件不可超过 100 行，复杂路由按领域拆分。
- **版本化 API**：`/api/v1/` 前缀，后续可平滑扩展 v2。
- **配置集中**：所有配置通过 `config.py` + `.env` 管理，不允许硬编码。
- **无状态设计**：每个请求不依赖服务端本地状态，便于水平扩展。

## 快速开始

### 前置条件

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）

```bash
# macOS / Linux 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 克隆项目后首次初始化

```bash
# 1. 克隆仓库
git clone <repo-url>
cd ssa

# 2. 一键初始化（安装依赖 + direnv + pre-commit hooks）
make init
```

> `make init` 会依次执行：
> 1. `uv sync` — 安装所有依赖并创建 `.venv`
> 2. 写入 direnv 配置 + `direnv allow`，此后 cd 进入项目自动激活虚拟环境
> 3. `pre-commit install --hook-type commit-msg` — 安装 commit message 校验钩子

### 启动开发服务器

```bash
make dev
# 等价于: uv run uvicorn src.ssa.main:app --reload --host 0.0.0.0 --port 8000
```

访问：
- Swagger UI：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc
- 健康检查：http://localhost:8000/api/v1/health

### 运行测试

```bash
make test
# 等价于: uv run pytest -v
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `make dev` | 启动开发服务器（热重载） |
| `make test` | 运行全部测试 |
| `make commit` / `make cm` | 交互式生成 Conventional Commits |
| `make cm-check` | 检查最近一次 commit 是否符合规范 |
| `make clean` | 清理本地构建产物 |

## 协作开发规范

### Git 提交规范

本项目使用 [Conventional Commits](https://www.conventionalcommits.org/)，通过 commitizen 校验。

```bash
# 交互式生成规范的 commit message
make commit
```

提交格式：`<type>(<scope>): <description>`

常用 type：`feat` `fix` `docs` `refactor` `test` `chore`

### 分支策略

- `master`：稳定分支，随时可部署
- `feat/<feature-name>`：功能开发分支
- `fix/<bug-name>`：Bug 修复分支

### 代码审查 Checklist

- [ ] 新功能是否在对应层级？（API 不写业务逻辑，services 不操作 HTTP）
- [ ] 是否有对应的测试用例？
- [ ] 配置是否通过 `config.py` 读取而非硬编码？
- [ ] API 路由是否正确版本化（`/api/v1/`）？
- [ ] commit message 是否符合 Conventional Commits 规范？

## 后续规划

| 阶段 | 内容 | 涉及目录 |
|---|---|---|
| **Phase 1** | SQLite 数据库集成、ORM 模型、session 管理 | `db/`, `models/` |
| **Phase 2** | LLM 服务接入、异步任务调度 | `services/`, `core/` |
| **Phase 3** | Docker 化部署、CI/CD 流水线 | 项目根目录 |
