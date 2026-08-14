# HttpTest

批量測試 IP 從中國 ISP 節點的連線可用性，並與 Google Sheets 雙向同步。

兩個測試來源、兩種測試模式：

| | **batch** 批量測試 | **single** 單站測試 |
|---|---|---|
| **itdog** | [itdog.cn/batch_http](https://www.itdog.cn/batch_http/)<br>一批 IP → 各節點的 HTTP 狀態碼 | [itdog.cn/http](https://www.itdog.cn/http/)<br>*尚未實作，見下方說明* |
| **tcptest** | [tcptest.cn/batch-tcping](https://www.tcptest.cn/batch-tcping)<br>一批 IP → 各節點的 TCP 延遲 | [tcptest.cn/http](https://www.tcptest.cn/http)<br>一個網址 → 108 節點的完整指標 |

> **itdog.cn 目前需要人工過驗證。** 該站已改用 Cloudflare 人機驗證，自動化瀏覽器
> 開頁後會停在「正在執行安全驗證」，等再久也不會自己通過。程式會把瀏覽器開著
> 等你點一下「我不是機器人」，偵測到表單才繼續。因此 itdog 無法無人值守排程，
> 也不能用 headless 模式。tcptest.cn 沒有這個限制。

## 架構

程式碼切成模組，放在共用套件 `busters/` 下：

| 模組 | 職責 | 知道什麼 |
|------|------|----------|
| **ITDOG** `busters/itdog/` | 操作 itdog.cn、解析結果、處理人機驗證 | 只知道 itdog.cn |
| **TCPTEST** `busters/tcptest/` | 操作 tcptest.cn、解析結果 | 只知道 tcptest.cn |
| **DATA** `busters/data/` | IP 清單、log 檔、Excel 報表、欄位排版 | 不知道任何網站 |
| **GOOGLE** `busters/google/` | Google Sheets 讀寫 | 不知道任何網站，也不知道欄位怎麼排 |

DATA 與 GOOGLE 完全不含網站知識，兩個來源共用。再接第三個來源時只需新增
`busters/<來源>/`，這兩個模組不需更動。

```
HttpTest/
├── config.yaml             # 結構性常數（節點、欄位、埠、等待秒數）
├── .env                    # 部署設定與機密（Sheet ID、gid、憑證路徑）— 不進版控
├── service_account.json    # Google 憑證 — 不進版控，需自行放置
├── requirements.txt
├── busters/                # 共用套件
│   ├── config.py           # 載入 config.yaml + .env
│   ├── modes.py            # single / batch 兩種模式的定義
│   ├── browser.py          # 共用的瀏覽器操作（等待、輸入、點擊）
│   ├── itdog/              # ITDOG 模組
│   │   ├── collector.py    #   Selenium 操作
│   │   ├── challenge.py    #   Cloudflare 人機驗證的等待
│   │   └── parser.py       #   結果頁解析（純函式）
│   ├── tcptest/            # TCPTEST 模組
│   │   ├── batch.py        #   批量 TCPing
│   │   ├── single.py       #   單站測速
│   │   └── parser.py       #   結果表解析（純函式）
│   ├── data/               # DATA 模組
│   │   ├── records.py      #   ResultRecord / SiteProbe 資料形狀
│   │   ├── ip_list.py      #   IP 清單讀寫、分批
│   │   ├── logs.py         #   log 檔讀寫、清除
│   │   └── report.py       #   報表排版、Excel 讀寫
│   └── google/             # GOOGLE 模組
│       └── sheets.py       #   Sheets 讀寫
├── tools/
│   └── probe_page.py       # 挖測試頁面 DOM 結構（會等你過人機驗證）
├── ITDOG-busters/          # itdog 應用層
│   ├── run_all.py          #   fetch / test / upload
│   ├── start.bat           #   排程進入點
│   ├── data/ └ logs/
└── TCPTEST-busters/        # tcptest 應用層
    ├── run_all.py          #   batch / single
    └── data/ └ logs/
```

### 資料流

檔案是各階段唯一的交接點，所以任何一步都能單獨重跑：

```
Google Sheets ──GOOGLE──> data/CDN_IP_list.txt
                              │
                        ITDOG 或 TCPTEST（分批，HTTP 與 HTTPS 各跑一輪）
                              ↓
                          logs/Group N - {HTTP,HTTPS}.txt
                              │
                           DATA（依 IP 清單順序排版）
                              ↓
                          data/*.xlsx
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

### itdog（批量，需人工過驗證）

```bash
cd ITDOG-busters

python run_all.py              # 完整流程：fetch → test → upload
python run_all.py fetch        # 只從 Sheets 同步 IP 清單
python run_all.py test         # 只跑測試並產出 Excel
python run_all.py upload       # 只把既有 Excel 回寫 Sheets
```

跑到 `test` 時會開啟 Chrome，若出現 Cloudflare 驗證，終端機會提示你去點一下。

### tcptest（批量 / 單站，全自動）

```bash
cd TCPTEST-busters

python run_all.py batch                        # 批量 TCPing，80 埠與 443 埠各跑一輪
python run_all.py single www.example.com       # 單站測速
python run_all.py single www.example.com --slow  # 改走「缓慢测试」，節點更多
```

本流程不碰 Google Sheets，結果留在 `data/`：

- `data/tcping_table.xlsx` — 批量結果矩陣
- `data/single_<網址>.xlsx` — 單站的 108 節點完整明細

## 設定

### config.yaml

| 項目 | 說明 |
|------|------|
| `itdog.batch_url` / `itdog.single_url` | 兩種模式的頁面網址 |
| `itdog.ip_split_count` | 每批 IP 數量，ITDOG 上限 250 |
| `itdog.test_wait_time` | 送出後固定等待秒數 |
| `itdog.challenge_wait` | 等待人工通過 Cloudflare 驗證的上限秒數 |
| `itdog.nodes` | 測試節點清單。順序即報表欄位順序 |
| `tcptest.batch_url` / `tcptest.single_url` | 兩種模式的頁面網址 |
| `tcptest.ip_split_count` | 每批目標數量，網站上限 256 |
| `tcptest.ports.http` / `.https` | TCPing 用的埠，預設 80 / 443 |
| `data.clear_logs_before_run` | 開跑前是否清空 `logs/*.txt` |
| `data.report.*` | Excel 欄位起點：IP 在 C、HTTP 從 D、HTTPS 從 L |
| `google.*` | Sheets 的讀取欄、起始列、回寫欄 |

### .env

| 變數 | 說明 |
|------|------|
| `SHEET_ID` | 試算表 ID（從網址取得） |
| `WORKSHEET_GID` | 工作表 gid。工作表名稱每天變動，故用 gid 識別 |
| `GOOGLE_CREDENTIALS` | Service Account 金鑰路徑，相對路徑以專案根目錄為基準 |

## 兩個來源的實質差異

不是換個網址就好，資料本身不同：

1. **itdog 量 HTTP 狀態碼**（`200`、`无法访问`），**tcptest 批量量 TCP 延遲**
   （`7ms`、`响应超时`）。前者測「網頁回不回得來」，後者測「端口通不通」。
2. **itdog 的節點固定**，由 `config.yaml` 指定節點 ID；**tcptest 的節點每次隨機分配**
   （這次「浙江宁波 电信」、下次「江西南昌 联通」），只能從結果表頭讀回。
   所以 tcptest 的報表欄位是跑完才決定的，HTTP 與 HTTPS 兩輪甚至會拿到不同節點。
3. **tcptest 兩個頁面在還沒測之前就擺著一整張示範結果表**（www.qq.com 那些）。
   程式的完成判斷會確認表格裡是你送出的目標，確認不到就報錯而不是寫入假資料。

## 排程

`start.bat` 會切到自己所在目錄再執行 `python run_all.py`：

```batch
:: 建立每日 09:10 執行（需系統管理員身份）
schtasks /create /tn "ITDOG批量測試" /tr "cmd /c \"E:\Github\HttpTest\ITDOG-busters\start.bat\"" /sc daily /st 09:10 /f

schtasks /run    /tn "ITDOG批量測試"        :: 手動執行一次
schtasks /query  /tn "ITDOG批量測試"        :: 查看狀態
schtasks /change /tn "ITDOG批量測試" /st 10:30
schtasks /delete /tn "ITDOG批量測試" /f
```

> itdog 需要人工點驗證，排程執行時若沒人在電腦前會卡住等到逾時。
> 要無人值守請改用 tcptest。

## 已知限制

- **itdog.cn 的 Cloudflare 驗證需人工點擊**，無法無人值守、不能用 headless
- `itdog.test_wait_time` 是固定等待而非輪詢完成狀態，IP 數接近 250 上限時可能提早抓頁面
- 每批測試會各自啟動一次 Chrome，一組 IP 需開關兩次瀏覽器
- **tcptest 尚未固定節點**：網站有「节点选择」可以指定，目前程式沒用它，
  所以每次拿到的節點都不同，跨日資料無法逐欄比較
- itdog 的 single 模式尚未實作——該頁被驗證擋著，還沒取得 DOM 結構。
  取得方式：`python tools/probe_page.py https://www.itdog.cn/http/`，
  手動過驗證後結構會存到 `tools/probes/`

## 授權

MIT License
