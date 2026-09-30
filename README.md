# 洞穴水准高程网配平（Leveling Network Adjustment）

把多条往返水准观测**联合**配成一致的高程网：不再逐条改正（可能每段都合格、环路却闭合不了），
而是一次性选择全部测站的整数高程，使

```
每条观测改正 c = H_end − H_start − 实测高差 Δh，且 |c| ≤ 该观测最大允许改正量
```

并按以下优先级（字典序）选定唯一解：

1. **最小化最大绝对改正量** `max |c|`
2. 在此前提下**最小化绝对改正量总和** `Σ |c|`
3. 再按**测站录入顺序展开的高程序列**取字典序最小（基准高程固定）

每一级目标用整数线性规划（CBC，经 PuLP）求解，上一级最优值固定后才解下一级，
避免大权重合并目标的数值风险。无可行解时明确返回“允许改正量不足”，且不返回任何旧高程/改正。

## 组成

| 目录 | 技术栈 | 说明 |
| --- | --- | --- |
| `backend/` | FastAPI + PuLP + CBC | `POST /api/adjust` 联合配平；`GET /health` 健康检查 |
| `frontend/` | Vite + 原生 JS | 录入 5–10 个唯一测站、7–18 条带方向观测；展示高程、逐观测改正/回算高差与基本环路闭合核验 |
| `verify/` | shell + stdlib | 一次性校验服务：等待健康 → 后端测试 → 前端测试+构建 → 闭合网 API 冒烟 |
| `docker-compose.yml` | compose | 以 `WEB_PORT` / `API_PORT` 暴露服务，含健康检查 |

## 快速开始

```bash
cp .env.example .env      # 可改 WEB_PORT / API_PORT（默认 8080 / 8000）
docker compose up --build
# 前端 http://localhost:${WEB_PORT}
# API  http://localhost:${API_PORT}/health  （Swagger 文档在 /docs）
```

前端经 nginx 把 `/api` 反向代理到 `api` 服务；页面中“API 地址”留空即走同源代理。

编辑任意草稿（测站名、基准、高差、限值增删改）会**立即撤销旧结论**并提示“草稿已修改，旧结果已失效”；
提交成功后展示各站高程、逐观测改正与回算高差，并对生成树余枝对应的基本环路累加回算高差，
联合配平下这些环路全部自然闭合为 0。无可行配平时保留草稿、清空旧结果并提示放宽允许改正量。

## 一次性 verify

```bash
docker compose --profile verify up --build verify
# 退出码位掩码：bit0 后端测试 | bit1 前端测试/构建 | bit2 API 冒烟（含健康等待）
docker compose --profile verify rm -f verify   # 清理已退出的一次性容器
```

verify 服务在 `api`、`web` 均健康后才启动；冒烟用例独立累加环路回算高差验证闭合差为 0，
并核对最小最大改正、改正总和、字典序结果，以及限值全为 0 时 `feasible=false` 且结果被清空。

## 本地开发（不使用 Docker）

```bash
# 后端
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend && python -m pytest -q
uvicorn app.main:app --reload --port 8000   # 在 backend/ 下

# 前端
cd frontend && npm install && npm test && npm run build && npm run dev
```

## API 摘要

`POST /api/adjust`

```jsonc
{
  "stations": [{"name": "A", "benchmark": true}, ...],   // 5–10 个，名称唯一，恰好一个基准
  "benchmark_height": 1000,                                // 整数毫米
  "observations": [                                        // 7–18 条
    {"start": "A", "end": "B", "delta": 125, "limit": 3}   // delta/limit 均为整数毫米，limit ≥ 0
  ]
}
```

成功：`feasible=true`，`elevations`（按录入顺序）、每条观测的 `correction` / `back_delta` /
`within_limit`、`max_abs_correction`、`total_abs_correction`。
无可行解：HTTP 200 且 `feasible=false`，高程与改正列表为空，`message` 指明允许改正量不足；
网络语义错误（重名、缺基准、未知端点、测站与基准不连通等）返回 422 并带中文说明。
