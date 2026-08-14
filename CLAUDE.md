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

三個模組，全部放在共用套件 `busters/` 下。分界的核心規則：

- **ITDOG** (`busters/itdog/`) — 唯一知道 itdog.cn 的地方。`collector.py` 碰瀏覽器，
  `parser.py` 是純函式（HTML → `ResultRecord`），可以存一份 page_source 下來離線驗證。
  對外只暴露「一批 IP + 協議 → `ResultRecord` 清單」。
- **DATA** (`busters/data/`) — 檔案通道與報表排版。**不含任何網站知識。**
  排版知識（哪欄放 IP、HTTP 從哪欄開始）集中在 `report.py`。
- **GOOGLE** (`busters/google/`) — Sheets 讀寫。**不含任何網站知識，也不知道欄位怎麼排。**
  只認「欄位字母 + 起始列 + 二維陣列」，資料由 DATA 排好後送進來。

新增測試來源（例如 tcptest.cn）時只需新增 `busters/tcptest/`，DATA 與 GOOGLE 不動。

### 資料流

檔案是各階段唯一交接點，每一步都能單獨重跑：

```
Sheets ──google──> CDN_IP_list.txt ──itdog──> logs/*.txt ──data──> *.xlsx ──google──> Sheets
```

`ITDOG-busters/run_all.py` 只做編排，三個 `step_*` 函式對應上面三段。

### 關鍵不變式

- `logs/*.txt` 格式為「target 節點名 狀態」，HTTPS 的 target 帶 `https://` 前綴。
  `ResultRecord.target` 保留原始字串就是為了維持這個格式。
- 報表列順序依 `CDN_IP_list.txt` 的 IP 順序，且只輸出有測到結果的 IP——
  回寫 Sheets 時列號要對得上原本的 IP 欄。
- `config.yaml` 的 `itdog.nodes` 順序 = 報表欄位順序。增減節點只改這裡，
  `ReportLayout.width` 會自動跟著算。

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
