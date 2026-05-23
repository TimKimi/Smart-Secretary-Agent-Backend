# ============================================================
# SSA 项目 Makefile
# ============================================================

# ---------- 服务器配置 ----------
SERVER_HOST   = your-server-ip
SERVER_USER   = root
SERVER_DIR    = /opt/ssa
IMAGE_NAME    = ssa-backend
IMAGE_TAG     = latest
TAR_FILE      = $(IMAGE_NAME).tar
# --------------------------------

.PHONY: help init dev test commit cz cm cm-check docker-build docker-save upload load deploy update clean

# 默认目标
help:
	@echo "开发环境:"
	@echo "  make init          初始化开发环境"
	@echo "  make dev           启动开发服务器"
	@echo "  make test          运行测试"
	@echo "  make testv          运行测试(详细信息)"
	@echo ""
	@echo "提交规范:"
	@echo "  make commit        交互式生成 Conventional Commits 提交"
	@echo "  make cm            同 make commit"
	@echo "  make cz            同 make commit"
	@echo "  make cm-check      检查最近一次提交是否符合规范"
	@echo ""
	@echo "镜像构建:"
	@echo "  make docker-build  构建 Docker 镜像"
	@echo "  make docker-save   构建并导出镜像为 tar 文件"
	@echo ""
	@echo "部署与更新:"
	@echo "  make upload        上传镜像 tar 到服务器"
	@echo "  make load          在服务器上加载 Docker 镜像"
	@echo "  make deploy        完整部署 (构建+上传+重启服务)"
	@echo "  make update        更新服务 (重新构建+上传+重启)"
	@echo ""
	@echo "其他:"
	@echo "  make clean         清理本地构建产物"

# ---------- 本地开发 ----------
init:
	uv sync
	echo 'source .venv/bin/activate' > .envrc
	direnv allow
	pre-commit install --hook-type commit-msg
	@echo "开发环境初始化完成(需对照检查.env.example)"

dev:
	uv run uvicorn src.ssa.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest
testv:
	uv run pytest -v

# ---------- Conventional Commits ----------
commit:
	uv run cz commit

cz: commit

cm: commit

cm-check:
	git log -1 --format=%B | uv run cz check

# ---------- Docker 镜像 ----------
docker-build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-save: docker-build
	docker save -o $(TAR_FILE) $(IMAGE_NAME):$(IMAGE_TAG)

# ---------- 服务器操作 ----------
upload:
	scp $(TAR_FILE) $(SERVER_USER)@$(SERVER_HOST):$(SERVER_DIR)/

load:
	ssh $(SERVER_USER)@$(SERVER_HOST) "docker load -i $(SERVER_DIR)/$(TAR_FILE)"

# ---------- 部署流程 ----------
deploy: docker-save upload
	ssh $(SERVER_USER)@$(SERVER_HOST) "cd $(SERVER_DIR) && docker load -i $(TAR_FILE) && docker-compose down && docker-compose up -d"
	@echo "部署完成，服务已重启"

update: docker-build docker-save upload
	ssh $(SERVER_USER)@$(SERVER_HOST) "cd $(SERVER_DIR) && docker load -i $(TAR_FILE) && docker-compose up -d --force-recreate"
	@echo "服务已更新并重启"

# ---------- 清理 ----------
clean:
	rm -f $(TAR_FILE)
	@echo "临时文件已清理"