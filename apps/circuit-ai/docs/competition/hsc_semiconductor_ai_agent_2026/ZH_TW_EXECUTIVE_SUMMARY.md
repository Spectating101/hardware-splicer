# Circuit.AI Hardware Splicer 摘要

## 專題名稱

Circuit.AI Hardware Splicer：以證據閘門為核心的電路板理解、維修、再利用與硬體重組 AI Agent。

## 專題簡介

Circuit.AI Hardware Splicer 不是單純的 PCB 圖片辨識工具，而是一個面向實體電路板的 AI Agent。系統會整合多張電路板照片、IC 標記、連接器資訊、公開資料表、量測腳位、電壓、電流、熱狀態與功能測試結果，建立可稽核的維修與再利用權限檔案。

此系統的重點是「不讓 AI 過度宣稱」。視覺模型可以協助找出元件、接頭與疑似可再利用功能，但不能直接授權上電、維修或拼接。只有在量測拓樸、電氣檢查、受控 bench test、release manifest 與證據附件完整後，系統才會提升到 scoped production repair authority。

## 解決問題

在電子維修、教學、硬體開發與回收再利用場景中，使用者常常拿到一片未知或資料不完整的電路板。即使 AI 能辨識部分元件，也不代表可以安全上電或重複利用。Circuit.AI 的目標是把「看起來可能可以用」轉換成「經過量測與測試，可以在明確範圍內使用」。

## 技術架構

系統包含：

- 多照片視覺證據擷取
- Qwen 或類似多模態模型輔助辨識
- 公開 pinout / datasheet 參考
- 電路拓樸假設
- bench measurement packet
- continuity / resistance / voltage / current / thermal 量測
- controlled bench outcome
- production authority casefile
- deterministic verifier 安全閘門

## 目前成果

目前已有可執行的 backend 與 frontend showcase：

```text
/showcase?state=release
```

展示結果：

- 只有參考資料時：`visual_candidate`，分數 `0.18`，不能授權維修。
- 完整 release evidence 時：`production_repair`，分數 `1.00`，可授權範圍限定的低電壓 UART 再利用。

## 七月至八月開發目標

若入選，補助 token 將用於：

- 多張電路板照片的視覺證據整合
- Qwen/native vision 實驗
- 真實或受控電路板案例集
- 量測流程 UI
- 中英文展示介面
- 最終 10 分鐘競賽展示

## 專題價值

本專題將 AI Agent 應用於半導體與電子硬體的實務流程：電路板理解、測試規劃、維修判斷、再利用與安全授權。它不只是聊天機器人，而是能把模型推論、實體量測與安全閘門整合成工程工作流程的系統。

