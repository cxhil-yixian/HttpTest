"""用 Selenium 操作 itdog.cn 執行一批測試。

這是整個專案唯一碰瀏覽器與 itdog.cn 的地方。
之後接 tcptest.cn 時新增 busters/tcptest/，DATA 與 GOOGLE 兩個模組不需更動。
"""

import json
import time
from typing import List, Sequence

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from ..config import ItdogConfig
from ..data.records import HTTPS, ResultRecord
from .parser import parse_results

PAGE_LOAD_WAIT = 2      # 開頁後等待秒數
OPTIONS_OPEN_WAIT = 1   # 展開節點選單後等待秒數


def build_targets(ips: Sequence[str], protocol: str) -> List[str]:
    """HTTPS 測試要把 IP 加上 https:// 前綴，HTTP 則直接送 IP。"""
    if protocol == HTTPS:
        return [f"https://{ip}" for ip in ips]
    return list(ips)


def _chrome_options(cfg: ItdogConfig) -> Options:
    options = Options()
    if cfg.headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return options


def run_batch(ips: Sequence[str], protocol: str, cfg: ItdogConfig) -> List[ResultRecord]:
    """送出一批 IP 到 itdog.cn，等待固定秒數後解析結果。

    注意：等待是固定 cfg.test_wait_time 秒而非輪詢完成狀態，
    IP 數量接近上限時可能在測試跑完前就抓頁面。
    """
    targets = build_targets(ips, protocol)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=_chrome_options(cfg))
    try:
        driver.get(cfg.url)
        time.sleep(PAGE_LOAD_WAIT)

        textarea = driver.find_element(By.ID, "host")
        textarea.clear()
        textarea.send_keys("\n".join(targets))

        # 展開進階選項才能選節點
        driver.find_element(By.ID, "ad_options").click()
        time.sleep(OPTIONS_OPEN_WAIT)

        # 節點選單是 jQuery 元件，用原生點擊選不了，只能走 JS
        driver.execute_script(
            f"$('select.node_select').val({json.dumps(cfg.node_ids)}).trigger('change');"
        )

        driver.find_element(By.XPATH, "//button[@onclick='check_form()']").click()
        time.sleep(cfg.test_wait_time)

        html = driver.page_source
    finally:
        driver.quit()

    return parse_results(html, cfg.nodes, protocol)
