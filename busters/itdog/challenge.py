"""偵測並等待 itdog.cn 的 Cloudflare 人機驗證。

itdog.cn 現在擋在 Cloudflare 後面，自動化瀏覽器開頁會停在「請稍候…」，
等再久也不會自己過——需要真人點一下「我不是機器人」。

這裡只做「偵測 + 等你點完」，不做任何規避、偽裝或代點。
偵測不能只看單一標記：cf-turnstile-response 這個 input 是 widget 動態插入的，
驗證重試時會消失，只看它會在還被擋著的時候誤判成「已通過」。
"""

import time
from typing import Optional

# 就緒 / 需要人工點擊 / Cloudflare 自動驗證中 / 還在載入
READY = "ready"
CLICK_REQUIRED = "click_required"
RUNNING = "running"
LOADING = "loading"

_PROBE = r"""
const sel = arguments[0];
const frames = [...document.querySelectorAll('iframe')]
  .map(f => f.getAttribute('src') || '')
  .filter(s => s.includes('challenges.cloudflare.com'));
return {
  ready: sel ? !!document.querySelector(sel) : false,
  cfOpt: typeof window._cf_chl_opt !== 'undefined',
  errText: !!document.querySelector('#challenge-error-text'),
  turnstile: !!document.querySelector('[name=cf-turnstile-response]'),
  widgetFrames: frames.length,
  title: document.title || ''
};
"""

# 攔截頁的標題（依瀏覽器語系而異）
_WAIT_TITLES = ("請稍候", "请稍候", "Just a moment", "稍等片刻")


def detect(driver, ready_selector: Optional[str] = None) -> dict:
    """回傳目前頁面的驗證狀態。

    state 為 READY / CLICK_REQUIRED / RUNNING / LOADING 之一，
    另附各項原始標記供除錯。
    """
    raw = driver.execute_script(_PROBE, ready_selector)

    title = raw.get("title", "")
    waiting_title = any(t in title for t in _WAIT_TITLES)
    challenged = bool(raw["cfOpt"] or raw["errText"] or raw["turnstile"] or waiting_title)

    if raw["ready"]:
        state = READY
    elif raw["widgetFrames"]:
        # Turnstile 的互動式核取方塊是跨網域 iframe，出現就代表在等人點
        state = CLICK_REQUIRED
    elif challenged:
        state = RUNNING
    else:
        state = LOADING

    return {**raw, "state": state, "challenged": challenged}


def wait_for_form(driver, ready_selector: str, timeout: int,
                  verbose: bool = True, poll: float = 2.0) -> bool:
    """等到頁面出現 ready_selector 指定的元素為止。

    ready_selector: 表單載入完成的判斷依據，例如批量頁的 '#host'。
    回傳是否等到；逾時回傳 False，由呼叫端決定怎麼處理。
    """
    deadline = time.time() + timeout
    announced = set()

    while time.time() < deadline:
        s = detect(driver, ready_selector)

        if s["state"] == READY:
            if announced and verbose:
                print("    驗證已通過，繼續執行", flush=True)
            return True

        if verbose and s["state"] not in announced:
            announced.add(s["state"])
            if s["state"] == CLICK_REQUIRED:
                print("\n    ⚠ 請到瀏覽器視窗點一下「我不是機器人」，"
                      f"腳本會自動偵測並繼續（最多等 {timeout} 秒）。\n", flush=True)
            elif s["state"] == RUNNING:
                print("    Cloudflare 驗證中…（實測自動化視窗多半不會給出核取方塊，"
                      "只會一直停在「正在執行安全驗證」）", flush=True)
            else:
                print("    等待頁面載入…", flush=True)

        time.sleep(poll)

    return detect(driver, ready_selector)["state"] == READY


def require_form(driver, ready_selector: str, timeout: int,
                 url: Optional[str] = None, verbose: bool = True) -> None:
    """等不到表單就直接失敗，不要讓後續程式碼對著驗證頁亂抓。"""
    if wait_for_form(driver, ready_selector, timeout, verbose):
        return

    final = detect(driver, ready_selector)
    where = f"（{url}）" if url else ""
    raise RuntimeError(
        f"等待 {timeout} 秒後仍看不到表單{where}，目前狀態：{final['state']}。\n"
        f"標記：cfOpt={final['cfOpt']} errText={final['errText']} "
        f"turnstile={final['turnstile']} 驗證框={final['widgetFrames']} "
        f"標題={final['title']!r}\n"
        f"itdog.cn 的 Cloudflare 驗證沒有通過。\n"
        f"若狀態一直是 running 且驗證框=0，代表 Cloudflare 根本沒在這個自動化視窗\n"
        f"渲染核取方塊——沒有東西可以點，把 challenge_wait 調大也沒用。\n"
        f"可行做法是讓 Selenium 沿用你平常那個已通過驗證的 Chrome 設定檔\n"
        f"（--user-data-dir），或改用沒有這道關卡的 tcptest 來源。"
    )
