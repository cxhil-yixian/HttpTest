"""tcptest.cn 批量測試（TCPing）。

量的是「端口通不通、延遲多少」，不是 HTTP 狀態碼——
結果是 1ms 這種延遲值或「响应超时」，不會有 200。

端口直接寫在每一行目標後面（1.2.3.4:443），比右側的預設端口欄可靠：
網站規則是「每行自帶端口優先，沒帶才用預設端口」。
"""

from typing import List, Sequence, Tuple

from ..browser import (
    await_placeholder,
    click_button,
    make_driver,
    set_value,
    wait_for,
)
from ..config import TcptestConfig
from ..data.records import ResultRecord
from .parser import parse_batch

INPUT_PLACEHOLDER = "每行一个"
START_BUTTON = "开始测试"
ATTEMPTS = 2   # React 偶爾漏收第一次輸入，給一次重試

# 頁面一載入就擺著一張示範結果表（www.qq.com 那些），所以完成判斷
# 必須確認第一列真的是我們送出的目標，不能只看「格子填滿了」。
_PROGRESS = r"""
const t = [...document.querySelectorAll('table')].find(
  x => x.querySelector('thead') && x.querySelector('thead').textContent.includes('检测目标'));
if (!t) return {rows: 0, filled: 0, total: 0, firstTarget: ''};
const rows = [...t.querySelectorAll('tbody tr')];
let filled = 0, total = 0;
rows.forEach(r => [...r.cells].slice(2).forEach(c => {
  total++; if (c.textContent.trim()) filled++;
}));
return {
  rows: rows.length,
  filled: filled,
  total: total,
  firstTarget: rows[0] && rows[0].cells[1] ? rows[0].cells[1].textContent.trim() : ''
};
"""


def build_targets(ips: Sequence[str], port: int) -> List[str]:
    """每個目標後面補上端口。已經自帶端口的原樣保留。"""
    out = []
    for ip in ips:
        ip = ip.strip()
        if not ip:
            continue
        head, sep, tail = ip.rpartition(":")
        out.append(ip if (sep and head and tail.isdigit()) else f"{ip}:{port}")
    return out


def run_batch(ips: Sequence[str], protocol: str, cfg: TcptestConfig,
              verbose: bool = True) -> Tuple[List[str], List[ResultRecord]]:
    """送出一批目標做 TCPing，回傳 (節點名稱清單, 結果紀錄)。

    節點名稱由網站隨機分配，必須從結果表頭讀回——每次執行可能都不一樣。
    """
    port = cfg.port_for(protocol)
    targets = build_targets(ips, port)
    if not targets:
        return [], []

    driver = make_driver(cfg.headless)
    try:
        driver.get(cfg.batch_url)

        textarea = await_placeholder(driver, INPUT_PLACEHOLDER, "textarea")
        if textarea is None:
            raise RuntimeError(f"在 {cfg.batch_url} 找不到目標輸入框")

        payload = "\n".join(targets)
        first = targets[0]

        def is_done(s: dict) -> bool:
            # 第一列必須是我們的目標（代表示範資料已被換掉），且格子全部回填
            return (s.get("firstTarget") == first
                    and s.get("total", 0) > 0
                    and s["filled"] == s["total"])

        def tick(s, left):
            if verbose:
                print(f"    {s.get('rows', 0)} 列，已回填 {s.get('filled', 0)}/"
                      f"{s.get('total', 0)} 格，剩餘等待 {left}s", flush=True)

        final = {}
        for attempt in range(1, ATTEMPTS + 1):
            set_value(driver, textarea, payload)
            if not click_button(driver, START_BUTTON):
                raise RuntimeError(f"找不到「{START_BUTTON}」按鈕")

            final = wait_for(
                probe=lambda: driver.execute_script(_PROGRESS),
                is_done=is_done,
                timeout=cfg.test_wait_time,
                on_tick=tick if verbose else None,
            )
            if is_done(final):
                break
            if verbose and attempt < ATTEMPTS:
                print(f"    第 {attempt} 次沒跑起來，重試…", flush=True)

        if final.get("firstTarget") != first:
            raise RuntimeError(
                f"重試 {ATTEMPTS} 次後結果表第一列仍是 "
                f"{final.get('firstTarget')!r}，不是送出的 {first!r}——"
                f"測試沒有真的執行，抓到的可能是網站的示範資料。"
            )

        html = driver.page_source
    finally:
        driver.quit()

    return parse_batch(html, protocol)
