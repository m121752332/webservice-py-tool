# WebService 測試工具 UI 改版設計（wxPython → PySide6）

- 日期：2026-09-25
- 分支：`feat/pyside6-ui`
- 版本：`v1.1.5` → `v2.0.0`

## 1. 目標與範圍

將目前以 wxPython + wxFormBuilder 製作的介面，改寫為 PySide6 的現代化桌面 App，並提供可切換的 Light / Dark 主題。

**目標**

- Fluent 風格的現代外觀（自製 QSS，不使用 GPL 元件庫，專案維持 MIT 授權）
- Light / Dark / 跟隨系統 三種主題模式，選擇會被記住
- 左側連線清單 + 右側工作區的版面
- 讀取 WSDL 與執行請求在背景執行，畫面不凍結
- XML 語法上色、請求格式化、回應複製、狀態列顯示結果/耗時/大小
- 核心邏輯與 UI 分離，並補上單元測試

**不在範圍內**

- 請求歷史紀錄、多分頁、自訂 HTTP Header、macOS/Linux 打包
- App 內建 UI 檢測面板（改以 PyQtInspect 作為開發工具）
- 快捷鍵自訂編輯器（舊版 Ctrl+E，移除）

**相容性要求**

- `src/app_data/connections.profile` 的 JSON 格式不變，舊資料可直接使用
- `src/app_data/ws_tool.yaml` 的欄位不變（僅版本號更新）

## 2. 架構與檔案結構

```
src/
├─ ws_tool.py                 進入點：QApplication、全域例外處理、主題、主視窗
├─ core/                      純邏輯，不依賴 UI 框架
│  ├─ connection_store.py     Connection dataclass + ConnectionStore
│  └─ soap_service.py         SoapService、CallResult、ParamCountMismatch、format_xml
├─ ui/
│  ├─ theme.py                色票、QSS 樣板、ThemeManager
│  ├─ main_window.py          主視窗（工作區、狀態列、快捷鍵）
│  ├─ notification_bar.py     通知橫幅
│  ├─ connection_list.py      左側連線清單（搜尋、新增、刪除、選取）
│  ├─ xml_editor.py           XmlEditor + XmlHighlighter
│  └─ workers.py              背景工作（QThreadPool + 訊號）
├─ config/                    沿用 web_service_config.py 與 ws_tool.yaml
└─ utils/                     沿用 pathutil / fileutils / yaml_values / uuidutil / globalvalues
tests/                        pytest 測試
```

**依賴變更**

| 變更 | 套件 | 群組 |
|---|---|---|
| 新增 | `pyside6-essentials` | 執行期 |
| 移除 | `wxpython` | 執行期 |
| 新增 | `pytest` | dev |
| 新增 | `PyQtInspect`（UI 檢測，不打包進 exe） | dev |

**移除的檔案**：`src/ui/main/`（`main.py`、`main_frame.py`）、`src/utils/darkmode.py`、`src/utils/toaster.py`、`src/utils/balloontip.py`、`fbp/`。

**使用者偏好設定**：主題模式存於 `app_data/settings.ini`（`QSettings` IniFormat，已被 `.gitignore` 的 `*.ini` 排除）。

## 3. 主畫面與互動

```
┌───────────────┬──────────────────────────────────────────────┐
│ WebService    │ [TIPTOP 正式區              ] ← 配置名，可直接改│
│ [🔍 搜尋連線 ] │ [http://.../aws_ttsrv2?WSDL        ] [讀取 WSDL]│
│               │ [GetPOData        ▾] 逾時 [30]s [▶ 執行] [清空]│
│ ▌TIPTOP 正式區 │ ⚠ 參數數量不符：需要 1 個，輸入了 2 個   ✕     │
│  172.20.3.22… │ ┌ 請求參數 (#~# 分隔) [格式化]┬ 回應結果  [複製]┐│
│  TOPTEST      │ │<Request>                   │<Response>      ││
│  172.20.3.22… │ │  <Access>…                 │  <Execution>…  ││
│               │ └────────────────────────────┴────────────────┘│
│ [+ 新增連線]   │                                                │
│ ◐ 主題  ⓘ 關於 │ ● 成功 · 0.42 s · 3.1 KB                       │
└───────────────┴──────────────────────────────────────────────┘
```

