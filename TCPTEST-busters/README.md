# TCPTEST-busters（待建）

預留給 [tcptest.cn/http](https://www.tcptest.cn/http) 的應用層目錄。

要接上時只需要做兩件事：

1. 新增 `busters/tcptest/`——放 tcptest.cn 專屬的採集與解析邏輯，
   對外暴露「一批 IP + 協議 → `ResultRecord` 清單」，與 `busters/itdog/` 同介面。
2. 在本目錄放 `run_all.py` 與 `start.bat`，比照 `ITDOG-busters/` 編排三個步驟。

DATA (`busters/data/`) 與 GOOGLE (`busters/google/`) 兩個模組不含任何網站知識，
可以直接沿用，不需修改。

節點清單與欄位配置寫在根目錄 `config.yaml`，屆時新增一個 `tcptest:` 區塊即可。
