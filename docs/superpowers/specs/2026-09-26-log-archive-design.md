# 記錄分流、日期歸檔與請求紀錄查閱設計

- 日期：2026-09-26
- 分支：`feat/log-archive`

## 1. 目標與範圍

目前只有一個 `run.log`：`ws_tool.yaml` 的 `retention: "10 days"` 沒有搭配輪替，實際上不會生效；而請求與回應只在 `run.log` 留下截斷後的摘要，事後很難回頭查。

**範圍內**

1. **等級分流**（類似 logback 的 `LevelFilter`）：依 `log.levels` 設定額外寫入 `ws_info.log`、`ws_debug.log`、`ws_error.log`、`ws_other.log`（other 收 TRACE、SUCCESS、WARNING、CRITICAL）；`run.log` 保留，當作完整記錄
2. **請求紀錄**：每次執行請求（成功或失敗）都寫一筆到 `ws_xml.log`，內容可用 `log.xml.content` 切換：`params`（使用者輸入的參數＋回應內容，預設）、`envelope`（實際的 SOAP 信封）、`both`
3. **日期歸檔**：`run.log`、四個分流檔與 `ws_xml.log` 都在換日時把前一天的檔案改名為 `名稱_YYYYMMDD.log`，再開新檔；超過保留天數的歸檔檔會自動刪除
4. **查閱工具**：獨立視窗，可以依日期、連線、方法篩選請求紀錄，也能用關鍵字搜尋，並可把某一筆「帶回工作區」重送；從側欄按鈕或快捷鍵 `F10` 開啟
5. 所有記錄檔一律放在 `log.path` 指定的目錄（預設 `app_data/logs`）

**不在範圍內**

- 依檔案大小輪替、壓縮歸檔
- 查閱工具編輯或刪除紀錄、匯出
- 讀取 WSDL 的呼叫不寫入 `ws_xml.log`（沒有請求／回應 XML）
- 參數數量不符（`ParamCountMismatch`）的情況沒有真正送出請求，所以也不記錄

**相容性要求**

- `ws_tool.yaml` 的既有欄位意義不變：`level` 仍然是 `run.log` 的門檻；`retention` 仍然使用 `"10 days"` 格式（也接受純數字）
- 新欄位（`levels`、`xml.*`）在舊設定檔中不存在時使用預設值，程式照常啟動
- `SoapService`、`MainWindow` 新增的參數都是選填，既有呼叫端與測試不需修改

## 2. 設定檔

```yaml
  log:
    # log path setting
    path: "app_data/logs"
    # log level（run.log 門檻）
    level: info
    # 額外分流的等級（info, debug, error, other，以逗號分隔；留空則不分流）
    levels: "info, debug, error, other"
    # log retention days（run.log 與 ws_*.log）
    retention: "10 days"
    # 請求紀錄（ws_xml.log）
    xml:
      # 是否記錄
      enabled: true
      # 內容：params（參數＋回應）/ envelope（SOAP 信封）/ both
      content: params
      # 保留天數
      retention: 30
```

`level` 與 `levels` 互相獨立：`level` 只決定 `run.log` 的門檻（和舊版相同，想要完整記錄就設成 `trace`）；分流檔只看 `levels`，不受 `level` 影響（例如 `level: info`、`levels` 含 `debug` 時，DEBUG 訊息仍會寫入 `ws_debug.log`，但不會出現在 `run.log`）。`ws_xml.log` 只看 `xml.enabled`。

預設值：`levels` 為 `"info, debug, error, other"`、`xml.enabled` 為 `true`、`xml.content` 為 `params`、`xml.retention` 為 `30`。`levels` 裡無法辨識的名稱會被忽略，並寫一筆 warning；`content` 不合法時改用 `params`。

`app_settings.py`：`app.log.xml.content` 在設定頁顯示成下拉選單（三個選項）；`app.log.xml.retention` 是 int，範圍 1～3650。這些 key 都屬於「需重新啟動」。

## 3. 架構

```
src/core/daily_log.py        新增：DailyFileSink、parse_retention_days、parse_levels、purge_archives（不依賴 Qt）
src/core/xml_log.py          新增：CallRecord、XmlLogWriter、format_record / parse_records、list_log_dates、read_records
src/core/soap_service.py     修改：可注入 recorder；call() 新增 connection 參數，不論成功或失敗都交給 recorder
src/config/web_service_config.py 修改：讀取新欄位（缺少時用預設值）
src/config/app_settings.py   修改：xml.content 下拉、xml.retention 範圍
src/ws_tool.py               修改：setup_logging 改用 DailyFileSink＋分流；建立 XmlLogWriter 注入 SoapService
src/ui/xml_log_viewer.py     新增：XmlLogViewer 查閱視窗
src/ui/main_window.py        修改：footer「紀錄」按鈕、F10、load_record() 帶回工作區
src/ui/icons.py / theme.py   修改：紀錄按鈕圖示、查閱視窗 QSS
src/app_data/ws_tool.yaml    修改：新增 levels、xml 區段
```

