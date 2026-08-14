"""itdog.cn 單站測試的實地探測。

流程：開新分頁 → 導航到單站測試頁 → 等你手動通過 Cloudflare 驗證 →
填入網址 → 點快速測試 → 把表單與結果表的結構挖下來。

itdog.cn 擋在 Cloudflare 後面，自動化瀏覽器過不去，所以驗證那一步一定要人工。
本工具只負責偵測與等待，不做任何規避。

用法：
    python tools/itdog_single_probe.py
    python tools/itdog_single_probe.py https://example.com --wait 600
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from selenium.common.exceptions import (                            # noqa: E402
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)
from selenium.webdriver.common.by import By                          # noqa: E402

from busters.browser import make_driver                              # noqa: E402
from busters.itdog.challenge import CLICK_REQUIRED, detect           # noqa: E402

URL = "https://www.itdog.cn/http"
DEFAULT_TARGET = "https://fantestcxma01.jd24h.com"
OUT_DIR = Path(__file__).resolve().parent / "probes"
PROFILE = REPO_ROOT / ".chrome-profile"

# 表單結構
FORM_DUMP = r"""
function a(el) {
  const o = {tag: el.tagName.toLowerCase()};
  for (const k of ['id','name','class','type','placeholder','value','onclick']) {
    const v = el.getAttribute(k);
    if (v) o[k] = v.length > 120 ? v.slice(0, 120) + '…' : v;
  }
  const r = el.getBoundingClientRect();
  o.visible = r.width > 0 && r.height > 0;
  const t = (el.textContent || '').trim().replace(/\s+/g, ' ');
  if (t && t.length < 50) o.text = t;
  return o;
}
return {
  title: document.title,
  hasJQuery: typeof window.jQuery !== 'undefined',
  inputs: [...document.querySelectorAll('input,textarea,select')].map(a),
  selects: [...document.querySelectorAll('select')].map(s => ({
    id: s.id, name: s.getAttribute('name'), cls: s.className,
    multiple: s.multiple, count: s.options.length,
    sample: [...s.options].slice(0, 8).map(o => ({value: o.value, text: o.text.trim()}))
  })),
  buttons: [...document.querySelectorAll('button,a.btn,[onclick]')].slice(0, 40).map(a)
};
"""

# 結果表結構
RESULT_DUMP = r"""
return [...document.querySelectorAll('table')].slice(0, 6).map((t, i) => ({
  index: i, id: t.id, cls: t.className,
  headers: [...t.querySelectorAll('thead th, thead td')].map(x => x.textContent.trim()),
  bodies: [...t.querySelectorAll('tbody')].map(tb => ({
    ariaLive: tb.getAttribute('aria-live'),
    cls: tb.className,
    rowCount: tb.rows.length,
    rows: [...tb.rows].slice(0, 2).map(r => [...r.cells].map(c => ({
      cls: c.className,
      text: c.textContent.trim().slice(0, 90),
      html: c.innerHTML.slice(0, 400)
    })))
  }))
}));
"""

ROW_COUNT = ("return [...document.querySelectorAll('table')]"
             ".map(t => t.querySelectorAll('tbody tr').length);")


class BrowserClosed(RuntimeError):
    """瀏覽器在流程中途被關閉。"""


def save(name, obj):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def wait_for_form(driver, timeout):
    """等到 Cloudflare 驗證過關、頁面出現真正的表單為止。"""
    deadline = time.time() + timeout
    announced = set()
    while time.time() < deadline:
        try:
            s = detect(driver, None)
            # 攔截頁沒有可見的文字輸入框，出現就代表過了
            visible_inputs = driver.execute_script(
                "return [...document.querySelectorAll('input[type=text],textarea')]"
                ".filter(e => e.getBoundingClientRect().width > 0).length;")
        except (InvalidSessionIdException, NoSuchWindowException) as e:
            raise BrowserClosed(
                "瀏覽器在等待驗證的過程中被關掉了，連線中斷。\n"
                "  請重跑，並且在通過驗證之前不要關閉那個視窗或分頁"
                "（Selenium 的 session 會跟著最後一個視窗一起結束）。"
            ) from e
        if visible_inputs and not s["challenged"]:
            print(f"  ✅ 驗證已過，表單出現（可見輸入框 {visible_inputs} 個）", flush=True)
            return True
        if s["state"] not in announced:
            announced.add(s["state"])
            if s["state"] == CLICK_REQUIRED:
                print("\n  ⚠ 請到瀏覽器點一下「驗證您是人類」，我會自動偵測並繼續\n",
                      flush=True)
            else:
                print(f"  狀態：{s['state']}（{s['title'][:20]!r}）", flush=True)
        time.sleep(2)
    return False


def find_url_input(driver):
    """找填網址的輸入框。優先 #host，其次任何可見的文字輸入框。"""
    try:
        el = driver.find_element(By.ID, "host")
        if el.is_displayed():
            return el, "#host"
    except Exception:
        pass
    for el in driver.find_elements(By.CSS_SELECTOR, "input[type=text], textarea"):
        if el.is_displayed():
            ph = el.get_attribute("placeholder") or ""
            return el, f"可見輸入框 placeholder={ph[:30]!r}"
    return None, ""