### 左側欄（`ConnectionList`）

- 每筆顯示兩行：名稱（粗體，空白時顯示「未命名」）與網址（次要色，過長省略）
- 搜尋框依名稱或網址即時篩選（不分大小寫）
- 「+ 新增連線」建立空白連線並選取，焦點移到配置名欄位
- 刪除：右鍵選單「刪除」或 Del 鍵，需確認
- 清單永遠至少一筆：啟動時沒有任何連線、或刪除最後一筆時，自動建立一筆空白連線並選取（沿用舊版行為）
- 底部「主題」按鈕彈出選單：跟隨系統 / 淺色 / 深色（勾選目前模式）
- 底部「關於」按鈕顯示 App 名稱、版本、版權、GitHub 連結、作者（內容取自 `ws_tool.yaml`）

### 右側工作區

- **配置名**：`QLineEdit`，最多 100 字，佔位文字「請輸入配置名稱」；離開欄位或 Enter 時存檔
- **網址**：`QLineEdit`，佔位文字「http://host/path?WSDL」；離開欄位或 Enter 時存檔；網址不以 `?WSDL`（不分大小寫）結尾時，欄位下方顯示提示「結尾請加上 ?WSDL」
- **讀取 WSDL**：背景載入方法清單，成功後存入該連線的 `methods` 並更新下拉框；若請求編輯器為空，填入 `<?xml version="1.0" encoding="utf-8"?>`
- **方法下拉框**：可編輯並以 `QCompleter`（包含比對、不分大小寫）篩選；選取連線時直接帶出已儲存的方法
- **逾時**：`QSpinBox` 5～120 秒，初始值取自 `ws_tool.yaml` 的 `timeout`
- **執行**：主要按鈕；背景執行請求
- **清空**：清除請求與回應內容（保留方法清單，與舊版不同：舊版會連方法清單一併清除，但方法已存在配置中，清除沒有意義）
- **請求編輯器**：標題「請求參數（多個用 #~# 隔開）」+「格式化」按鈕（Ctrl+Shift+F）；格式化失敗時顯示警告橫幅，不修改內容
- **回應編輯器**：唯讀，標題「回應結果」+「複製」按鈕（複製到剪貼簿後顯示成功橫幅）
- 請求與回應以 `QSplitter` 左右並排，可拖曳調整

### 執行中狀態

- 讀取或執行時，觸發的按鈕文字變為「取消」，其餘會改變狀態的操作（讀取、執行、新增、刪除、切換連線）停用
- 取消時畫面立即恢復；背景的 suds 請求無法中斷，會在逾時後自行結束，其結果被忽略
- 狀態列顯示「讀取中…」/「執行中…」

### 通知

- 工作區頂端的通知橫幅（`NotificationBar`）：info / success / warning / error 四種樣式
- success / info 3 秒後自動隱藏；warning / error 需手動關閉（或被下一則通知取代）
- 確認對話框（`QMessageBox`）只用於刪除連線與離開程式

### 狀態列

- 結果標記：`● 成功`（success 色）/ `● 失敗`（danger 色）/ `讀取中…`
- 執行成功時附上耗時（秒，兩位小數）與回應大小（B / KB / MB）

### 快捷鍵

| 按鍵 | 功能 |
|---|---|
| F1 | 新增連線 |
| F2 | 刪除連線（需確認） |
| F3 | 讀取 WSDL |
| F5 | 執行請求 |
| F6 | 清空 |
| Ctrl+Shift+F | 格式化請求 XML |
| Esc | 離開程式（需確認） |

不再使用選單列，功能以畫面上的按鈕與上述快捷鍵提供。關閉視窗（X）同樣需要確認。

## 4. 主題系統

### ThemeManager