**資料流**

```
logger.xxx()  → run.log sink（level 門檻）
              → ws_<level>.log sink（精準比對等級，只註冊 levels 裡有的）
              → LogBuffer（主控台，不變）

背景執行緒 SoapService.call(url, method, params, timeout, connection=名稱)
  → suds 呼叫；client.last_sent() / last_received() 取得信封
  → recorder(CallRecord)  → XmlLogWriter → DailyFileSink(ws_xml.log)
  → 回傳 CallResult 或丟出例外（行為不變）

F10 / 紀錄按鈕 → XmlLogViewer（背景讀檔 → parse_records → 表格）
  → 「帶回工作區」 → resendRequested(CallRecord) → MainWindow.load_record()
```

紀錄寫在 `SoapService.call()` 裡，而不是 UI 回呼裡：使用者按「取消」後，背景請求仍會繼續跑完，這一筆也會被記下來。

## 4. 日期歸檔（`src/core/daily_log.py`）

```python
class DailyFileSink:
    def __init__(self, log_dir: Path, stem: str, retention_days: int, clock=datetime.now): ...
    def write(self, text: str) -> None   # 執行緒安全；可直接當 loguru sink
    def close(self) -> None
```

- 目前的檔名固定為 `<stem>.log`；「目前檔案的日期」在建立時取自既有檔案的修改時間（檔案不存在時用今天）
- `write()` 發現今天和目前檔案的日期不同時：關檔 → 改名為 `<stem>_<YYYYMMDD>.log`（日期為舊檔日期）→ 開新檔 → 呼叫 `purge_archives`
- 建立時也會做一次同樣的檢查與清理，所以隔天啟動時會先把昨天的檔案歸檔
- 如果歸檔檔名已經存在，就把內容附加到既有檔案後面，不覆蓋
- `purge_archives(log_dir, stem, retention_days, today)`：刪除符合 `^<stem>_(\d{8})\.log$`、而且日期早於 `today - retention_days` 的檔案；刪除失敗（例如檔案被占用）時忽略，下次再試
- 所有檔案 I/O 錯誤都不可以往外丟，避免記錄動作把主流程弄壞
- `parse_retention_days("10 days") -> 10`：接受 `"N"`、`"N day(s)"`、int；無法解析時用 10
- `parse_levels("info, debug, foo") -> (("info", "debug"), ("foo",))`：回傳（有效等級, 無法辨識的名稱）；不分大小寫，會去掉重複，只接受 `info/debug/error/other`

`setup_logging` 用 loguru 預設的檔案格式（`{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}`）、`colorize=False`；分流 filter：`info/debug/error` 比對 `record["level"].name` 是否完全相同，`other` 則收其餘所有等級（包含自訂等級）。

## 5. 請求紀錄（`src/core/xml_log.py`）

```python
@dataclass(frozen=True)
class CallRecord:
    time: datetime
    connection: str          # 連線名稱（可為空）
    url: str
    method: str
    status: str              # "success" / "failed"
    elapsed: float
    size: int
    error: str = ""
    params: str = ""
    response: str = ""       # 排版後的回應文字（失敗時為空）
    sent: str = ""           # SOAP 請求信封
    received: str = ""       # SOAP 回應信封
```

檔案格式（一筆一塊，記事本打開也看得懂）：

```
===== 2026-09-26 14:03:22.123 =====
{"connection": "訂單服務", "url": "http://…?wsdl", "method": "GetOrder", "status": "success", "elapsed": 0.53, "size": 1234, "error": ""}
----- 參數 -----
<?xml version="1.0" encoding="utf-8"?>…
----- 回應 -----
…
```

- `content=params` 寫「參數」「回應」兩段；`envelope` 寫「SOAP 請求」「SOAP 回應」兩段；`both` 四段都寫
- 解析：以 `===== … =====` 開頭行切成一筆；下一行是 JSON 標頭；接著以 `----- 段名 -----` 切段。格式壞掉的區塊略過，不影響其他筆
- `XmlLogWriter(log_dir, content, retention_days)` 可呼叫（`__call__(record)`），內部用 `DailyFileSink(log_dir, "ws_xml", …)`
- `list_log_dates(log_dir) -> list[tuple[date, Path]]`：`ws_xml.log`（以修改日期為準）＋所有 `ws_xml_YYYYMMDD.log`，新的排在前面
- `read_records(path) -> list[CallRecord]`：讀檔並解析，檔案不存在時回傳空清單