def find_test_button(driver):
    """找測試按鈕。優先 onclick=check_form()，其次文字含「测试」。"""
    try:
        el = driver.find_element(By.XPATH, "//button[@onclick='check_form()']")
        if el.is_displayed():
            return el, "onclick=check_form()"
    except Exception:
        pass
    for el in driver.find_elements(By.CSS_SELECTOR, "button, a.btn"):
        text = (el.text or "").strip()
        if el.is_displayed() and ("测试" in text or "測試" in text):
            return el, f"文字={text!r}"
    return None, ""


def main():
    ap = argparse.ArgumentParser(description="itdog 單站測試實地探測")
    ap.add_argument("target", nargs="?", default=DEFAULT_TARGET, help="要測的網址")
    ap.add_argument("--wait", type=int, default=600, help="等待人工過驗證的上限秒數")
    ap.add_argument("--result-wait", type=int, default=120, help="等測試結果的上限秒數")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"設定檔目錄：{PROFILE}", flush=True)
    print("※ 通過驗證之前請不要關閉瀏覽器視窗或分頁", flush=True)
    driver = make_driver(headless=False, profile_dir=PROFILE)

    try:
        # 1. 開新分頁再導航
        print("\n[1] 開新分頁", flush=True)
        driver.switch_to.new_window("tab")
        print(f"[2] 導航到 {URL}", flush=True)
        driver.get(URL)

        # 2. 等人工過驗證
        print(f"[3] 等待通過 Cloudflare 驗證（最多 {args.wait} 秒）", flush=True)
        if not wait_for_form(driver, args.wait):
            driver.save_screenshot(str(OUT_DIR / "single_blocked.png"))
            print("\n❌ 逾時仍未通過驗證，中止", flush=True)
            return

        # 3. 挖表單結構
        form = driver.execute_script(FORM_DUMP)
        save("itdog_single_form.json", form)
        driver.save_screenshot(str(OUT_DIR / "single_form.png"))
        print(f"\n[4] 表單結構已存：標題={form['title'][:30]!r} "
              f"jQuery={form['hasJQuery']} 輸入={len(form['inputs'])} "
              f"下拉={len(form['selects'])} 按鈕={len(form['buttons'])}", flush=True)

        # 4. 填入網址
        box, how = find_url_input(driver)
        if box is None:
            print("❌ 找不到網址輸入框，只存結構後結束", flush=True)
            return
        box.clear()
        box.send_keys(args.target)
        print(f"[5] 已填入 {args.target}（用 {how}）", flush=True)

        # 5. 點測試
        button, bhow = find_test_button(driver)
        if button is None:
            print("❌ 找不到測試按鈕，只存結構後結束", flush=True)
            return
        driver.execute_script("arguments[0].click();", button)
        print(f"[6] 已點擊測試按鈕（{bhow}）", flush=True)

        # 6. 等結果
        print(f"[7] 等待結果（最多 {args.result_wait} 秒）", flush=True)
        deadline = time.time() + args.result_wait
        last = None
        steady = 0
        while time.time() < deadline:
            time.sleep(5)
            counts = driver.execute_script(ROW_COUNT)
            total = sum(counts) if counts else 0
            print(f"    各表列數 {counts}", flush=True)
            if total and total == last:
                steady += 1
                if steady >= 3:
                    break
            else:
                steady = 0
                last = total

        result = driver.execute_script(RESULT_DUMP)
        save("itdog_single_result.json", result)
        (OUT_DIR / "itdog_single_result.html").write_text(
            driver.page_source, encoding="utf-8")
        driver.save_screenshot(str(OUT_DIR / "single_result.png"))

        print("\n===== 結果表 =====", flush=True)
        for t in result:
            rows = sum(b["rowCount"] for b in t["bodies"])
            print(f"  table[{t['index']}] id={t['id']!r} 列數={rows} "
                  f"表頭={t['headers']}", flush=True)
        print(f"\n✅ 已寫入 {OUT_DIR}", flush=True)

    except BrowserClosed as e:
        print(f"\n❌ {e}", flush=True)
    except WebDriverException as e:
        print(f"\n❌ 瀏覽器操作失敗：{str(e).splitlines()[0]}", flush=True)
    finally:
        try:
            time.sleep(3)
            driver.quit()
        except WebDriverException:
            pass   # 視窗已經關了，沒什麼好收的


if __name__ == "__main__":
    main()
