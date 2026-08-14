# HttpTest

批量測試 IP 從中國 ISP 節點的連線可用性，並與 Google Sheets 雙向同步。

目前有一個可用的測試來源：**ITDOG**（[itdog.cn](https://www.itdog.cn/batch_http/)）。
`TCPTEST-busters/` 是預留給 [tcptest.cn](https://www.tcptest.cn/http) 的位置。

## 架構

程式碼切成三個模組，放在共用套件 `busters/` 下：

| 模組 | 職責 | 知道什麼 |
|------|------|----------|
| **ITDOG** `busters/itdog/` | Selenium 操作 itdog.cn、解析結果頁 | 只知道 itdog.cn |
| **DATA** `busters/data/` | IP 清單、log 檔、Excel 報表、欄位排版 | 不知道任何網站 |
| **GOOGLE** `busters/google/` | Google Sheets 讀寫 | 不知道任何網站，也不知道欄位怎麼排 |

DATA 與 GOOGLE 完全不含網站知識，之後接 tcptest.cn 時只需新增 `busters/tcptest/`。

```
httptest/
├── config.yaml             # 結構性常數（節點、欄位、等待秒數）
├── .env                    # 部署設定與機密（Sheet ID、gid、憑證路徑）— 不進版控
├── service_account.json    # Google 憑證 — 不進版控，需自行放置
├── requirements.txt
├── busters/                # 共用套件
│   ├── config.py           # 載入 config.yaml + .env
│   ├── itdog/              # ITDOG 模組
│   │   ├── collector.py    #   Selenium 操作
│   │   └── parser.py       #   結果頁解析（純函式）
│   ├── data/               # DATA 模組
│   │   ├── records.py      #   ResultRecord 資料形狀
│   │   ├── ip_list.py      #   IP 清單讀寫、分批
│   │   ├── logs.py         #   log 檔讀寫、清除
│   │   └── report.py       #   報表排版、Excel 讀寫
│   └── google/             # GOOGLE 模組
│       └── sheets.py       #   Sheets 讀寫
├── ITDOG-busters/          # 應用層
│   ├── run_all.py          #   流程編排
│   ├── start.bat           #   排程進入點
│   ├── data/               #   CDN_IP_list.txt、inaccessible_table.xlsx
│   └── logs/               #   Group N - HTTP.txt / HTTPS.txt
└── TCPTEST-busters/        # 待建
```

### 資料流

檔案是各階段唯一的交接點，所以任何一步都能單獨重跑：

```
Google Sheets ──GOOGLE──> data/CDN_IP_list.txt
                              │
                          ITDOG（每 250 個 IP 一批，HTTP 與 HTTPS 各跑一次）
                              ↓
                          logs/Group N - {HTTP,HTTPS}.txt
                              │
                           DATA（依 IP 清單順序排版）
                              ↓
                          data/inaccessible_table.xlsx
                              │
                          GOOGLE（收 DATA 排好的二維陣列）
                              ↓
                        Google Sheets D4:H / L4:P
```

## 安裝

需求：Windows 10/11、Python 3.7+、Google Chrome。

```bash
pip install -r requirements.txt
cp .env.example .env        # 再填入實際值
```

Google Sheets 整合需要 Service Account：

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立專案
2. 啟用 **Google Sheets API** 與 **Google Drive API**
3. 建立 Service Account 並下載 JSON 金鑰
4. 金鑰改名為 `service_account.json` 放到專案根目錄（或改 `.env` 的 `GOOGLE_CREDENTIALS`）
5. 在 Google Sheets 把試算表分享給 Service Account 的 email

## 使用

```bash
cd ITDOG-busters

python run_all.py              # 完整流程：fetch → test → upload
python run_all.py fetch        # 只從 Sheets 同步 IP 清單
python run_all.py test         # 只跑測試並產出 Excel
python run_all.py upload       # 只把既有 Excel 回寫 Sheets
python run_all.py test upload  # 指定執行其中幾步
```

不使用 Google Sheets 時：手動編輯 `ITDOG-busters/data/CDN_IP_list.txt`（一行一個 IP），
執行 `python run_all.py test`，結果在 `data/inaccessible_table.xlsx`。

## 設定

### config.yaml

| 項目 | 說明 |
|------|------|
| `itdog.url` | 測試頁面網址 |
| `itdog.ip_split_count` | 每批 IP 數量，ITDOG 上限 250 |
| `itdog.test_wait_time` | 送出後固定等待秒數 |
| `itdog.headless` | 是否隱藏 Chrome 視窗 |
| `itdog.nodes` | 測試節點清單。順序即報表欄位順序，增減節點只需改這裡 |
| `data.clear_logs_before_run` | 開跑前是否清空 `logs/*.txt` |
| `data.report.*` | Excel 欄位起點：IP 在 C、HTTP 從 D、HTTPS 從 L |
| `google.*` | Sheets 的讀取欄、起始列、回寫欄 |

### .env

| 變數 | 說明 |
|------|------|
| `SHEET_ID` | 試算表 ID（從網址取得） |
| `WORKSHEET_GID` | 工作表 gid。工作表名稱每天變動，故用 gid 識別 |
| `GOOGLE_CREDENTIALS` | Service Account 金鑰路徑，相對路徑以專案根目錄為基準 |

## 排程

`start.bat` 會切到自己所在目錄再執行 `python run_all.py`，排程指令維持不變：

```batch
:: 建立每日 09:10 執行（需系統管理員身份）
schtasks /create /tn "ITDOG批量測試" /tr "cmd /c \"E:\Github\httptest\ITDOG-busters\start.bat\"" /sc daily /st 09:10 /f

schtasks /run    /tn "ITDOG批量測試"        :: 手動執行一次
schtasks /query  /tn "ITDOG批量測試"        :: 查看狀態
schtasks /change /tn "ITDOG批量測試" /st 10:30
schtasks /delete /tn "ITDOG批量測試" /f
```

## 已知限制

- `itdog.test_wait_time` 是固定等待而非輪詢完成狀態，IP 數接近 250 上限時可能在測試跑完前就抓頁面
- 每批測試會各自啟動一次 Chrome，一組 IP 需開關兩次瀏覽器
- 排程執行時電腦需開機

## 授權

MIT License
