# SSA

基于 FastAPI 的异步 Web 后端服务，提供用户认证（注册/登录/登出/注销）等基础能力。

## 技术选型

| 分类 | 技术 | 选型理由 |
|---|---|---|
| **Web 框架** | FastAPI | 原生异步支持、自动 OpenAPI 文档、Pydantic 集成、类型安全 |
| **ASGI 服务器** | Uvicorn | FastAPI 官方推荐，支持热重载和标准模式 |
| **ORM** | SQLAlchemy 2.0+ | 异步 session 支持（AsyncSession）、声明式映射、成熟生态 |
| **数据库** | SQLite（开发）/ PostgreSQL（生产） | 开发期零配置；生产通过 `database_url` 配置切换，无需改代码 |
| **密码哈希** | bcrypt (5.x) | 自动加盐、抗暴力破解、行业标准 |
| **JWT** | python-jose | 支持 HS256/RS256 等多种算法，JWT 创建/解码标准库 |
| **配置管理** | pydantic-settings | 自动读取 `.env`，类型校验，IDE 友好 |
| **包管理** | uv | Rust 实现，比 pip 快 10-100x，lockfile 确定性构建 |
| **测试** | pytest + httpx + pytest-asyncio | 异步测试、ASGI 传输层直连（不走网络） |
| **代码规范** | pre-commit + commitizen | Conventional Commits 强制校验 |

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
                                │  ┌───────────────────┐  │
                                │  │  lifespan: init_db │  │
                                │  └───────────────────┘  │
                                └───────────┬─────────────┘
                                            │
                        ┌───────────────────┼───────────────────┐
                        │                   │                   │
                        ▼                   ▼                   ▼
                ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
                │   api/        │   │   core/       │   │   services/   │
                │  (路由层)      │   │  (核心逻辑)    │   │  (业务服务)    │
                │  - 参数校验    │   │  - 密码哈希    │   │  - 注册/登录   │
                │  - 认证依赖    │   │  - JWT签发     │   │  - 日志/登出    │
                │  - 状态码/响应 │   │  - 纯函数      │   │  - 账户管理    │
                └───────┬───────┘   └───────────────┘   └───────┬───────┘
                        │                                       │
                        │         ┌───────────────┐             │
                        └────────▶│   models/     │◀────────────┘
                                  │  (数据模型)    │
                                  │  - ORM Model  │
                                  │  - Pydantic   │
                                  └───────┬───────┘
                                          │
                                          ▼
                                  ┌───────────────┐
                                  │   db/         │
                                  │  (数据库层)    │
                                  │  - engine     │
                                  │  - session    │
                                  └───────────────┘
```

### 分层职责与编码规范

#### API 层 (`src/ssa/api/`)

**职责**：路由定义、请求参数校验、响应序列化、HTTP 状态码。只做协议适配，不写业务逻辑。

**编码规则**：
- 每个路由文件只包含端点函数和该域专用的依赖项（如 `get_current_user`）
- 端点函数体不超过 5 行——提取参数后立即委托给 Service
- 使用 `status` 常量，不硬编码数字状态码
- 错误通过 Service 层抛出的 `HTTPException` 处理，不在路由层捕获

**示例 — 新增一个端点**：

```python
# src/ssa/api/v1/auth.py
@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    access_token = await service.authenticate(data.username, data.password)
    return Token(access_token=access_token)
```

**技术要点**：
- `APIRouter(prefix="/auth", tags=["auth"])` — prefix 定义 URL 前缀，tags 分组到 Swagger 文档
- `Depends(get_db)` — FastAPI 依赖注入，自动管理 session 生命周期
- `response_model=Token` — FastAPI 自动校验输出并生成 OpenAPI schema

#### Services 层 (`src/ssa/services/`)

**职责**：业务逻辑编排。组合 core 层（纯函数）和 db 层（数据库操作）完成具体用例。

**编码规则**：
- 每个 Service 类对应一个业务领域（如 `UserService` 管理用户全生命周期）
- Service 构造函数接收 `AsyncSession`，通过依赖注入传入
- 方法命名以动词开头：`register`, `authenticate`, `get_by_id`, `delete_account`
- 业务异常通过 `HTTPException` 抛出（FastAPI 会自动转为 HTTP 错误响应）
- 数据库操作不泄漏到 API 层

**示例**：

```python
class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserCreate) -> User:
        # 1. 校验唯一性
        # 2. 创建 ORM 实例
        # 3. add → commit → refresh
        ...
