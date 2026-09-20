# 多波长激光干涉仪 · 整周数解算工作台

激光干涉仪用多组波长测量长距离位移时，每路读数只有包裹相位（缺少整周数）。
逐路取最近整数会把局部合理的结果拼成实际不存在的位置。本工作台以**精确有理数**
求解满足全部通道约束 `|d/λ − n − p| ≤ ε` 的整周向量（可能性类别），并给出精确的共同距离交集。

- 前端：React + TypeScript（Vite），浏览器内导入/编辑测量输入，展示各路整周数、残差区间与共同距离带
- 后端：FastAPI，`fractions.Fraction` 全程精确计算，不使用浮点近似
- 部署：根目录 `Dockerfile`（多阶段）+ `docker-compose.yml`，一条命令启动 Web 与 API
- 验收：Compose 中名为 `verify` 的可执行验收服务，用真实 Chromium 浏览器覆盖联调

## 快速开始

```bash
docker compose up --build
```

- Web: http://localhost:8080 （可用 `WEB_PORT` 覆盖，如 `WEB_PORT=3000 docker compose up`）
- API: http://localhost:8000 （可用 `API_PORT` 覆盖；文档见 `/docs`，健康检查 `/api/health`）

## 运行验收（真实浏览器）

```bash
docker compose --profile verify up --build --exit-code-from verify
```

`verify` 服务等待 `web`、`api` 健康检查后，执行：

- API 验收：健康检查、唯一解/多解/无解、精确有理数结果、输入校验、长距离性能（见下）
- UI 验收（Playwright + Chromium）：页面加载、三种预设解算流程、导入 JSON、
  非法输入拦截、**输入变更后旧结论被清除**、添加/删除通道

## 问题与算法

每路通道 `i` 给定波长 `λ_i > 0`、包裹相位 `p_i ∈ [0,1)`、误差界 `ε_i < 1/4`（周）。
对整周数 `n_i`，可行距离为闭区间“梳齿”
`T_i(n_i) = [λ_i(n_i + p_i − ε_i), λ_i(n_i + p_i + ε_i)]`。
因 `ε_i < 1/4`，同一路相邻梳齿互不接触，故每个连通可行域唯一对应一个整周向量，
其距离集即精确交集 `[lo, hi] ∩ ⋂_i T_i(n_i)`。

**禁止的朴素做法**是逐一枚举最短波长在量程内的所有整周数
（`O((hi−lo)/λ_min)`，长距离下不可行）。本实现采用两种精确策略，均不做该枚举：

1. **增量求精**（量程不超过最长波长 4096 个齿距时）：最长波长先给出最稀疏的初始候选，
   随后每一路只在已存活的狭窄交集窗口内、用精确 floor/ceil 直接算出重叠齿序号——
   最短波长永远只在收窄后的窗口内解析，从不横扫整个量程。
2. **周期合并（CRT）**（长量程）：每路是周期为 `λ_i` 的梳；两两合并时周期取有理数
   `lcm`，一个周期内的重合由丢番图方程 `k2·t2 − k1·t1 = m` 在小窗口整数 `m` 上精确求解；
   最后把周期片按提升指数算术展开——类别总数通过整数区间合并**算术计数**，
   与量程跨越的周期数无关。例如量程 `10⁹`、波长 `1000/1001` 的算例仅考察约百个候选。

两种策略在测试中与指数级暴力 oracle 交叉验证一致（`api/tests/test_solver.py`，173 例）。

### 结果裁决

- 唯一整周向量 → 返回其精确距离交集；
- 多个 → 返回类别总数，并按（交集下端点， 整周向量字典序）返回前两份见证；
- 无解 → 明确返回 `none`。

## API

### `POST /api/solve`

```json
{
  "range": { "lo": "0", "hi": "10" },
  "channels": [
    { "wavelength": "2", "phase": "0.5", "epsilon": "0.1" },
    { "wavelength": "3", "phase": "0.25", "epsilon": "0.1" }
  ]
}
```

- 所有输入为**有限十进制数**（JSON 数字或十进制字符串，支持科学计数法；`"1/3"`、`"nan"` 等会被 422 拒绝）
- 校验：`lo ≤ hi`；2–32 路；`λ > 0`；`0 ≤ p < 1`；`0 ≤ ε < 1/4`

响应（节选）：

```json
{
  "status": "multiple",
  "total_classes": 2,
  "mode": "incremental",
  "candidates_examined": 9,
  "witnesses": [
    {
      "integers": [0, 0],
      "interval": { "lo": {"exact": "4/5", "approx": 0.8}, "hi": {"exact": "21/20", "approx": 1.05} },
      "channels": [
        { "index": 0, "integer": 0,
          "band": {"lo": {"exact": "4/5", "approx": 0.8}, "hi": {"exact": "6/5", "approx": 1.2}},
          "residual": {"lo": {"exact": "-1/10", "approx": -0.1}, "hi": {"exact": "1/40", "approx": 0.025}} }
      ]
    }
  ]
}
```

`exact` 为精确有理数（整数或 `分子/分母`），`approx` 为浮点近似。

### `GET /api/health`

返回 `{"status": "ok"}`，用于 Compose 健康检查。

## 本地开发

```bash
# 后端（http://localhost:8000）
cd api && pip install -r requirements.txt
uvicorn app.main:app --reload

# 后端测试（解算器 + API）
cd api && python -m pytest tests -q

# 前端（http://localhost:5173，代理 /api 到 8000）
cd web && npm install && npm run dev
```

## 目录结构

```
Dockerfile              # 多阶段：api / web / verify
docker-compose.yml      # web + api + verify（含健康检查、可配置端口）
api/
  app/solver.py         # 精确有理数解算器（增量求精 + 周期合并）
  app/schemas.py        # 有限十进制数解析与校验
  app/main.py           # FastAPI 端点
  tests/                # 解算器性质测试（暴力 oracle 交叉验证）与 API 测试
web/
  src/                  # React 工作台（导入/编辑/解算/见证展示）
  nginx.conf            # 静态服务 + /api 反代 + /healthz
verify/
  tests/                # 验收：API 端到端 + Playwright 真实浏览器联调
```
