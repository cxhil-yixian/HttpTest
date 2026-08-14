"""共用的瀏覽器操作工具。

tcptest.cn 是 React SPA——沒有 id、沒有 name、沒有 jQuery，
只能靠 placeholder 文字、按鈕文字、表頭文字定位，而且值必須用
原生 setter + input 事件寫入，否則 React 的 state 不會更新。
"""

import time
from pathlib import Path
from typing import Callable, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# 用原生 setter 寫值再手動送出 input 事件，React 才會收到變更
_REACT_SET_VALUE = """
const el = arguments[0], value = arguments[1];
const proto = el.tagName === 'TEXTAREA'
  ? window.HTMLTextAreaElement.prototype
  : window.HTMLInputElement.prototype;
Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
el.dispatchEvent(new Event('input', {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
"""


def make_driver(headless: bool = False, window: str = "1500,1100",
                profile_dir=None) -> webdriver.Chrome:
    """建立 Chrome。

    profile_dir: 指定後會用這個目錄當瀏覽器設定檔，cookie 與 session 跨次保留。
    預設每次都是全新的拋棄式設定檔，代表上一次通過的人機驗證不會被記住，
    每跑一次就得重驗一次。用專屬目錄（不是你平常那個 Chrome 設定檔）可以
    避免佔用你正在用的瀏覽器。
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--window-size={window}")

    if profile_dir:
        profile_dir = Path(profile_dir)
        profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir.resolve()}")

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def find_by_placeholder(driver, fragment: str, tag: str = "input"):
    """用 placeholder 的一段文字找輸入框。"""
    for el in driver.find_elements(By.TAG_NAME, tag):
        if fragment in (el.get_attribute("placeholder") or ""):
            return el
    return None


def await_placeholder(driver, fragment: str, tag: str = "input",
                      timeout: int = 30, interval: float = 1.0,
                      settle: float = 3.0):
    """等到指定 placeholder 的輸入框出現為止。

    別用 driver.implicitly_wait() 當睡眠——它只是設定全域逾時，不會暫停，
    迴圈會瞬間空轉完，然後在 React 掛載前就把值寫進去（寫得進去但狀態不會更新）。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        el = find_by_placeholder(driver, fragment, tag)
        if el is not None and el.is_displayed():
            # 元素出現不等於 React 已經接手，多給一點時間讓事件處理器掛上
            time.sleep(settle)
            return el
        time.sleep(interval)
    return None


def set_value(driver, element, value: str) -> None:
    """寫入輸入框的值。

    優先用真實鍵盤事件（send_keys）——React 一定收得到。
    原生 setter 只是備援：它寫得進 DOM，但元件還沒掛載時 React 的 state
    不會更新，表單看起來有值、送出去卻是空的。
    """
    try:
        element.clear()
        element.send_keys(value)
        if (element.get_attribute("value") or "").strip() == value.strip():
            return
    except Exception:
        pass
    driver.execute_script(_REACT_SET_VALUE, element, value)


def find_button(driver, text: str, exact: bool = True):
    """用按鈕上的文字找按鈕。"""
    for b in driver.find_elements(By.TAG_NAME, "button"):
        label = b.text.strip()
        if (label == text) if exact else (text in label):
            return b
    return None


def click_button(driver, text: str, exact: bool = True) -> bool:
    """點擊指定文字的按鈕。用 JS 點擊避開被其他元素遮住的問題。"""
    b = find_button(driver, text, exact)
    if b is None:
        return False
    driver.execute_script("arguments[0].click();", b)
    return True


def wait_until(check: Callable[[], bool], timeout: int, interval: float = 2.0,
               on_tick: Optional[Callable[[int], None]] = None) -> bool:
    """輪詢直到條件成立或逾時。回傳是否成立。

    比固定 sleep 好在測完就走，也不會在還沒測完時就去抓頁面。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        if on_tick:
            on_tick(int(deadline - time.time()))
        time.sleep(interval)
    return check()


def wait_for(probe: Callable[[], dict], is_done: Callable[[dict], bool],
             timeout: int, interval: float = 2.0,
             on_tick: Optional[Callable[[dict, int], None]] = None) -> dict:
    """輪詢探針直到 is_done 成立或逾時，回傳最後一次的狀態。

    完成條件一定要能分辨「我們的結果」與「網站預設顯示的示範資料」。
    tcptest 兩個頁面在還沒測之前就擺著一整張示範結果表，若只看
    「數值不再變動」會立刻被示範資料騙過去，抓到完全無關的內容。
    """
    deadline = time.time() + timeout
    state: dict = {}
    while time.time() < deadline:
        state = probe()
        if is_done(state):
            return state
        if on_tick:
            on_tick(state, int(deadline - time.time()))
        time.sleep(interval)
    return state or probe()


def stabilizer(rounds: int = 2):
    """產生一個「值連續 rounds 次不變才算數」的判斷器。

    給那些沒有明確完成訊號、只能靠停止變動來判斷的頁面用。
    """
    history = {"last": None, "count": 0}

    def settled(value) -> bool:
        if value == history["last"]:
            history["count"] += 1
        else:
            history["last"] = value
            history["count"] = 0
        return history["count"] >= rounds

    return settled


def table_row_counts(driver) -> List[int]:
    """各個 table 的 tbody 列數，用來判斷結果有沒有長出來。"""
    return driver.execute_script(
        "return [...document.querySelectorAll('table')]"
        ".map(t => t.querySelectorAll('tbody tr').length);"
    ) or []