```

**技术要点**：
- `select(User).where(...)` — SQLAlchemy 2.0 风格的 select 语句，类型安全
- `self.db.add(user)` + `self.db.commit()` — 显式事务控制
- `self.db.refresh(user)` — 刷新以获取数据库生成的默认值（如 id, created_at）

#### Core 层 (`src/ssa/core/`)

**职责**：纯函数、领域逻辑，不依赖 IO（无数据库访问、无 HTTP 调用）。可被 services 和 api 层安全调用。

**编码规则**：
- 所有函数均为纯函数：给定相同输入，始终返回相同输出
- 不导入 `AsyncSession`、`FastAPI` 等 IO 相关模块
- 函数签名显式声明输入输出类型

**示例**：

```python
# src/ssa/core/security.py
def hash_password(password: str) -> str:
    ...

def create_access_token(data: dict) -> str:
    ...
```

**技术要点**：
- bcrypt 自动处理 salt 生成和存储（哈希结果中包含 salt）
- `jti` (JWT ID) 用于实现登出黑名单：每个 token 有唯一 ID，登出时将该 ID 加入黑名单表，校验时查表即可使 token 失效
- `uuid.uuid4()` 生成全局唯一 JTI，碰撞概率可忽略

#### Models 层 (`src/ssa/models/`)

**职责**：定义数据结构。包含两类模型：

| 类型 | 基类 | 用途 | 示例 |
|---|---|---|---|
| **ORM 模型** | `Base` (SQLAlchemy) | 映射数据库表，定义列、约束、索引 | `User`, `TokenBlacklist` |
| **Pydantic 模型** | `BaseModel` | 请求体校验、响应体序列化 | `UserCreate`, `UserLogin`, `UserResponse`, `Token` |

**编码规则**：
- ORM 模型使用 SQLAlchemy 2.0 Mapped 风格（非 legacy `Column` 风格）
- `UserResponse` 设置 `model_config = {"from_attributes": True}` 以支持 ORM → Pydantic 转换
- 每个文件对应一个业务域（`user.py` 包含 User ORM 和所有用户相关 Pydantic 模型）
- 请求模型命名规则：`<Entity><Action>`，如 `UserCreate`, `UserLogin`

**示例 — 新增 ORM 模型**：

```python
class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**技术要点**：
- `String(36)` — JTI 使用 UUID4 格式，36 字符固定长度
- `unique=True, index=True` — 唯一约束 + 索引，加快黑名单查询
- `server_default=func.now()` — 数据库端生成时间戳，避免应用服务器时钟不一致
- `Mapped` 类型注解使 IDE 能推断属性类型，提升开发体验

#### DB 层 (`src/ssa/db/`)

**职责**：数据库连接管理、Session 工厂、表创建。

**编码规则**：
- `session.py` 是唯一创建 engine 的地方
- `get_db()` 作为 FastAPI 依赖生成器，确保每个请求获得独立 session
- `init_db()` 在应用启动时通过 lifespan 调用

**技术要点**：
- `create_async_engine` + `async_sessionmaker` — 全异步数据库链路，不阻塞事件循环
- `expire_on_commit=False` — commit 后不使对象过期，允许在 commit 后继续访问属性
- `echo=settings.debug` — debug 模式下打印 SQL 语句，便于开发调试

## API 端点文档

所有 API 挂载在 `/api/v1/` 前缀下。

