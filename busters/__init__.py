"""HttpTest 共用套件。

三個模組：
    busters.itdog   — itdog.cn 批量測試採集（網站專屬）
    busters.data    — 檔案通道、報表排版、Excel 讀寫（不含任何網站知識）
    busters.google  — Google Sheets 讀寫（不含任何網站知識）

資料流全程以檔案為通道：
    Sheets ──google──> CDN_IP_list.txt ──itdog──> logs/*.txt ──data──> *.xlsx ──google──> Sheets
"""
