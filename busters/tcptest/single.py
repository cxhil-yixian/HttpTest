"""tcptest.cn 單站測試。

一個網址，量它在上百個節點上的完整指標：
狀態碼、總耗時、DNS 解析、連接、響應、重定向。
"""

from typing import List, Tuple

from ..browser import (
    await_placeholder,
    click_button,
    make_driver,
    set_value,
    stabilizer,
    wait_for,
)
from ..config import TcptestConfig
from ..data.records import SiteProbe
from .parser import parse_single

INPUT_PLACEHOLDER = "example.com"
FAST_BUTTON = "快速测试"
SLOW_BUTTON = "缓慢测试"

# 這一頁在還沒測之前也擺著一整張示範結果表，所以要先記下原本的內容指紋，
# 等到指紋變了（示範資料被換掉）而且不再變動，才算測完。
_SIGNATURE = r"""
const t = [...document.querySelectorAll('table')].find(
  x => x.querySelector('thead') && x.querySelector('thead').textContent.includes('总耗时'));
if (!t) return {rows: 0, sig: ''};
const rows = [...t.querySelectorAll('tbody tr')];
return {
  rows: rows.length,
  sig: rows.slice(0, 5).map(r => r.textContent.trim()).join('|').slice(0, 400)
};
"""


def run_single(url: str, cfg: TcptestConfig, slow: bool = False,
               verbose: bool = True) -> Tuple[List[str], List[SiteProbe]]:
    """測一個網址，回傳 (欄位名稱, 每個節點一筆的量測)。

    slow=True 走「缓慢测试」，節點更多但耗時較長。
    """
    url = url.strip()
    if not url:
        raise ValueError("單站測試需要一個網址")

    driver = make_driver(cfg.headless)
    try:
        driver.get(cfg.single_url)

        box = await_placeholder(driver, INPUT_PLACEHOLDER, "input")
        if box is None:
            raise RuntimeError(f"在 {cfg.single_url} 找不到網址輸入框")

        set_value(driver, box, url)
        if (box.get_attribute("value") or "").strip() != url:
            raise RuntimeError("網址寫入輸入框後讀不回來，頁面可能還沒載入完成")

        # 先記下示範資料的指紋，才能判斷結果有沒有被換掉
        before = driver.execute_script(_SIGNATURE).get("sig", "")

        button = SLOW_BUTTON if slow else FAST_BUTTON
        if not click_button(driver, button):
            raise RuntimeError(f"找不到「{button}」按鈕")

        settled = stabilizer(rounds=2)

        def is_done(s: dict) -> bool:
            sig = s.get("sig", "")
            return bool(sig) and sig != before and settled(sig)

        def tick(s, left):
            if verbose:
                mark = "換新" if s.get("sig") and s["sig"] != before else "仍是示範資料"
                print(f"    {s.get('rows', 0)} 個節點（{mark}），剩餘等待 {left}s",
                      flush=True)

        final = wait_for(
            probe=lambda: driver.execute_script(_SIGNATURE),
            is_done=is_done,
            timeout=cfg.test_wait_time,
            on_tick=tick if verbose else None,
        )

        if not final.get("sig") or final["sig"] == before:
            raise RuntimeError(
                f"等待 {cfg.test_wait_time} 秒後結果表沒有變化——"
                f"測試沒有真的執行，抓到的可能是網站的示範資料。"
            )

        html = driver.page_source
    finally:
        driver.quit()

    return parse_single(html, url)