### 健康检查

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| `GET` | `/api/v1/health` | 服务存活性检查 | 无 |

### 认证

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | 用户注册 | 无 |
| `POST` | `/api/v1/auth/login` | 用户登录，返回 JWT | 无 |
| `POST` | `/api/v1/auth/logout` | 登出，使当前 token 失效 | Bearer Token |
| `GET` | `/api/v1/auth/me` | 获取当前用户信息 | Bearer Token |
| `DELETE` | `/api/v1/auth/me` | 注销账户（永久删除） | Bearer Token |

### 请求/响应示例

**POST /api/v1/auth/register**

```json
// Request
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "secret123"
}

// Response 201
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "is_active": true,
  "created_at": "2026-05-23T08:30:00Z"
}
```

**POST /api/v1/auth/login**

```json
// Request
{
  "username": "alice",
  "password": "secret123"
}

// Response 200
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

**POST /api/v1/auth/logout** — Response 204 (No Content)

**DELETE /api/v1/auth/me** — Response 204 (No Content)

## 目录结构

```
.
├── src/ssa/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口，create_app() + lifespan
│   ├── config.py            # 配置中心，读取 .env / 环境变量
│   ├── api/                 # API 路由层
│   │   ├── __init__.py
│   │   ├── router.py        # 顶层路由聚合（/api 前缀）
│   │   └── v1/
│   │       ├── __init__.py  # v1 路由聚合
│   │       ├── health.py    # 健康检查端点
│   │       └── auth.py      # 认证端点（注册/登录/登出/注销）+ 认证依赖
│   ├── core/                # 核心逻辑层（纯函数）
│   │   ├── __init__.py
│   │   └── security.py      # 密码哈希、JWT 签发/解码
│   ├── services/            # 业务服务层
│   │   ├── __init__.py
│   │   └── user.py          # 用户服务（注册/认证/登出/注销）
│   ├── models/              # 数据模型
│   │   ├── __init__.py
│   │   └── user.py          # User ORM、TokenBlacklist ORM、Pydantic 请求/响应模型
│   └── db/                  # 数据库层
│       ├── __init__.py
│       ├── base.py          # DeclarativeBase 基类
│       └── session.py       # engine、session factory、get_db 依赖
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures（测试数据库、HTTP client）
│   ├── test_health.py       # 健康检查测试
│   ├── test_auth.py         # 认证流程测试
│   └── test_security.py     # 安全核心函数单元测试
├── pyproject.toml           # 项目元数据、依赖、pytest/commitizen 配置
├── Makefile                 # 常用命令集合
├── .env.example             # 环境变量模板
├── .pre-commit-config.yaml  # pre-commit 钩子配置
└── README.md
```

## 如何新增功能

### 完整开发流程（以"新增用户头像上传"为例）

**Step 1 — 定义数据模型**

在 `src/ssa/models/user.py`（或新建 `src/ssa/models/avatar.py`）中定义：

```python
# ORM 模型 — 映射到数据库表
class Avatar(Base):
    __tablename__ = "avatars"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    url: Mapped[str] = mapped_column(String(512))

# Pydantic 模型 — 请求体校验
class AvatarUpload(BaseModel):
    file: UploadFile
```

模型写完后运行一次 `make dev`，lifespan 中的 `init_db()` 会通过 `Base.metadata.create_all` 自动建表。

**Step 2 — 编写业务逻辑**

在 `src/ssa/services/` 中新建 `avatar.py`：

```python
class AvatarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload(self, user: User, file_data: bytes) -> Avatar:
        # 1. 保存文件到存储（本地/S3）
        # 2. 创建或更新 Avatar 记录
        # 3. commit + refresh
        ...
```

**Step 3 — 定义 API 路由**

在 `src/ssa/api/v1/` 中新建 `avatar.py`：

```python
router = APIRouter(prefix="/avatar", tags=["avatar"])

