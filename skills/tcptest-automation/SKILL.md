---
name: tcptest-automation
description: Use when driving tcptest.cn with a browser agent (Selenium/Playwright/CDP) — filling the domain or target field, clicking 快速测试 / 开始测试, or reading its result tables. Covers the input field going empty with a 未輸入URL / 请输入 error on submit, results that look right but are the site's built-in demo data, and node column names changing between runs.
---

# 自動化 tcptest.cn

## 概述

tcptest.cn 是 **React SPA**：沒有 id、沒有 name、沒有 jQuery、沒有 `<select>`。
定位只能靠 placeholder 文字、按鈕文字、表頭文字。

三個會讓自動化「看起來成功、其實失敗」的陷阱：

1. 直接寫 `.value` 填不進去，一提交欄位就變空並報「未輸入 URL」
2. 頁面**未測之前就顯示一整張示範結果表**，會被誤判成測試已完成
3. 節點每次隨機分配，欄位名稱不能寫死

## 兩個頁面

| 頁面 | 用途 | 輸入 | 送出按鈕 |
|---|---|---|---|
| `tcptest.cn/http` | 單站測速 | `input[type=text]`，placeholder 含 `example.com` | `快速测试`（或 `缓慢测试`） |
| `tcptest.cn/batch-tcping` | 批量 TCPing | `textarea`，placeholder 含 `每行一个` | `开始测试` |

批量量的是 **TCP 延遲**（`7ms` / `响应超时`），不是 HTTP 狀態碼。上限 256 個目標。

## 陷阱 1：欄位變空、報「未輸入 URL」

**症狀：** 填完看起來有值，一點「快速测试」欄位就空了，頁面顯示 `请输入` / `未輸入URL`。

**原因：** React 受控元件用內部 value tracker 追蹤值。直接指派 `.value` 只改 DOM，
**React 的 state 仍是空字串**。提交時 React 依 state 重繪，把欄位打回空值並判定沒輸入。
欄位不是被清空，是從來沒被填進去過。

實測結果：

| 方式 | 點擊後的 value | 錯誤 |
|---|---|---|
| `el.value = "..."` | `''` | `请输入` |
| 原生 setter + `input` 事件 | 完整保留 | 無 |
| 真實鍵盤事件（`send_keys` / `fill`） | 完整保留 | 無 |

**修法一（優先）：用真實鍵盤事件**

```python
box.clear()
box.send_keys("https://example.com")      # Selenium
# page.get_by_placeholder("example.com").fill("https://example.com")   # Playwright
```

**修法二（備援）：原生 setter + 手動送事件**

```javascript
const el = document.querySelector('input[type=text]');
const proto = el.tagName === 'TEXTAREA'
  ? window.HTMLTextAreaElement.prototype
  : window.HTMLInputElement.prototype;
Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
el.dispatchEvent(new Event('input',  {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
```

`Object.getOwnPropertyDescriptor(...).set.call()` 是關鍵——它繞過 React 覆寫的 setter，
讓 tracker 認為值變了，`input` 事件才會真的更新 state。

**填完一定要驗證：**

```python
assert (box.get_attribute("value") or "").strip() == target, "值沒寫進去"
```

**時序也要顧：** 元素出現 ≠ React 已掛載事件處理器。太早填一樣不會進 state。
等元素可見後再多等 2–3 秒，或直接改用會自動等待的 API。
`driver.implicitly_wait()` **不是 sleep**，只是設定全域逾時，別拿它當等待。

## 陷阱 2：抓到示範資料

**兩個頁面在還沒測之前就顯示一整張結果表**（`www.qq.com`、`www.163.com` 那些）。

- 單站頁一載入就有 **108 列**，測完還是 108 列
- 批量頁一載入就有 **5 列**，格子全滿

所以「列數變了」「格子填滿了」「數值不再變動」**全都不能當完成訊號**——
它們在你按下按鈕之前就已經成立。

