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

選用的基礎設施（不設定時全部退回單機模式）：PostgreSQL（預設 SQLite）、Redis（房間快照、重啟恢復、跨實例觀戰）、S3 相容物件儲存（錄影檔與預簽名下載；docker compose 內建 SeaweedFS）、Celery（實驗室任務與排位排程）。

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

macOS 沒有 Docker Desktop 時，可用 Colima（免費、免管理員權限）：

```bash
brew install colima docker docker-buildx docker-compose
mkdir -p ~/.docker && echo '{"cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]}' > ~/.docker/config.json
colima start --cpu 4 --memory 8 --disk 60
```

啟動整套服務：

```bash
docker compose up -d --build           # postgres、redis、s3（SeaweedFS）、backend、frontend
docker compose build sandbox           # 提交代理程式用的隔離映像檔（MAIJONG_SANDBOX=docker）
docker compose down                    # 停止（加 -v 連資料一起清掉）
```

| 服務 | 網址 |
| --- | --- |
| 網站 | http://localhost:3000 |
| API | http://localhost:8000（健康檢查 `/healthz`） |
| S3（錄影檔） | http://localhost:8333，金鑰在 `deploy/seaweedfs-s3.json` |
| PostgreSQL／Redis | localhost:5432／localhost:6379 |

錄影下載連結由後端預簽名：後端在容器內以 `S3_ENDPOINT=http://s3:8333` 存取，瀏覽器則用 `S3_PUBLIC_ENDPOINT=http://localhost:8333`。部署到其他網址時改這一項。MinIO 已停止在 Docker Hub 發布映像檔，所以改用 SeaweedFS；任何 S3 相容服務（AWS S3、R2 等）都可以換上。

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

### 實力天梯

台灣十六張麻將沒有公開的 benchmark（Computer Olympiad 的參賽程式未公開），所以用 `ai.ladder` 讓所有模型互打：每輪挑出賽最少的四個模型同桌，同一副牌打四次、輪流坐遍四個座位，抵銷牌運與座位。Elo 由 Bradley–Terry 模型擬合「同一輪誰得分較多」，以 `lv3` = 1500 為錨點；每手淨得分是相對全體平均、已校正對手強度的最小平方解；兩者都附 200 次 bootstrap 的 95% 信賴區間。

```bash
uv run python -m ai.ladder play --pool default --blocks 20000 --out runs/ladder/main
uv run python -m ai.ladder report runs/ladder/main
```

2026-10-29，24,710 輪（98,840 手，每個模型約 19,000–21,000 手）：

| 名次 | 模型 | 說明 | Elo（95% CI） | 每手淨得分（95% CI） | 胡牌率 | 放槍率 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `rule` | 規則型（溫度 0） | 1597（1587–1606） | +41.1（+36.6–+46.5） | 28.0% | 14.4% |
| 2 | `lv5` | 規則型，配對評估調參（目前 Lv5） | 1595（1587–1603） | +34.6（+29.4–+40.1） | 27.9% | 14.0% |
| 3 | `rollq` | Lv5 + rollout Q 打牌修正（2026-10-29） | 1595（1584–1604） | +33.8（+28.5–+39.1） | 26.6% | 15.0% |
| 4 | `tuned` | 規則型，座標上升調參 | 1594（1585–1605） | +35.8（+31.0–+41.0） | 27.9% | 14.2% |
| 5 | `ppo_v4` | PPO（BC 初始化） | 1589（1581–1599） | +30.9（+25.8–+36.0） | 27.2% | 15.3% |
| 6 | `vote5` | 五個頂尖模型投票（2026-10-29） | 1587（1577–1597） | +30.8（+24.9–+36.4） | 25.8% | 15.1% |
| 7 | `ppo_lv5` | PPO（以 Lv5 為師） | 1585（1577–1595） | +29.4（+25.1–+34.0） | 27.5% | 15.1% |
| 8 | `bc_v3` | BC（10 萬手規則型對局） | 1585（1576–1593） | +29.8（+25.4–+35.1） | 26.7% | 15.7% |
| 9 | `ppo_v5` | PPO（BC 初始化） | 1584（1574–1594） | +27.3（+23.0–+32.6） | 27.1% | 15.3% |
| 10 | `bc_lv5` | BC（以 Lv5 為師） | 1583（1575–1592） | +27.0（+22.3–+32.0） | 27.5% | 15.2% |
| 11 | `lv4` | 規則型（溫度 0.3） | 1562（1552–1571） | +8.9（+3.7–+13.9） | 23.8% | 14.4% |
| 12 | `ppo_v1` | PPO 第一版 | 1561（1552–1570） | +7.9（+3.2–+12.7） | 24.0% | 16.2% |
| 13 | `bc_v2` | BC（3 千手） | 1556（1546–1565） | +5.9（+0.5–+10.7） | 23.8% | 16.5% |
| 14 | `sb3_bc` | SB3（BC 暖身） | 1543（1532–1552） | -1.2（-6.3–+3.9） | 22.4% | 16.8% |
| 15 | `sb3_best` | SB3 MaskablePPO | 1543（1534–1551） | -1.6（-5.4–+2.8） | 22.5% | 17.0% |
| 16 | `lv3` | 規則型（溫度 1.5） | 1500（1500–1500） | -41.0（-44.9–-37.2） | 16.1% | 13.4% |
| 17 | `bc_v1` | BC 第一版 | 1489（1480–1497） | -44.0（-48.9–-39.8） | 16.7% | 18.8% |
| 18 | `lv2` | 規則型（溫度 3） | 1430（1421–1438） | -89.0（-93.0–-85.5） | 8.2% | 12.9% |
| 19 | `random` | 隨機 | 1229（1219–1238） | -166.6（-169.2–-164.5） | 0.1% | 27.3% |

前十名的信賴區間互相重疊，統計上是同一級，包括這次新增的 rollout Q（`rollq`）與投票集成（`vote5`）。配對評估（`ai.training.duplicate`）在沒用過的牌局上也一樣：`rule` 對 `lv5` −1.0 ± 2.9、`lv5` 對 `bc_v3` −2.7 ± 4.6（各 12,000／6,000 副牌）。過去調參時看似顯著的勝出（例如 `lv5` 對 `bc_v3` +9.2）都是在同一批預設牌局上反覆比較得來的，換一批牌就消失；所以宣告勝出前請用 `--seed` 換一批沒看過的牌再驗證一次。

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

© 2026 ShiYu Huang (黃士育) and mAIjong contributors.

主程式（引擎、後端、訓練 pipeline、前端）採 Apache-2.0（`LICENSE`）；`sdk/`（maijong-sdk）採 MIT（`sdk/LICENSE`）。第三方依賴與字型的授權列在 `NOTICE`（`uv run python scripts/generate_notice.py` 重新產生）。

### 貢獻者協議

送出 Pull Request 即表示同意：
- 平台程式碼的貢獻以 Apache-2.0 授權提交；`sdk/` 內的貢獻以 MIT 授權提交。
- 貢獻者保留其貢獻的著作權，並授予 mAIjong 專案永久、不可撤銷的使用授權。
