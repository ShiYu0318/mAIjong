# mAIjong 麥醬

台灣十六張麻將的線上對戰、AI 對手與強化學習研究平台。規則依照常見的台灣十六張玩法：底＋台×每台、連莊拉莊、花牌、搶槓、過水、留牌 16 張等。

## 功能

- **規則引擎**（`engine/`）：純函式狀態機 `apply_action(state, player, action)`，O(1) 向聽數查表、完整台型（39 種）與支付計算，可用種子＋動作序列完整重播。
- **線上對戰**（`backend/` + `frontend/`）：FastAPI + WebSocket 房間、快速配對、房間碼、斷線由電腦代打並可重連、聊天、計時器；PixiJS 牌桌。
- **AI 對手**：Lv1 隨機、Lv2–3 規則型（含防守）、Lv4 DQN、Lv5 PPO／MaskablePPO（評估勝率未達門檻時自動退回規則型）。
- **學習輔助**：局內提示（向聽、進張、聽牌台數、危險牌）、AI 教練課程、手牌分析、決策問答、引導對局、錄影播放與 AI 決策評分。
- **強化學習**（`ai/`）：Gymnasium 環境、行為克隆、自寫 PPO／Dueling DQN（PER、N 步）、Stable-Baselines3 MaskablePPO 多行程自我對弈、PettingZoo 四人多代理環境、依名次與對手強度更新的四人 rating。
- **實驗室**（`/lab`）：訓練監控即時曲線、策略比較（含顯著性）、模擬執行器、錄影探索器。
- **社群與競賽**：`maijong-sdk` 打包提交代理程式、隔離沙盒驗證、競技場排位、賽季與排行榜、挑戰賽、人類排位。
- **練習與完善**：情境練習（55 題）、速度挑戰、防守練習；PWA、鍵盤與螢幕閱讀器支援、英文介面。

## 架構

```
engine/     規則引擎（純 Python，無外部依賴）
ai/         代理程式、特徵、RL 環境與訓練（PyTorch、SB3、PettingZoo）
backend/    FastAPI、WebSocket 房間 hub、SQLAlchemy + Alembic、競技場、實驗室任務
frontend/   Next.js 15 + PixiJS 8 + Zustand + Tailwind v4
sdk/        maijong-sdk：寫代理程式、本機評估、打包提交（MIT）
packages/   maijong-engine：SDK 依賴的引擎套件
scripts/    查表產生、批次模擬、情境產生、本機開發
tests/      引擎、AI、後端、SDK 測試與 Playwright 端對端測試
```

選用的基礎設施（不設定時全部退回單機模式）：PostgreSQL（預設 SQLite）、Redis（房間快照、重啟恢復、跨實例觀戰）、MinIO／S3（錄影檔與預簽名下載）、Celery（實驗室任務與排位排程）。

## 快速開始

需要 Python 3.12（建議用 [uv](https://docs.astral.sh/uv/)）與 Node 20 + pnpm。

```bash
uv sync --extra backend --extra ai     # 後端與 AI（含 PyTorch）
(cd frontend && pnpm install)
./scripts/dev.sh                       # 後端 :8000、前端 :3000
```

瀏覽器開 http://localhost:3000 。只想在終端機玩：

```bash
uv run python -m engine.cli play --seed 1    # 親自打一手
uv run python -m engine.cli watch --seed 3   # 觀看四個電腦打一圈
```

### Docker

```bash
docker compose up --build              # postgres、redis、minio、backend、frontend
docker compose build sandbox           # 提交代理程式用的隔離映像檔（MAIJONG_SANDBOX=docker）
```

設定項目見 `.env.example`。

## 訓練 AI

```bash
# 產生規則型自對弈資料並做行為克隆
uv run python scripts/simulate_batch.py --agents rule rule rule rule -n 3000 --save data/bc/rule_3k.jsonl.gz
uv run python -m ai.training.bc_trainer --data data/bc/rule_3k.jsonl.gz --out checkpoints/bc_v2.pt --epochs 30
# 大型資料用串流：--chunk-hands 5000

# 自寫 PPO（value 暖身、KL 錨定）
uv run python -m ai.training.ppo_trainer --init checkpoints/bc_v2.pt --out checkpoints/ppo_latest.pt --updates 300

# Stable-Baselines3 MaskablePPO 自我對弈（多行程）
uv run python -m ai.training.sb3_trainer --steps 2000000 --envs 8 --bc-data data/bc/rule_3k.jsonl.gz --run sb3-mine
```

訓練曲線寫入 `runs/<名稱>/metrics.jsonl`，可在實驗室「所有訓練紀錄」即時查看；設定 `WANDB_PROJECT` 也會同步到 Weights & Biases。

多代理框架可直接使用 PettingZoo 環境：

```python
from ai.marl import env
e = env()
e.reset(seed=0)
for agent in e.agent_iter():
    obs, reward, term, trunc, info = e.last()
    ...
```

## 寫自己的代理程式

```python
from maijong_sdk import Action, BaseAgent, Observation

class MyAgent(BaseAgent):
    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        return legal_actions[0]
```

```bash
uv run python -m maijong_sdk.evaluate --agent my_agent.py:MyAgent --opponent greedy --games 200
uv run python -m maijong_sdk.cli pack --agent my_agent.py:MyAgent --name "My Bot v1"
```

把產生的 `submission.zip` 上傳到網站的「社群 AI」頁面，通過 10 手沙盒驗證後即加入競技場。範例在 `sdk/examples/`。

## 測試

```bash
uv run pytest                 # 引擎、AI、後端、SDK
uv run ruff check . && uv run mypy
cd frontend && pnpm lint && pnpm typecheck && pnpm e2e
```

## 授權

主程式 Apache-2.0；`sdk/`（maijong-sdk）MIT。
