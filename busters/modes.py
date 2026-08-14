"""兩種測試模式。

SINGLE — 單站測試：一個網址，看它在各節點的詳細指標（狀態、耗時、解析、連接…）
BATCH  — 批量測試：一批 IP，看每個 IP 在各節點的狀態（狀態碼或延遲）

兩個來源（itdog / tcptest）各自實作這兩種模式，介面一致：
    run_batch(targets, protocol, cfg)  -> List[ResultRecord]
    run_single(url, cfg)               -> (columns, List[SiteProbe])
"""

SINGLE = "single"
BATCH = "batch"

ALL_MODES = (SINGLE, BATCH)

ITDOG = "itdog"
TCPTEST = "tcptest"

ALL_SOURCES = (ITDOG, TCPTEST)
