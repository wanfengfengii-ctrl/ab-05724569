# 多波长激光干涉 · 整周解算工作台

多波长激光干涉仪测量长距离位移时，每一路读数只给出包裹相位 p∈[0,1)，
真正的距离公式是

```
nᵢ + pᵢ − εᵢ  ≤  d / λᵢ  ≤  nᵢ + pᵢ + εᵢ      （nᵢ ∈ ℤ，整数周数未知）
```

逐路各自取"最近整数"会把局部合理的结果拼成现实中并不存在的位置。
本工作台把所有通道放进**同一个距离闭区间**联立求解，以**精确有理数**
找出全部可行整周向量类别，明确裁决唯一 / 多候选 / 无解，并让计量员在
浏览器中复核每一路的整周数、残差区间与共同距离带。

## 计量语义

- 所有输入均为**有限十进制字符串**：波长 λ>0，相位 0≤p<1，误差界 0≤ε<1/4 周，
  通道数 2–32，距离为闭区间 [d_min, d_max]。
- 后端用 `fractions.Fraction` 精确解析与求解，全程不使用浮点。
- 输出同时给出**精确分数**与四舍五入的十进制近似。
- 裁决：
  - **唯一**：仅有一个整周向量可行，返回其精确距离交集；
  - **多解**：按「交集下端点、整周向量字典序」返回前两份见证，并给出类别总数；
  - **无解**：明确判定读数互不一致 / 区间过窄。

## 算法：为什么不枚举最短波长的整周数

朴素做法按最短波长把量程内整周数逐一枚举（50 km 对 500 nm 即上亿次）。
本实现（`backend/app/solver.py`）：

1. **统一整数刻度**：取所有波长、相位、误差、端点分母的公倍数 U，
   令 D=d·U，分支循环内只有整数运算，结果以 `Fraction(n,U)` 精确还原。
2. **分支限界 + MRV**：每个节点在当前共同距离带上只选取候选整数最少
   （最受限）的通道分裂；某通道候选为空立即剪枝；距离带只缩不扩。
3. **配对模跳变**：当单路候选都很大时，取一对通道，用 gcd / 扩展欧几里得
   直接解模数方程，按**合成波长** W_iW_j/g 大步跳到下一个两路重合簇，
   再对其余通道做 MRV。

例如预置的 41 km 三路（633/532/502 nm）场景，最短波长在粗测区间内有
**19,920** 个整周，而解算只细化 **31** 个分支。前端与 API 的 `stats`
会同时展示这两个数字供核对。

为防止病态输入导致无界搜索，分支细化上限为 5,000,000；触顶时返回
422 并明确声明"无法保证穷尽"，绝不静默截断。

## 快速开始（Docker Compose）

```bash
docker compose up --build
```

- Web 工作台：http://localhost:8080  （可用 `WEB_PORT` 改宿主机端口）
- API 文档：http://localhost:8000/docs （可用 `API_PORT` 改端口）
- 健康检查：`GET /health`

自定义端口：

```bash
WEB_PORT=9090 API_PORT=9000 docker compose up --build
```

## 真实浏览器验收服务

Compose 中提供名为 **`verify`** 的可执行验收服务，在容器内用
Playwright 驱动**真实 Chromium**，覆盖前后端联调（唯一 / 多解 / 无解、
整周数与残差区间、长距离非枚举、输入变化即刻失效、校验阻断、JSON 导入）：

```bash
# 一键
./scripts/acceptance.sh

# 等价于
docker compose --profile verify run --rm --build verify
```

## 本地开发

```bash
# 后端
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q

# 前端
cd frontend
npm install
npm run dev        # http://localhost:5173 ，/api 代理到 8000
npm run build
```

后端测试包含 300 组随机用例与"按最短波长枚举"参照实现的完全对拍。

## HTTP 接口

`POST /api/solve`

```json
{
  "distance": {"min": "0", "max": "1.2"},
  "channels": [
    {"wavelength": "1", "phase": "0.25", "epsilon": "0.1"},
    {"wavelength": "1", "phase": "0.35", "epsilon": "0.1"}
  ]
}
```

响应（节选）：

```json
{
  "status": "unique",
  "total_solutions": 1,
  "witnesses": [{
    "rank": 1,
    "orders": [0, 0],
    "distance_band": {
      "lower": {"fraction": "1/4", "decimal": "0.25", "exact": true},
      "upper": {"fraction": "7/20", "decimal": "0.35", "exact": true},
      "width":  {"fraction": "1/10", "decimal": "0.1", "exact": true}
    },
    "per_channel": [
      {"index": 0, "order": 0,
       "residual_lower": {"fraction": "0", "decimal": "0", "exact": true},
       "residual_upper": {"fraction": "1/10", "decimal": "0.1", "exact": true},
       "within_tolerance": true}
    ],
    "verified": true
  }],
  "stats": {"channels": 2, "cells_refined": 2,
            "naive_shortest_wavelength_integers": 2, "max_cells": 5000000}
}
```

另有 `GET /health` 与 `GET /api/examples`（预置唯一 / 多解 / 无解 /
长距离唯一 / 长距离多解场景）。

## 目录

```
backend/   FastAPI + 精确有理数求解器与测试
frontend/  React + Vite 工作台（编辑 / 导入导出 / 候选复核）
docker/    nginx 配置（静态托管 + API 反代）
verify/    Playwright 真实 Chromium 端到端验收
scripts/   acceptance.sh 便捷入口
Dockerfile           web / api / verify 三个构建目标
docker-compose.yml   web、api 服务与 verify 验收服务
```