@router.post("/upload", response_model=AvatarResponse)
async def upload_avatar(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AvatarService(db)
    return await service.upload(current_user, await file.read())
```

**Step 4 — 注册路由**

在 `src/ssa/api/v1/__init__.py` 中注册：

```python
from src.ssa.api.v1.avatar import router as avatar_router
v1_router.include_router(avatar_router)
```

**Step 5 — 编写测试**

在 `tests/` 中新建 `test_avatar.py`，测试覆盖：
- 正常上传成功 → 201
- 未登录上传 → 401
- 文件类型/大小校验 → 422

**Step 6 — 运行测试，提交代码**

```bash
make test          # 确保全部通过
make commit        # 交互式生成 Conventional Commit
```

### 跨层调用规则速查

```
api ──depends──▶ services ──calls──▶ core (pure functions)
  │                  │
  │                  └──calls──▶ db (via AsyncSession)
  │
  └──imports──▶ models (Pydantic schemas only)

❌ api 不直接调 db
❌ services 不接触 HTTP 请求/响应对象
❌ core 不 import AsyncSession / FastAPI
```

## 测试

### 测试工具

| 工具 | 用途 |
|---|---|
| **pytest** | 测试框架，自动发现 `test_*.py` 文件 |
| **pytest-asyncio** | 使测试函数可以是 `async def`，`asyncio_mode = "auto"` 自动检测 |
| **httpx + ASGITransport** | 模拟 HTTP 请求，不经过网络直接调用 FastAPI app |

### 何时写测试

| 场景 | 测试类型 | 要求 |
|---|---|---|
| 新增 API 端点 | 集成测试（通过 httpx 调用） | 必须，覆盖正常路径 + 至少 3 种异常（401/422/409 等） |
| 新增 core 纯函数 | 单元测试（直接调函数） | 必须，覆盖正常 + 边界条件 |
| 新增 Service 方法 | 集成测试（通过 API 间接触发） | 必须，通过对应端点测试 |
| 修复 Bug | 回归测试 | 必须，先写复现 Bug 的测试，再修复 |
| 重构 | 现有测试全部通过 | 重构前跑一次全量测试 |

### 如何写测试

**集成测试示例**（通过 HTTP client 调用 API）：

```python
# tests/test_auth.py
class TestLogout:
    def _auth_header(self, token_response):
        token = token_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_logout_returns_204(self, client):
        # Arrange: 注册 + 登录
        await client.post("/api/v1/auth/register", json=VALID_USER)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "secret123"},
        )
        # Act: 登出
        response = await client.post(
            "/api/v1/auth/logout", headers=self._auth_header(login_resp)
        )
        # Assert
        assert response.status_code == 204

    async def test_revoked_token_cannot_access_me(self, client):
        # 登出后使用同一个 token 访问受保护端点 → 401
        ...
```

**单元测试示例**（直接测试纯函数）：

```python
# tests/test_security.py
class TestPasswordHashing:
    def test_hash_is_salted(self):
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2  # 相同密码产生不同哈希（因为 salt 不同）
```

### 测试约定的目录/命名规范

- 测试文件命名：`tests/test_<module>.py`，对应 `src/ssa/<layer>/<module>.py`
- 测试类命名：`Test<Feature>`，如 `TestRegister`, `TestLogout`
- 测试方法命名：`test_<what>_<expectation>`，如 `test_register_duplicate_username_returns_409`
- 每个测试类内方法共享 fixture（`client`），不同测试类间通过数据库重建隔离
- 公共 fixture 定义在 `tests/conftest.py`，自动被所有测试继承

### conftest.py 工作原理

```python
@pytest_asyncio.fixture(scope="function")
async def client():
    # 1. 为每个测试创建独立的 SQLite 数据库（test.db）
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # 2. 创建 app 实例，用测试数据库覆盖生产数据库依赖
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    # 3. 通过 ASGITransport 创建不经过网络的 HTTP client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # 4. 测试结束后删除所有表，确保测试间完全隔离
    await conn.run_sync(Base.metadata.drop_all)