- 模式：`system` / `light` / `dark`，預設 `system`，存於 `settings.ini` 的 `ui/theme`
- 實際配色（effective scheme）：
  - `system`：取 `QGuiApplication.styleHints().colorScheme()`，並監聽 `colorSchemeChanged` 即時更新；若回傳 `Unknown` 視為 light
  - `light` / `dark`：直接使用，並呼叫 `styleHints().setColorScheme()` 讓 Windows 標題列同步
  - 從手動模式切回 `system` 時呼叫 `styleHints().unsetColorScheme()`
- 套用：設定 `QPalette` + 產生 QSS 後 `app.setStyleSheet()`，基底樣式為 `Fusion`
- 發出 `themeChanged(ThemePalette)` 訊號，供 XML 上色等元件更新

### 色票（`ThemePalette` dataclass）

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `bg` | #F3F3F3 | #202020 | 視窗底色、側欄 |
| `surface` | #FFFFFF | #2B2B2B | 卡片、輸入框、編輯器 |
| `surface_hover` | #EAEAEA | #383838 | 滑過狀態、清單選取底色（需與 `bg` 有明顯差異） |
| `border` | #E0E0E0 | #3A3A3A | 邊框、分隔線 |
| `text` | #1B1B1B | #FFFFFF | 主要文字 |
| `text_muted` | #616161 | #A0A0A0 | 次要文字、佔位文字 |
| `accent` | #0067C0 | #4CC2FF | 主要按鈕、選取指示、焦點框 |
| `accent_hover` | #1975C5 | #47B1E8 | 主要按鈕滑過 |
| `accent_text` | #FFFFFF | #000000 | 主要按鈕上的文字 |
| `success` | #0F7B0F | #6CCB5F | 成功狀態 |
| `warning` | #9D5D00 | #FCE100 | 警告 |
| `danger` | #C42B1C | #FF99A4 | 錯誤、刪除 |

XML 上色（`XmlColors`，隨主題切換）：

| 類別 | Light | Dark |
|---|---|---|
| 標籤名稱 | #800000 | #569CD6 |
| 屬性名稱 | #E50000 | #9CDCFE |
| 屬性值 | #0000FF | #CE9178 |
| 註解 | #008000 | #6A9955 |
| 宣告 `<?xml ?>` | #808080 | #808080 |

### 外觀規格

- 圓角：按鈕、輸入框 6px；卡片、通知橫幅 8px
- 按鈕三種變體（以 Qt 動態屬性 `variant` 區分）：`primary`（實心 accent）、預設（外框）、`subtle`（無框）
- 字型：介面 `Segoe UI Variable`，中文 fallback `Microsoft JhengHei UI`；編輯器 `Cascadia Mono`，fallback `Consolas`
- 間距：以 4 的倍數（4 / 8 / 12 / 16）

### XmlHighlighter

`QSyntaxHighlighter` 以正規表達式處理：宣告 `<?…?>`、註解 `<!--…-->`（支援跨行）、標籤名稱、屬性名稱、屬性值（單/雙引號）。主題變更時更新顏色並 `rehighlight()`。

## 5. 核心邏輯

### ConnectionStore（`core/connection_store.py`）

```python
@dataclass
class Connection:
    uuid: str
    name: str
    url: str
    methods: list[str]

class ConnectionStore:
    def __init__(self, path: Path): ...
    def all(self) -> list[Connection]: ...           # 回傳副本；不取名 list，避免遮蔽 list[...] 型別註解
    def get(self, uuid: str) -> Connection | None: ...
    def add(self) -> Connection: ...                 # name="", url="", methods=[]
    def remove(self, uuid: str) -> None: ...
    def rename(self, uuid: str, name: str) -> None: ...
    def set_url(self, uuid: str, url: str) -> None: ...
    def set_methods(self, uuid: str, methods: list[str]) -> None: ...
    @property
    def recovered_from_corruption(self) -> bool: ...
```

- 檔案格式：`{"connections": [{"uuid", "name", "url", "method": [...]}]}`（`method` 鍵名沿用舊格式）
- 所有操作以 uuid 定位；找不到 uuid 時丟出 `KeyError`
- 每次修改後立即儲存：寫入同目錄暫存檔再 `os.replace`，JSON `indent=4`、`ensure_ascii=False`
- 檔案不存在：建立 `{"connections": []}`
- JSON 解析失敗：原檔改名為 `connections.profile.bak`（已存在則覆蓋），以空清單開始，`recovered_from_corruption` 為 `True`，由 UI 顯示警告橫幅