**批量：比對第一列是不是你送出的目標**

```javascript
const t = [...document.querySelectorAll('table')].find(
  x => x.querySelector('thead')?.textContent.includes('检测目标'));
const rows = [...t.querySelectorAll('tbody tr')];
let filled = 0, total = 0;
rows.forEach(r => [...r.cells].slice(2).forEach(c => {
  total++; if (c.textContent.trim()) filled++;
}));
return {
  firstTarget: rows[0]?.cells[1]?.textContent.trim() ?? '',
  filled, total
};
// 完成 = firstTarget === 你送出的第一個目標 && total > 0 && filled === total
```

**單站：先記下示範資料的內容指紋，等它變了且穩定**

```javascript
const t = [...document.querySelectorAll('table')].find(
  x => x.querySelector('thead')?.textContent.includes('总耗时'));
return [...t.querySelectorAll('tbody tr')].slice(0, 5)
  .map(r => r.textContent.trim()).join('|').slice(0, 400);
// 完成 = 指紋 !== 點擊前的指紋 && 連續兩輪不再變動
```

**確認不到就報錯，不要寫入結果。** 靜默接受示範資料會產生看起來正常的假報表。

## 陷阱 3：節點每次隨機

同一批目標連續跑兩次會拿到完全不同的節點：

```
第一次：湖北襄阳 电信 | 山东济南 联通 | 山东济南 移动 | 中国香港 港澳台、海外
第二次：广西南宁2 电信 | 河南周口 联通 | 福建厦门 移动 | 加拿大蒙特利尔 港澳台、海外
```

**節點名一律從結果表頭讀回**（`headers[2:]`），不要寫死在設定裡。
同一次執行的 HTTP 那輪與 HTTPS 那輪也可能拿到不同節點，報表要兩區塊各自算欄位。

節點名**帶空格**（`湖北襄阳 电信`）。存成空白分隔的 log 時，解析要用
「第一段是目標、最後一段是狀態、中間全是節點名」，不能 `split(' ')[1]`——
那會把運營商當成狀態。

## 結果結構

**批量**：表頭 `序号 | 检测目标：端口 | <節點…>`，每格三個 div：

```html
<div class="font-semibold text-green-600">1ms</div>      <!-- 或 响应超时 -->
<div class="text-xs">响应IP：1.1.1.1:443</div>
<div class="text-xs">位置：澳大利亚</div>
```

目標欄含一顆快捷操作按鈕，取**第一個 span** 的文字才乾淨。

**單站**：表頭 `检测点 | 响应IP | IP位置 | 状态 | 总耗时 | 解析 | 连接 | 响应 | 重定向 | Head | 赞助商`。
`检测点` 是兩個 span（運營商徽章 + 地點），要合起來讀。
`赞助商` 是廣告、`Head` 是按鈕，都該丟掉。

## 批量的端口

端口寫在**每行目標後面**，比右側的預設端口欄可靠——
網站規則是「每行自帶端口優先，沒帶才用預設」：

```
1.2.3.4:80
example.com:443
```

## 常見錯誤

| 錯誤 | 後果 |
|---|---|
| `el.value = x` 填值 | 欄位變空 + 「未輸入 URL」 |
| 元素一出現就填 | React 未掛載，值寫不進 state |
| 拿 `implicitly_wait()` 當 sleep | 完全不會暫停，迴圈瞬間空轉 |
| 用列數判斷完成 | 抓到示範資料 |
| 用「數值穩定」判斷完成 | 示範資料一開始就是穩定的 |
| 節點名寫死在設定 | 下次執行全部對不上 |
| log 用 `split(' ')[1]` 取節點 | 節點名有空格，運營商被當成狀態 |
| 讀 IP 清單用 `utf-8` | 記事本／PowerShell 的 BOM 讓第一個目標失效 |

## 驗證方式

parser 全部寫成純函式，存一份 `page_source` 就能離線驗證，不必反覆打網站。
