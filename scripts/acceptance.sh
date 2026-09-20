# 本地与 CI 辅助：构建并运行 Compose 中的 verify 验收服务（真实 Chromium）。
#!/usr/bin/env sh
set -e
exec docker compose --profile verify run --rm --build verify "$@"
