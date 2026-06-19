# 決賽簡報大綱（10 分鐘 + 5 分鐘 Q&A）

**Agent 名稱：** Fab-Truth 硬體製造準備度 AI 助理
**主題：** 自訂主題（四）— 半導體周邊硬體製造準備度

---

## Slide 1 — 封面
- 隊名、組員、系所
- Agent 名稱、競賽主題
- 一句話：*「能動手編譯、能誠實拒絕的硬體製造 AI 員工」*

## Slide 2 — 問題（為什麼需要）
- 打樣前常不知道板子是否真的可製造
- 一般 AI 容易「說可以」，缺乏 KiCad / Gerber 證據
- 半導體周邊：測試治具、開發板、原型 → NPI 成本風險

## Slide 3 — Agent 任務（做什麼）
- 輸入：目標描述 / Salvage 零件 / 模組清單
- 輸出：DRC + 製造檢查 PASS，或結構化失敗 + casefile
- 流程圖（一頁）

## Slide 4 — 現場 Demo：成功案例
- 操作：`hs_compose` 或 MCP 等價呼叫
- 顯示：DRC=0、`honest_fabrication_ready`
- 時間盒：3 分鐘

## Slide 5 — 現場 Demo：失敗案例
- 零件不足或故意錯誤輸入
- 顯示：`failure` JSON + `COMPILE_CASEFILE.json`
- 強調：不是 crash，是 **可審核的拒絕**

## Slide 6 — Harness 治理（30% 評分重點）
- Task Router：`compose_dispatch`
- Tools：MCP 工具列表
- Guardrails：testing_mode 關閉、KiCad 權威
- Observability：casefile、FABRICATION_INSPECTION
- Evaluation：CI verify-tier-c

## Slide 7 — Token 使用（20% 評分重點）
- 預設路徑：0 Token（Python + KiCad）
- LLM 僅選用：模組挑選 / 重試
- 七月八月實報：Cursor / API 收據
- 圖表：各路徑 Token 估算

## Slide 8 — 產業價值
- 財務語言：減少錯誤 Gerber 沉沒成本
- 半導體周邊：測試治具、驗證板
- 與欣銓文化：可重現、可稽核

## Slide 9 — 技術成熟度
- 18 kit / 18 netlist / 3 geometry 快照
- 159 模組庫、Tier C 已達
- 暑修：Demo + 簡報，非從零

## Slide 10 — 結語 & Q&A
- 我們賣的不是聊天，是 **證據鏈**
- 聯絡方式、QR（可選）

---

## Q&A 預想問題

1. **和 ChatGPT 差在哪？** → 我們用 KiCad DRC 當權威，失敗寫 casefile。
2. **為什麼算半導體？** → 測試治具與驗證板在產業鏈下游，製造準備度是共同痛點。
3. **Token 怎麼控？** → 預設 deterministic，LLM 可關。
4. **財系為什麼做這個？** → 風險與稽核視角，Harness 與成本表是強項。
