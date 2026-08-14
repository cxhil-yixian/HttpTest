"""把一個測試頁面的表單與結果表結構挖出來，存成 JSON。

itdog.cn 擋在 Cloudflare 人機驗證後面，自動化瀏覽器進不去。這支工具會把
瀏覽器開著等你手動點過「我不是機器人」，偵測到表單才繼續抓結構。

用法：
    python tools/probe_page.py https://www.itdog.cn/http/
    python tools/probe_page.py https://www.itdog.cn/http/ --ready "#host"
    python tools/probe_page.py https://www.tcptest.cn/http --wait 20

輸出：tools/probes/<頁面名>.json（結構）與同名 .html（完整原始碼）
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from busters.browser import make_driver   # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "probes"

DUMP = r"""
function attrs(el) {
  const o = {tag: el.tagName.toLowerCase()};
  for (const a of ['id','name','class','type','placeholder','value','onclick','multiple']) {
    const v = el.getAttribute(a);
    if (v) o[a] = v.length > 160 ? v.slice(0, 160) + '…' : v;
  }
  const t = (el.textContent || '').trim().replace(/\s+/g, ' ');
  if (t && t.length < 60 && ['button','a','label'].includes(o.tag)) o.text = t;
  return o;
}
return {
  title: document.title,
  url: location.href,
  hasJQuery: typeof window.jQuery !== 'undefined',
  stillChallenged: !!document.querySelector('[name=cf-turnstile-response]'),
  inputs: [...document.querySelectorAll('input,textarea,select')].map(attrs),
  selects: [...document.querySelectorAll('select')].map(s => ({
    id: s.id, name: s.getAttribute('name'), cls: s.className,
    multiple: s.multiple, optionCount: s.options.length,
    sample: [...s.options].slice(0, 10).map(o => ({value: o.value, text: o.text.trim()}))
  })),
  buttons: [...document.querySelectorAll('button,[onclick]')].slice(0, 40).map(attrs),
  tables: [...document.querySelectorAll('table')].slice(0, 6).map((t, i) => ({
    index: i, id: t.id, cls: t.className,
    headers: [...t.querySelectorAll('thead th, thead td')].map(x => x.textContent.trim()),
    tbodies: [...t.querySelectorAll('tbody')].map(tb => ({
      ariaLive: tb.getAttribute('aria-live'),
      ariaRelevant: tb.getAttribute('aria-relevant'),
      cls: tb.className,
      rowCount: tb.rows.length,
      firstRow: tb.rows[0] ? [...tb.rows[0].cells].map(c => ({
        cls: c.className,
        text: c.textContent.trim().slice(0, 80),
        html: c.innerHTML.slice(0, 400)
      })) : []
    }))
  }))
};
"""

CHALLENGED = "return !!document.querySelector('[name=cf-turnstile-response]');"


def slug(url: str) -> str:
    p = urlparse(url)
    raw = f"{p.netloc}{p.path}".strip("/")
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in raw) or "page"


def main() -> None:
    ap = argparse.ArgumentParser(description="挖出測試頁面的 DOM 結構")
    ap.add_argument("url")
    ap.add_argument("--ready", default=None,
                    help="表單載入完成的 CSS selector，例如 '#host'；不給就只等驗證消失")
    ap.add_argument("--wait", type=int, default=240,
                    help="等待人工通過驗證的上限秒數（預設 240）")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    driver = make_driver(headless=False)
    try:
        driver.get(args.url)
        print(f"已開啟 {args.url}", flush=True)

        deadline = time.time() + args.wait
        announced = False
        while time.time() < deadline:
            challenged = driver.execute_script(CHALLENGED)
            ready = (driver.execute_script(
                "return !!document.querySelector(arguments[0]);", args.ready)
                if args.ready else not challenged)
            if ready:
                print("頁面就緒", flush=True)
                break
            if challenged and not announced:
                announced = True
                print("\n⚠ 出現 Cloudflare 人機驗證。"
                      "\n  請到瀏覽器視窗點一下「我不是機器人」，"
                      f"\n  本工具會自動偵測並繼續（最多等 {args.wait} 秒）。\n", flush=True)
            time.sleep(2)
        else:
            print("等待逾時，仍然抓不到頁面內容", flush=True)

        data = driver.execute_script(DUMP)
        name = slug(args.url)
        (OUT_DIR / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT_DIR / f"{name}.html").write_text(driver.page_source, encoding="utf-8")

        print(f"\n標題: {data['title']}")
        print(f"仍被驗證擋住: {data['stillChallenged']}")
        print(f"jQuery: {data['hasJQuery']}")
        print(f"輸入元素: {len(data['inputs'])}  下拉選單: {len(data['selects'])}  "
              f"按鈕: {len(data['buttons'])}  表格: {len(data['tables'])}")
        print(f"\n已寫入 {OUT_DIR / (name + '.json')}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