`SoapService`：

```python
SoapService(client_factory=..., recorder: Callable[[CallRecord], None] | None = None)
call(url, method, raw_params, timeout, *, connection: str = "") -> CallResult
```

參數數量檢查通過後，才開始計時並呼叫；呼叫成功或失敗時都組出 `CallRecord` 交給 recorder（失敗時的 `error` 是例外訊息，`sent/received` 盡量取得）。recorder 本身發生錯誤時只寫 warning，不影響呼叫結果。`MainWindow._on_run_clicked` 會把目前的連線名稱傳進去。

## 6. 查閱工具（`src/ui/xml_log_viewer.py`）

```
┌ 請求紀錄 ───────────────────────────────────────────────────────┐
│ 日期 [2026-09-26（今天）▾] 連線 [全部▾] 方法 [全部▾] [🔍 關鍵字…] [重新整理] │
├──────────────────────────────┬──────────────────────────────────┤
│ 時間     連線   方法   狀態 耗時 │ [參數][回應][SOAP 請求][SOAP 回應]   │
│ 14:03:22 訂單  GetOrder 成功 0.53│  （唯讀 XmlEditor）                │
│ 13:58:10 訂單  GetOrder 失敗 1.20│                                  │
│ …                            │                    [帶回工作區]     │
└──────────────────────────────┴──────────────────────────────────┘
```

- 獨立的頂層視窗（`Qt.Window`），只建立一次；再按 F10 或紀錄按鈕時，會把它顯示出來並帶到前景。它不是 modal，可以和主視窗並排對照
- 每次開啟、切換日期、按「重新整理」（視窗內 `F5`）時，用 `run_in_background` 讀檔
- 連線下拉：全部＋該日出現過的連線名稱（名稱是空的就顯示 URL）；方法下拉：全部＋所選連線出現過的方法
- 關鍵字：不分大小寫，比對參數、回應、信封、錯誤訊息
- 表格新的在上面；狀態欄失敗的用錯誤色顯示；沒有內容的分頁會隱藏；失敗的紀錄在「回應」分頁顯示錯誤訊息
- `resendRequested = Signal(object)`（CallRecord）：按「帶回工作區」或雙擊某一列時送出
- 主題切換時更新 XmlEditor 的顏色（和主視窗相同，接 `themeChanged`）

`MainWindow`：

- 建構子新增選填參數 `xml_log_dir: Path | None = None`；沒有給的話，紀錄按鈕與 F10 不會出現／不會生效
- 側欄 footer 最後新增「紀錄」按鈕：只顯示圖示（既有三顆文字按鈕已接近 236 px 上限），tooltip「請求紀錄 (F10)」
- `load_record(record)`：設定頁開著時先嘗試離開（有未存檔變更會詢問，取消就中止）；如果目前有背景工作 → 顯示 warning 通知；否則先找 URL 與名稱都相同的連線，找不到再找只有 URL 相同的，都找不到 → warning 通知「找不到對應的連線」。找到時就選取該連線，並填入方法與參數，把主視窗帶到前景，顯示 info 通知；紀錄沒有保存參數（`content=envelope`）時只帶回連線與方法，並顯示 warning 說明

## 7. 錯誤處理

- 記錄目錄不存在時自動建立；檔案 I/O 失敗不影響主程式（記錄功能會降級，不會讓程式崩潰）
- 查閱工具讀檔失敗時，在視窗內用通知列顯示錯誤，表格清空
- 歸檔檔案被其他程式占用、無法改名時：繼續寫入目前的檔案，下次寫入時再試

## 8. 測試

- `tests/test_daily_log.py`：換日改名、同名歸檔改為附加、啟動時歸檔舊檔、清除過期檔（邊界日）、忽略不符合檔名規則的檔案、`parse_retention_days`、`parse_levels`
- `tests/test_xml_log.py`：三種 content 模式的輸出、寫入後再解析結果一致、內容含中文與多行 XML、格式壞掉的區塊會被略過、`list_log_dates` 排序
- `tests/test_soap_service.py`：成功與失敗都呼叫 recorder、參數數量不符時不記錄、recorder 丟例外不影響結果
- `tests/test_entry_point.py`：`setup_logging` 依 `levels` 只建立對應的分流檔、info 只進 `ws_info.log`、other 收 WARNING；舊設定檔（沒有新欄位）能讀取
- `tests/test_app_settings.py`：`xml.content` 顯示成 list 欄位、`xml.retention` 有範圍檢查
- `tests/test_xml_log_viewer.py`：載入、日期／連線／方法／關鍵字篩選、分頁隱藏、`resendRequested`
- `tests/test_main_window.py`：F10 開啟查閱視窗、`load_record` 的三種情況（找到連線、找不到連線、忙碌中）
