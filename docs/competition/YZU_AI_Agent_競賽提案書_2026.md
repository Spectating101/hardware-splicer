# 元智大學欣銓半導體書院【AI Agent 實作競賽】提案書

**（請將本文件轉為 PDF 後，與授權同意書一併 Email 至企業書院：carrielee@saturn.yzu.edu.tw）**

---

## 一、基本資料

| 項目 | 內容 |
|------|------|
| **隊名** | （請填寫，例：Fab-Truth Agent Team） |
| **競賽主題** | **自訂主題（四）**：半導體產業周邊硬體製造準備度 AI 助理 |
| **Agent 名稱** | **Fab-Truth 硬體製造準備度 AI 助理** |
| **組員 1** | 姓名：＿＿＿＿＿＿　系所：＿＿＿＿＿＿　學號：＿＿＿＿＿＿　Email：＿＿＿＿＿＿ |
| **組員 2** | 姓名：＿＿＿＿＿＿　系所：＿＿＿＿＿＿　學號：＿＿＿＿＿＿　Email：＿＿＿＿＿＿（無則刪除） |
| **組員 3** | 姓名：＿＿＿＿＿＿　系所：＿＿＿＿＿＿　學號：＿＿＿＿＿＿　Email：＿＿＿＿＿＿（無則刪除） |
| **聯絡人** | ＿＿＿＿＿＿　電話：＿＿＿＿＿＿ |

---

## 二、Agent 任務說明

### 2.1 要解決的問題

半導體產業鏈下游與周邊系統（測試治具、開發板、工控原型、IoT 硬體）在進入打樣與量產前，常面臨以下痛點：

1. **連線與電氣安全錯誤**：零件湊齊不代表能安全上電或正確通訊。
2. **「看起來能出貨」的幻覺**：一般對話式 AI 容易自評「設計完成」，但缺乏 KiCad DRC、BOM、Gerber 等第三方可驗證證據。
3. **打樣浪費**：錯誤 Gerber 或不合格板子造成不必要的 NPI 成本（沉沒成本）。
4. **除錯困難**：失敗時缺少結構化案卷，無法稽核「卡在哪一關」。

本團隊欲打造一位 **可動手做事、可拒絕、可稽核** 的 AI 員工，而非僅回答問題的聊天機器人。

### 2.2 Agent 如何完成任務

**輸入：**

- 自然語言目標（例：「用土壤濕度感測與幫浦做澆水原型」）
- 或 **Salvage 零件清單**（例：ESP32、USB 5V 電源、繼電器模組等）
- 或 **模組／畫布節點**（編輯器圖形）

**處理流程：**

```
使用者意圖 / 零件清單
    → Task Router（判斷：salvage / scratch 組裝 / 標準 kit）
    → 自動連線與編譯（Python 引擎 + KiCad CLI）
    → 電氣安全 + DRC 驗證
    → 製造檢查（PCB / BOM / Gerber 一致性）
    → 輸出：可製造報告 或 結構化失敗案卷
```

**輸出（成功）：**

- `DESIGN_QUALITY.json`、KiCad PCB、BOM、Gerber 路徑
- `FABRICATION_INSPECTION.json`（誠實製造準備度評分）
- `honest_fabrication_ready = true` 時才允許進入製造流程

**輸出（失敗）：**

- HTTP 200 但 `ok: false`
- 結構化 `failure` 區塊：`type`、`stage`、`blockers`、`casefile_path`
- `COMPILE_CASEFILE.json` 供工程與管理端事後稽核

### 2.3 與半導體產業的關聯

欣銓科技等半導體 **測試與驗證** 環節重視 **可重現、可量測、可稽核**。本 Agent 將相同精神應用於 **硬體原型製造準備度**：

- 測試治具／開發板在投產前的 **DRC / BOM / Gerber 真實性**
- 降低錯誤打樣造成的 **成本與交期風險**
- 提供 **證據鏈** 而非主觀判斷

### 2.4 決賽 Demo 規劃（10 分鐘簡報 + 5 分鐘 Q&A）

| 段落 | 時間 | 內容 |
|------|------|------|
| 問題與價值 | 1.5 分 | NPI 風險、為何需要 Fab-Truth |
| 現場 Demo（成功） | 3 分 | 目標描述 → Agent 編譯 → KiCad DRC=0 → inspect_fab PASS |
| 現場 Demo（失敗） | 2 分 | 零件不足 → 結構化 failure + casefile 展示 |
| Harness 治理 | 2 分 | Router / Guardrails / Observability（見第三節） |
| Token 與成本 | 1 分 | 預設零 Token 的 deterministic 路徑 |
| 結語 | 0.5 分 | 商業價值與未來擴充 |