### SoapService（`core/soap_service.py`）

```python
@dataclass
class CallResult:
    text: str          # 已格式化（若為合法 XML）或原文
    elapsed: float     # 秒
    size: int          # 原始回應的 UTF-8 位元組數

class ParamCountMismatch(Exception):
    expected: int
    actual: int

def split_params(raw: str) -> list[str]: ...   # 移除 \r \n 後以 "#~#" 切分
def format_xml(text: str) -> str: ...          # lxml pretty print，失敗丟 ValueError

class SoapService:
    def __init__(self, client_factory=suds.client.Client): ...
    def load_methods(self, url: str, timeout: int) -> list[str]: ...   # 重建並快取 client
    def call(self, url: str, method: str, raw_params: str, timeout: int) -> CallResult: ...
```

- Client 以網址快取；`load_methods` 一律重建（`cache=None`，不用 suds 預設一天的磁碟快取）。`call` 若無快取則建立；有快取則以 `set_options(timeout=...)` 更新逾時。取消後的舊請求可能仍在使用同一個 client，但 suds 1.2 的 `clone()` 會 RecursionError，因此直接共用
- 參數對應沿用舊邏輯：依方法定義的參數順序，將切分結果依序對應
- 回應不是字串時以 `str()` 轉換；`format_xml` 失敗時 `text` 使用原文
- `client_factory` 可注入，方便測試

### 背景工作（`ui/workers.py`）

- `Task(QRunnable)` 包裝任意函式，透過 `TaskSignals(QObject)` 發出 `succeeded(object)` / `failed(Exception)`
- 主視窗維護遞增的請求序號；結果回來時序號不符（已取消或被取代）則忽略

## 6. 錯誤處理與記錄

| 情境 | 呈現 |
|---|---|
| WSDL 讀取失敗、網路錯誤、逾時、SOAP Fault | error 橫幅（簡短原因）+ 狀態列「● 失敗」；完整 traceback 寫入 log |
| 參數數量不符 | warning 橫幅：「此方法需要 N 個參數，目前輸入 M 個（多個參數請用 #~# 隔開）」 |
| 未填網址 / 未選方法 | warning 橫幅 |
| 格式化失敗 | warning 橫幅「請求內容不是合法的 XML」 |
| 設定檔損毀 | warning 橫幅，說明已備份為 `.bak` |
| 未預期例外 | `sys.excepthook` 寫入 log 並顯示錯誤對話框 |

log 沿用 loguru，路徑與保留天數取自 `ws_tool.yaml`。

## 7. 測試

pytest，全部離線執行：

- `tests/test_connection_store.py`：新增、刪除、改名、改網址、存方法、重新載入後資料一致、檔案不存在、JSON 損毀的備份、讀取現有 `connections.profile` 格式
- `tests/test_soap_service.py`：`split_params`、`format_xml`（合法/不合法）、以假 client 驗證參數對應與 `ParamCountMismatch`、client 快取、`load_methods` 使用本機 WSDL fixture（`tests/fixtures/sample.wsdl`）
- UI 元件測試（`QT_QPA_PLATFORM=offscreen`）：`test_theme.py`、`test_xml_editor.py`、`test_workers.py`、`test_notification_bar.py`、`test_connection_list.py`、`test_main_window.py`（以假的 SoapService 驗證讀取、執行、取消、刪除、主題切換等流程）

## 8. 打包與文件

- `build.bat` 維持現有流程（`uv sync` + `uv run pyinstaller`），PySide6 由 PyInstaller 內建 hook 處理；完成後實際打包並啟動驗證
- `ws_tool.yaml` 版本更新為 `v2.0.0`
- README：更新技術說明（PySide6）、開發方式、UI 檢測工具使用方式；移除 wxFormBuilder 說明。截圖需由使用者於新介面重新擷取