```

### 运行测试命令

```bash
make test           # 运行全部测试
make testv          # 运行全部测试（详细输出）
uv run pytest -v -k "logout"  # 只运行名称包含 "logout" 的测试
uv run pytest -v --lf         # 只重跑上次失败的测试
```

## 快速开始

### 前置条件

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 初始化

```bash
git clone <repo-url>
cd ssa
make init
```

`make init` 依次执行：
1. `uv sync` — 安装所有依赖并创建 `.venv`
2. 写入 direnv 配置 + `direnv allow`，此后 cd 进入项目自动激活虚拟环境
3. `pre-commit install --hook-type commit-msg` — 安装 commit message 校验钩子

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，修改 jwt_secret_key 为生产密钥（openssl rand -base64 32）
```

### 启动

```bash
make dev
# → http://localhost:8000/docs   Swagger UI
# → http://localhost:8000/redoc  ReDoc
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `make dev` | 启动开发服务器（热重载） |
| `make test` | 运行全部测试 |
| `make testv` | 运行全部测试（详细输出） |
| `make commit` / `make cm` | 交互式生成 Conventional Commits |
| `make cm-check` | 检查最近一次 commit 是否符合规范 |
| `make docker-build` | 构建 Docker 镜像 |
| `make deploy` | 构建镜像 → 上传服务器 → 重启服务 |
| `make clean` | 清理本地构建产物 |

## Git 工作流

### 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/)，通过 commitizen 校验。

```bash
make commit   # 交互式生成规范 commit message
```

格式：`<type>(<scope>): <description>`

| type | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `refactor` | 重构（不改变功能） |
| `test` | 测试相关 |
| `chore` | 构建/工具链变更 |

### 分支策略

- `master`：稳定分支，随时可部署
- `feat/<feature-name>`：功能开发分支
- `fix/<bug-name>`：Bug 修复分支
- 对 `master` 作出修改后，同步更新 README 文档

## 登出与注销机制

### 登出（Logout）

JWT 本身是无状态的，登出通过 **Token 黑名单** 实现：

1. 每个签发的 JWT 包含唯一 `jti`（JWT ID）声明
2. 用户调用 `POST /auth/logout` 时，将当前 token 的 `jti` 和过期时间写入 `token_blacklist` 表
3. 后续请求在 `get_current_user` 依赖中查询黑名单，命中则返回 401 "Token has been revoked"
4. 过期的黑名单条目自然失效（查询时过滤 `expires_at > now`），无需立即清理

### 注销（Delete Account）

`DELETE /auth/me` 永久删除用户数据：

1. 将当前 token 加入黑名单（防止后续使用）
2. 从 `users` 表中删除用户记录
3. 返回 204，无响应体

注销后用户无法重新登录（用户名和邮箱记录已删除），但 `token_blacklist` 中该 token 的条目保留至过期。

## 设计原则

- **分层解耦**：API 层不直接操作数据库，通过 services 层编排
- **单一路由文件不可超过 100 行**：复杂路由按领域拆分
- **版本化 API**：`/api/v1/` 前缀，后续可平滑扩展 v2
- **配置集中**：所有配置通过 `config.py` + `.env` 管理，禁止硬编码
- **无状态设计**：请求不依赖服务端本地状态，便于水平扩展；通过 JWT + 黑名单表实现有状态登出
- **测试隔离**：每个测试使用独立 SQLite 数据库，测试结束自动销毁

## 代码审查 Checklist

- [ ] 新功能是否正确分层？（API 不写业务逻辑，services 不操作 HTTP）
- [ ] 是否有对应的测试用例？（正常路径 + 异常路径）
- [ ] 配置是否通过 `config.py` 读取而非硬编码？
- [ ] API 路由是否正确版本化（`/api/v1/`）？
- [ ] ORM 模型是否在 `Base.metadata` 中注册（导入即注册），以确保 `init_db()` 能自动建表？
- [ ] commit message 是否符合 Conventional Commits 规范？