備援：預錄 3 分鐘螢幕操作影片，以防現場網路或 KiCad 環境異常。

---

## 三、Agent 治理（Harness）架構構想

本專案已實作 **單一編譯主幹（compose_dispatch）**，API、CLI、SDK、MCP 共用同一邏輯，避免「同一任務、不同入口、不同結果」。

### 3.1 架構總覽

```
┌─────────────────────────────────────────────────────────┐
│                    使用者 / MCP Client                   │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  Task Router（compose_dispatch）                         │
│  · salvage  │  scratch  │  canvas  │  netlist  │  kit  │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  Tools（MCP / API）                                      │
│  hs_plan_salvage │ hs_compose │ hs_inspect_fab           │
│  hs_engine_doctor │ hs_suggest_modules                    │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  Prove Engine（Python + KiCad CLI）                      │
│  圖編譯 → 電氣安全 → DRC → BOM / Gerber → 製造檢查       │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  Guardrails + Observability + Evaluation                 │
│  testing_mode 關閉 │ casefile │ CI verify-tier-c        │
└─────────────────────────────────────────────────────────┘
```

### 3.2 各元件說明

| Harness 元件 | 本專案實作 | 設計目的 |
|--------------|------------|----------|
| **Task Router** | `compose_dispatch()` | 依輸入類型分派至 salvage / scratch / canvas / netlist / catalog kit，單一路徑 |
| **Memory Manager** | `PROJECT_INTAKE.json`、compile casefile | 持久化結構化狀態，非無限聊天記憶 |
| **Tools** | MCP Server（`hardware_splicer.mcp_server`） | 標準化工具介面，供 Cursor / Agent 框架呼叫 |
| **Guardrails** | `testing_mode` 生產環境必須關閉；`honest_fabrication_ready` false 則阻擋製造；KiCad DRC 為權威 | 防止 Agent 或模型「自評過關」 |
| **Observability** | `COMPILE_CASEFILE.json`、`FABRICATION_INSPECTION.json`、`FUNCTIONAL_DELIVERY.json` | 失敗與成功皆可事後稽核 |
| **Evaluation** | `make verify-tier-c`、`verify-netlist-engine`、`verify-geometry`；pytest 回歸 | CI 確保 18 套 kit、18 組 netlist、3 組 geometry 快照不退步 |

### 3.3 失敗處理（Gate 3.9）

證明失敗時回傳 **HTTP 200 + 結構化 failure**，包含：

- `type`（例：`module_pick_failed`、`drc_failed`、`design_quality_failed`）
- `stage`、`blockers`、`casefile_path`、`attempts`

符合決賽評審「可預測、有邊界、可審核」之要求。

### 3.4 開發工具與框架（符合競賽規定）

| 類別 | 選用 |
|------|------|
| 允許模型 | OpenAI / Anthropic / Google（選用於 NL 模組挑選；核心 prove 不依賴 LLM） |
| Agent 框架 | Cursor Agent、MCP（Model Context Protocol）、自建 Python SDK |
| 編譯權威 | KiCad CLI DRC、自建 Python 引擎（Hardware-Splicer） |

---

## 四、Token 使用量說明與優化策略

### 4.1 設計原則：**預設不走 LLM**

本 Agent 的 **核心價值在 deterministic 編譯與 KiCad 驗證**，非文字生成。因此：

- **約 80–90% 任務路徑 Token 消耗為 0**（Python 引擎 + KiCad CLI）
- **LLM 僅在選用路徑啟用**：自然語言模組挑選、compose 失敗後可選重試（`QWEN_COMPOSE_RETRY`，可關閉）

### 4.2 預估 Token 消耗（單次任務）

| 路徑 | 是否使用 LLM | 預估 Token |
|------|--------------|------------|
| 標準 catalog kit 編譯 | 否 | 0 |
| Salvage 規劃（離線規則） | 否 | 0 |
| NL scratch compose（離線模組挑選） | 否 | 0 |
| NL compose + 可選 LLM 重試 | 是（可關） | 中（約 2k–8k，視模型與重試次數） |
| 決賽 Demo 彩排（10 次） | 混合 | 預估 < 50k tokens / 月 |

### 4.3 優化手段

