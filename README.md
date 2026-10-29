# mAIjong 麥醬

**台灣十六張麻將的線上遊戲、AI 練習場與強化學習研究平台。**

和朋友開桌、與不同難度的 AI 對戰，從每一次出牌學習；也可以用同一套規則引擎訓練代理程式、重播牌局，並在固定牌譜上比較策略。介面以繁體中文為主，提供英文切換。

![麥醬大廳：快速配對、開桌與玩家進度](assets/screenshots/home.png)

> [!NOTE]
> 本專案實作的是**台灣十六張**玩法。台數與特殊規則依程式內的計分設定；不同地區的麻將慣例可能不同。

## 目錄

- [遊戲與產品](#遊戲與產品)
- [快速開始](#快速開始)
- [規則與系統架構](#規則與系統架構)
- [AI 與強化學習](#ai-與強化學習)
- [實驗與模型評估](#實驗與模型評估)
- [開發自己的代理程式](#開發自己的代理程式)
- [部署、設定與測試](#部署設定與測試)
- [授權與貢獻](#授權與貢獻)

## 遊戲與產品

### 從開桌到複盤

1. **開始遊戲**：在大廳快速配對，或建立私人房間、分享房間碼；空位可由 AI 補上。房間可設定回合數、每步時間與各座位的 AI 難度。
2. **看懂牌局**：PixiJS 牌桌呈現四人座位、牌河、牌牆與即時動作。WebSocket 同步吃、碰、槓、聽、胡等決策；斷線時可由電腦暫代，回來後接手。
3. **學習決策**：局內提示顯示向聽、有效進張、聽牌與危險牌；AI 教練提供課程、手牌分析、決策問答與引導對局。解說預設採本機模板，亦可設定相容的 LLM 服務。
4. **回顧與挑戰**：錄影與註解供複盤；情境練習、速度挑戰、防守練習，以及排行、賽季與社群 AI 競技場提供不同目標。玩家檔案記錄等級、任務與外觀；網站也提供 PWA 安裝、鍵盤操作與螢幕閱讀器提示。

![實際對局：四人牌桌、行動提示與牌局紀錄](assets/screenshots/table.png)

| 區域 | 能做什麼 |
| --- | --- |
| [大廳](frontend/app/page.tsx) | 快速配對、建立或加入房間、選擇 AI 與局數 |
| [AI 教練](frontend/app/tutor/page.tsx) | 8 堂課、引導對局、手牌分析與決策問答 |
| [單人練習](frontend/app/practice/page.tsx) | 55 個情境、速度挑戰與防守練習 |
| [實驗室](frontend/app/lab/page.tsx) | 啟動訓練、查看曲線、策略比較、模擬與錄影探索 |
| [社群 AI](frontend/app/agents/page.tsx) | 上傳代理程式、檢視驗證與競技成績 |
| [排行榜](frontend/app/leaderboard/page.tsx) | 賽季、挑戰與人類／AI 排位 |

![AI 教練：課程與練習入口](assets/screenshots/tutor.png)

### 遊戲規則的實作範圍

`engine/` 以一手牌為狀態機，處理發牌、補花、摸打、吃碰槓、宣告聽牌、過水、搶槓、胡牌與流局；`engine/score.py` 定義 39 個台型識別項目（`T00`–`T38`）與支付計算。預設計分為底 100 點、每台 50 點，可透過 `ScoringRules` 調整。規則包含莊家與連莊拉莊、花牌、海底及特殊胡牌時機。

引擎的核心介面 `apply_action(state, player, action)` 回傳新狀態與事件，不改動輸入狀態。固定亂數種子配合動作序列可以重播同一手，讓網站、訓練與驗證共用規則。向聽計算使用預先產生的查表資料（`engine/data/`）。

![單人練習：從真實牌局抽出的情境](assets/screenshots/practice.png)

## 快速開始

### 需求

- Python **3.12+**；建議使用 [uv](https://docs.astral.sh/uv/)
- Node.js **20+** 與 pnpm
- 本機開發可使用 SQLite，無須先啟動 PostgreSQL、Redis 或 S3

在專案根目錄執行：

~~~bash
uv sync --extra backend --extra ai
(cd frontend && pnpm install)
./scripts/dev.sh
~~~

開啟 [http://localhost:3000](http://localhost:3000)。後端在 [http://localhost:8000](http://localhost:8000)，健康檢查為 `/healthz`，互動 API 文件為 `/docs`。`scripts/dev.sh` 會啟動兩個服務；若只在本機瀏覽，可設定 `DEV_HOST=127.0.0.1`。

想先用終端機體驗規則引擎：

~~~bash
uv run python -m engine.cli play --seed 1
uv run python -m engine.cli watch --seed 3
~~~

只需後端與遊戲功能時，可安裝 `uv sync --extra backend`；訓練與模型推論需要 `ai` 額外套件。更多環境變數參考 [`.env.example`](.env.example)。

## 規則與系統架構

~~~mermaid
flowchart LR
    P["玩家瀏覽器<br/>Next.js / React / PixiJS"] <-->|"HTTP API / WebSocket"| B["FastAPI<br/>房間、教學、競技場、實驗室"]
    B --> E["純 Python 規則引擎<br/>局面、合法動作、台數與支付"]
    B --> A["AI 代理程式<br/>規則／搜尋／神經網路"]
    A --> E
    T["訓練與評估<br/>Gymnasium / PettingZoo"] --> E
    T --> A
    B --> DB[("SQLite / PostgreSQL")]
    B -. "選用" .-> R[("Redis")]
    B -. "選用" .-> S[("S3 相容儲存")]
    SDK["maijong-sdk"] --> E
    SDK --> B
~~~

| 目錄 | 職責 |
| --- | --- |
| `engine/` | 零執行期依賴的台灣十六張規則、向聽、台數與一手／整場狀態 |
| `ai/` | 特徵、代理程式、RL 環境、模型、訓練、自我對弈與評估 |
| `backend/` | FastAPI、WebSocket 房間、SQLAlchemy／Alembic、提示、錄影與競技場 |
| `frontend/` | Next.js 15、React 19、PixiJS 8、Zustand、Tailwind CSS 4 |
| `sdk/`、`packages/` | 對外代理程式 SDK 與可獨立安裝的規則引擎套件 |
| `scripts/`、`tests/` | 模擬與資料產生工具；引擎、AI、後端、SDK 與端對端測試 |

後端預設可使用 SQLite、程序內任務執行器與本機錄影儲存。需要跨實例房間恢復與發布訂閱時可接 Redis；持久化錄影可接 S3 相容儲存；實驗室背景工作可接 Celery。這些服務的設定入口集中在 [`.env.example`](.env.example) 與 [`docker-compose.yml`](docker-compose.yml)。

## AI 與強化學習

mAIjong 將**遊戲中的 AI 難度**與**研究用模型**分開管理。玩家看到的 Lv1 是隨機代理，Lv2–3 是不同溫度的規則代理；Lv4 可載入 DQN checkpoint，否則退回規則代理。Lv5 優先讀取 `checkpoints/level5.json` 的晉升紀錄，也可載入已選出的神經網路模型；目前專案內的晉升紀錄指向 **CEM 調參的規則代理**（`checkpoints/rule_cem_v1.json`）；PPO 等模型在此仍屬研究候選。詳見 [代理工廠](ai/agents/__init__.py) 與 [晉升紀錄](checkpoints/level5.json)。

### RL 問題定義

| 項目 | 單一學習座位 `MahjongEnv` |
| --- | --- |
| Episode | 一手牌；其餘三席由指定代理程式行動 |
| Observation | `tiles`：34 種牌 × 14 個通道；`scalars`：13 個局面數值 |
| Action | `Discrete(108)`，包含打牌與吃碰槓聽胡等編碼 |
| 合法性 | `info["legal_mask"]`／`action_masks()`，只在可行動作中選擇 |
| Reward | 依向聽、有效進張、花牌及終局結果計算；訓練預設採 `potential` preset |

`ai/env.py` 提供 Gymnasium API；`ai/marl/pettingzoo_env.py` 則提供四席皆可由代理控制的 PettingZoo AEC 環境，終局依各席支付分數給獎勵。編碼與合法動作遮罩和公開 SDK 共用，方便同一代理在訓練與提交時使用一致輸入。`potential` preset 以牌型品質的前後差與實際支付點數為主，避免只獎勵「進步」而讓策略重複拆牌刷分；`spec` preset 保留原始台數導向設計。細節見 [reward 實作](ai/reward.py)。

~~~mermaid
flowchart LR
    E["規則引擎<br/>新局與合法動作"] --> O["觀測編碼<br/>34×14 + 13"]
    O --> M["合法動作遮罩<br/>108 actions"]
    M --> P["策略／價值網路"]
    P --> D["選擇動作"]
    D --> E
    E --> W["終局支付與 shaping reward"]
    W --> U["PPO / DQN 更新"]
    U --> P
    P --> C["Checkpoint"]
    C --> V["同牌譜配對評估<br/>座位輪替"]
    V --> G["晉升為遊戲代理"]
~~~

### 訓練路線

專案提供多種可比較的策略，而非單一模型：

- **Behavior Cloning（BC）**：從規則代理對局建立監督資料，作為策略模型初始權重。
- **Dueling DQN**：經驗回放、Prioritized Experience Replay、N-step target，支援 noisy layers。
- **自寫 PPO**：自我對弈聯盟、規則代理混合對手、value 暖身與對初始策略的 KL 錨定。
- **SB3 MaskablePPO**：`sb3-contrib` 的合法動作遮罩、多程序環境、自我對弈與 BC 暖身。
- **搜尋與規則調參**：規則代理、搜尋代理、rollout Q、CEM 調參與模型投票也納入相同評估框架。

典型流程如下；較大的訓練會使用大量 CPU／記憶體，建議先用小規模參數確認管線：

~~~bash
# 1. 用規則代理產生帶完整動作紀錄的訓練資料
uv run python scripts/simulate_batch.py --agents rule rule rule rule -n 3000 \
  --save data/bc/rule_3k.jsonl.gz

# 2. 行為克隆
uv run python -m ai.training.bc_trainer --data data/bc/rule_3k.jsonl.gz \
  --out checkpoints/bc_v2.pt --epochs 30

# 3. 以 BC 權重啟動 PPO 自我對弈
uv run python -m ai.training.ppo_trainer --init checkpoints/bc_v2.pt \
  --out checkpoints/ppo_latest.pt --updates 300

# 可選：SB3 MaskablePPO 路線
uv run python -m ai.training.sb3_trainer --steps 2000000 --envs 8 \
  --bc-data data/bc/rule_3k.jsonl.gz --run sb3-mine
~~~

其他入口：`python -m ai.training.dqn_trainer`、`python -m ai.training.cem_tune`、`python -m ai.training.duplicate`。訓練指標會寫入 `runs/<名稱>/metrics.jsonl`，實驗室可直接讀取；設定 `WANDB_PROJECT` 可同步至 Weights & Biases。PettingZoo 最小迴圈：

~~~python
from ai.marl import env

game = env()
game.reset(seed=0)
for agent in game.agent_iter():
    obs, reward, terminated, truncated, info = game.last()
    action = None if terminated or truncated else int(obs["action_mask"].nonzero()[0][0])
    game.step(action)
~~~

![實驗室：既有 ppo-v8 訓練紀錄與指標曲線](assets/screenshots/lab.png)

## 實驗與模型評估

麻將的抽牌運氣與座位差異很大，因此模型比較使用**同副牌輪流坐四席**的配對設計。`ai.ladder` 的每個 block 讓四個代理在同一副牌上打四次；報告以 `lv3 = 1500` 為 Elo 錨點，並以 200 次 bootstrap 估計 95% 信賴區間。`ai.training.duplicate` 可在另外一批未參與搜尋的牌局上複驗候選模型。

~~~bash
uv run python -m ai.ladder play --pool default --blocks 20000 --out runs/ladder/main
uv run python -m ai.ladder report runs/ladder/main

# 換 seed，在新的牌局上做配對比較
uv run python -m ai.training.duplicate ppo:checkpoints/ppo_v7.pt \
  --baseline rule --hands 2000 --seed 123456
~~~

以下是倉庫內 [`runs/ladder/main/ratings.json`](runs/ladder/main/ratings.json) 的**歷史快照**（2026-10-30；49,710 blocks／198,840 手），不是每次執行即時更新的排名：

| 代理 | Elo（95% CI） | 每手相對淨得分（95% CI） | 胡牌率 |
| --- | ---: | ---: | ---: |
| `rule` | 1595（1589–1602） | +35.3（+31.7–+38.9） | 27.3% |
| `ppo_v7` | 1594（1587–1602） | +33.0（+29.2–+36.9） | 27.4% |
| `rollq` | 1592（1584–1601） | +29.0（+24.8–+33.3） | 26.4% |
| `cem_v1` | 1591（1585–1599） | +29.7（+25.6–+33.9） | 26.9% |
| `ppo_v8` | 1589（1583–1597） | +30.0（+26.2–+34.1） | 27.2% |
| `lv3` | 1500（錨點） | −44.8（−48.1–−41.1） | 15.6% |
| `random` | 1231（1224–1239） | −169.7（−171.6–−167.5） | 0.1% |

前段模型的區間大量重疊，不能僅依名次宣稱其中一個明顯較強。這份快照中的 `lv5` 名稱仍指**舊的**規則參數；當前正式 Lv5 對應 `cem_v1` 的晉升紀錄。CEM 候選在未見牌局上對舊 Lv5 的三批配對結果分別是 +2.9、+7.7、+8.4 點／手（共 36,000 副配對牌局，合併約 +6.3 ± 1.8）。重複在相同 seed 上調參會對牌局過擬合；新的結論應換 seed 再驗證。

## 開發自己的代理程式

`maijong-sdk` 定義觀測、合法動作、驗證與打包流程；`sdk/examples/` 有隨機、貪婪與 DQN／PPO 範例。最小代理：

~~~python
from maijong_sdk import Action, BaseAgent, Observation

class MyAgent(BaseAgent):
    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        return legal_actions[0]
~~~

在本倉庫的 `uv` 環境中可以評估並打包：

~~~bash
uv run python -m maijong_sdk.evaluate --agent my_agent.py:MyAgent \
  --opponent greedy --games 200
uv run python -m maijong_sdk.cli pack --agent my_agent.py:MyAgent \
  --name "My Bot v1"
uv run python -m maijong_sdk.cli validate submission.zip
~~~

將 `submission.zip` 上傳至網站的「社群 AI」，通過 10 手驗證後會進入競技場；封裝可包含 `model.pt`，額外需求僅允許 `torch` 與 `numpy`。SDK 可於 `sdk/` 獨立安裝，要求 Python 3.10+，詳見 [SDK 設定](sdk/pyproject.toml)。

## 部署、設定與測試

### Docker Compose

~~~bash
docker compose up -d --build
docker compose build sandbox  # 社群代理程式的隔離執行映像
docker compose down
~~~

Compose 會啟動 PostgreSQL、Redis、SeaweedFS S3、後端與前端；網站為 `localhost:3000`、API 為 `localhost:8000`、S3 為 `localhost:8333`。錄影預簽名連結使用 `S3_PUBLIC_ENDPOINT` 作為瀏覽器可到達的位址。正式部署至少應設定自己的 `SECRET_KEY`、`CORS_ORIGINS` 與儲存端點；完整項目見 [環境變數範例](.env.example)。

### 驗證

~~~bash
uv run pytest
uv run ruff check .
uv run mypy
(cd frontend && pnpm lint && pnpm typecheck && pnpm e2e)
~~~

測試涵蓋規則與計分、RL 環境與代理、後端房間／安全／錄影、SDK，以及 Playwright 瀏覽器對局。修改規則時，先跑 `tests/engine/`，並確認重播與支付結果一致。

## 授權與貢獻

© 2026 ShiYu Huang（黃士育）與 mAIjong contributors。平台程式碼採 [Apache-2.0](LICENSE)；`sdk/` 採 [MIT](sdk/LICENSE)。第三方依賴與字型授權見 [NOTICE](NOTICE)。

歡迎以 Issue 討論規則差異、模型與可重現的評估結果，或提交 Pull Request。提交平台程式碼的貢獻以 Apache-2.0 授權，`sdk/` 內貢獻以 MIT 授權；貢獻者保留著作權，並授予專案永久、不可撤銷的使用授權。
