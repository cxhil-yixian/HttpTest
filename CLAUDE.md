# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python automation that batch-tests HTTP/HTTPS reachability of IP addresses from Chinese ISP nodes,
and syncs the results with Google Sheets. Currently one working source: ITDOG (itdog.cn).
`TCPTEST-busters/` is a placeholder for tcptest.cn.

## Commands

```bash
pip install -r requirements.txt      # 安裝依賴（根目錄）
cp .env.example .env                 # 建立部署設定

cd ITDOG-busters
python run_all.py                    # 完整流程
python run_all.py fetch              # Sheets → data/CDN_IP_list.txt
python run_all.py test               # IP 清單 → logs → Excel
python run_all.py upload             # Excel → Sheets
```

排程管理：

```batch
schtasks /run    /tn "ITDOG批量測試"
schtasks /query  /tn "ITDOG批量測試"
schtasks /delete /tn "ITDOG批量測試" /f
```

## Architecture

模組全部放在共用套件 `busters/` 下。分界的核心規則：

- **ITDOG** (`busters/itdog/`) — 唯一知道 itdog.cn 的地方。`collector.py` 碰瀏覽器，
  `challenge.py` 處理 Cloudflare 人機驗證，`parser.py` 是純函式（HTML → `ResultRecord`）。
- **TCPTEST** (`busters/tcptest/`) — 唯一知道 tcptest.cn 的地方。`batch.py` 是批量
  TCPing、`single.py` 是單站測速、`parser.py` 純函式。
- **DATA** (`busters/data/`) — 檔案通道與報表排版。**不含任何網站知識。**
- **GOOGLE** (`busters/google/`) — Sheets 讀寫。**不含任何網站知識，也不知道欄位怎麼排。**
  只認「欄位字母 + 起始列 + 二維陣列」，資料由 DATA 排好後送進來。

再接第四個來源時只需新增 `busters/<來源>/`，DATA 與 GOOGLE 不動。

### 資料流

檔案是各階段唯一交接點，每一步都能單獨重跑：

```
Sheets ──google──> CDN_IP_list.txt ──itdog──> logs/*.txt ──data──> *.xlsx ──google──> Sheets
```

`ITDOG-busters/run_all.py` 只做編排，三個 `step_*` 函式對應上面三段。

### 關鍵不變式

踩過的坑，改動前先讀：

- `logs/*.txt` 格式為「target 節點名 狀態」。解析時**第一段是 target、最後一段是
  status、中間全是節點名**——不能寫 `split(' ')[1]`，tcptest 的節點名帶空格
  （「湖北襄阳 电信」），那樣會把運營商當成狀態。
- itdog 的 HTTPS log target 帶 `https://` 前綴，tcptest 的 target 帶 `:port` 後綴。
  `ResultRecord.ip` 一律是去掉兩者的純 IP（`bare_ip()`），報表比對只用它。
- 讀 IP 清單與 log 一律用 **utf-8-sig**。記事本、Excel、PowerShell 的 `Out-File`
  都會寫 BOM，用 utf-8 讀會讓第一個 IP 變成 `﻿1.2.3.4`，送到測試網站直接失效。
- **tcptest 兩個頁面在還沒測之前就顯示一整張示範結果表。** 完成判斷必須確認
  表格內容是我們送出的目標（批量比對第一列、單站比對內容指紋），只看「數值不再
  變動」會立刻被示範資料騙過去。確認不到要報錯，不要寫入假資料。
- **tcptest 是 React SPA**，值要用 `send_keys` 這種真實事件寫入。原生 setter 寫得進
  DOM 但元件未掛載時 React state 不會更新，表單看起來有值、送出去是空的。
  `driver.implicitly_wait()` 不是 sleep，別拿它當等待。
- 報表列順序依 `CDN_IP_list.txt` 的 IP 順序，且只輸出有測到結果的 IP——
  回寫 Sheets 時列號要對得上原本的 IP 欄。
- itdog 的節點固定在 `config.yaml`，順序 = 報表欄位順序。
  **tcptest 的節點每次隨機**，只能從結果表頭讀回，所以走
  `generate_dynamic_report()`（HTTP 與 HTTPS 兩區塊各自算欄位）而非
  `generate_report()`。

## Configuration

所有常數集中在兩個檔案，不要再散回程式碼裡：

- **config.yaml** — 節點清單、Excel/Sheets 欄位起點、批次大小、等待秒數、是否清 log
- **.env** — `SHEET_ID`、`WORKSHEET_GID`、`GOOGLE_CREDENTIALS`（不進版控）

`busters/config.py` 負責載入，回傳 `AppConfig`。欄位字母與索引的轉換用
`column_index()` / `column_letter()`，不要手寫魔術數字。

## Notes

- 專案無自動化測試。改動 DATA 模組後，可用既有 `logs/*.txt` 重新產出 Excel
  跟前一版逐格比對來驗證。
- `itdog.test_wait_time` 是固定等待而非輪詢，IP 數接近 250 上限時可能抓到未跑完的頁面。
