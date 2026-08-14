"""處理 itdog.cn 的 Cloudflare 人機驗證。

itdog.cn 現在擋在 Cloudflare Turnstile 後面，自動化瀏覽器一律停在
「正在執行安全驗證」，等再久也不會自己過——需要真人點一下
「我不是機器人」。

這裡的作法是把瀏覽器開著等你點，偵測到頁面上出現真正的表單元素
才繼續。不做任何規避或偽裝。
"""

import time
from typing import Optional

_PROBE = """
return {
  challenged: !!document.querySelector('[name=cf-turnstile-response]'),
  ready: !!document.querySelector(arguments[0])
};
"""


def wait_for_form(driver, ready_selector: str, timeout: int,
                  verbose: bool = True, poll: float = 2.0) -> bool:
    """等到頁面出現 ready_selector 指定的元素為止。

    ready_selector: 表單載入完成的判斷依據，例如批量頁的 '#host'。
    回傳是否成功等到；逾時回傳 False，由呼叫端決定怎麼處理。
    """
    deadline = time.time() + timeout
    announced = False

    while time.time() < deadline:
        state = driver.execute_script(_PROBE, ready_selector)
        if state["ready"]:
            if announced and verbose:
                print("    驗證已通過，繼續執行", flush=True)
            return True

        if state["challenged"] and not announced and verbose:
            announced = True
            print(
                "\n    ⚠ itdog.cn 出現 Cloudflare 人機驗證。\n"
                "      請在剛開啟的瀏覽器視窗點一下「我不是機器人」，\n"
                f"      腳本會自動偵測並繼續（最多等 {timeout} 秒）。\n",
                flush=True,
            )
        elif verbose and not announced:
            announced = True
            print("    等待頁面載入…", flush=True)

        time.sleep(poll)

    return False


def require_form(driver, ready_selector: str, timeout: int,
                 url: Optional[str] = None, verbose: bool = True) -> None:
    """等不到表單就直接失敗，不要讓後續程式碼對著驗證頁亂抓。"""
    if not wait_for_form(driver, ready_selector, timeout, verbose):
        where = f"（{url}）" if url else ""
        raise RuntimeError(
            f"等待 {timeout} 秒後仍看不到表單{where}。\n"
            f"itdog.cn 的 Cloudflare 驗證沒有通過——請確認瀏覽器視窗有開啟、\n"
            f"你有點到「我不是機器人」，或把 config.yaml 的 "
            f"itdog.challenge_wait 調大。\n"
            f"另外 headless 模式下無法人工點擊，itdog 請保持 headless: false。"
        )