1. **Offline-first**：`HARDWARE_SPLICER_OFFLINE_COMPOSE=1` 時完全使用規則式模組挑選
2. **Fail-fast**：DRC 或電氣安全失敗即停止，不無限重試
3. **Policy 集中**：`llm_policy.py` 統一管理何時允許 LLM
4. **快取與 Ledger**：文字 LLM 回應可快取，避免重複呼叫

### 4.4 七月、八月補助使用規劃

入圍後，預計將 **Token 採購補助** 用於：

- Cursor / 允許之 API（OpenAI、Anthropic 或 Google）訂閱或儲值
- 用途：**本 Agent 暑修開發、決賽 Demo 彩排、Harness 文件與簡報優化**
- 每月實報實銷上限 NT$6,000（依收據核銷）

---

## 五、產業價值與商業意義

### 5.1 財務／風險視角

| 傳統做法 | Fab-Truth Agent |
|----------|-----------------|
| 工程師手動連線、主觀判斷「應該能打樣」 | 自動編譯 + 第三方 DRC |
| 失敗後難追溯 | Casefile 完整記錄 |
| LLM 自評「可以製造」 | `honest_fabrication_ready` 需通過檔案級檢查 |

**價值主張：** 在投入打樣費用 **之前**，以可稽核方式回答「這塊板子是否真的準備好上產線？」

### 5.2 應用場景

- 半導體周邊 **測試治具、驗證板** 快速迭代
- 新創／實驗室 **Salvage 零件** 組裝原型
- 教學與競賽之 **可重現硬體 Agent** 示範

### 5.3 既有成果（技術成熟度）

本提案基於已運作之開源專案 **Hardware-Splicer**，具備：

- 18 套 catalog kit：KiCad DRC 全數通過（CI：`verify-engine`、`verify-tier-c`）
- 18 組 netlist 測試 fixture：general engine 路徑驗證
- 159 個模組庫、MCP 工具鏈、結構化失敗 payload
- 產品層級已達 **Tier C**（誠實製造門檻、KiCad 權威驗證）

暑修目標為 **競賽 Demo、中文簡報、Token 治理文件**，非從零開發。

---

## 六、實作時程（2026 年 7–8 月）

| 時程 | 工作項目 | 產出 |
|------|----------|------|
| **6 月底前** | 提案送件、入圍等待 | 本提案書、授權同意書 |
| **7 月第 1–2 週** | Demo 腳本定稿、MCP 路徑穩定 | 成功／失敗雙路徑可重現 |
| **7 月第 3–4 週** | 繁體中文簡報初稿、Token 使用紀錄表 | 10 頁簡報、收據整理 |
| **8 月** | 決賽彩排、Q&A 預演、備援影片 | 最終簡報、3 分鐘錄影 |
| **9/2** | 決賽（10+5 分鐘） | 現場報告 |

---

## 七、過去實作案例（選填）

- **專案名稱**：Hardware-Splicer（硬體編譯引擎 + Agent SDK + MCP）
- **角色**：獨立開發／維護
- **成果摘要**：
  - 統一 `compose_dispatch` 編譯主幹
  - MCP 工具：`hs_compose`、`hs_inspect_fab`、`hs_plan_salvage` 等
  - CI：`verify-tier-c`、`verify-netlist-engine`、`verify-geometry`
  - 前端 `/build` 已接 Python 引擎（KiCad 權威驗證）
- **與本競賽之關係**：本提案將既有引擎 **包裝為半導體周邊可稽核之 AI 員工**，並完成決賽所需之中文簡報與 Demo。

---

## 八、參考資料與附件（選填）

- 專案路徑：（請填寫 GitHub 或本機路徑，若可公開）
- 架構文件：`docs/ENGINE_DONE.md`、`docs/FLUX_TARGET.md`
- MCP 啟動：`PYTHONPATH=src python -m hardware_splicer.mcp_server`

---

## 九、聲明

本提案內容為組員自行創作，不侵害第三人智慧財產權。組員已閱讀並同意附件【授權同意書】內容，授權元智大學於教學、宣傳及合理範圍內使用競賽資料；本人仍保留非專屬之智慧財產權。

---

**組長簽名：**＿＿＿＿＿＿＿＿　　**日期：**　　2026 年　　月　　日

**組員簽名：**＿＿＿＿＿＿＿＿　　**日期：**　　2026 年　　月　　日

---

*（將本文件轉為 PDF，檔名建議：`YZU_AI_Agent_提案書_隊名.pdf`）*
