# 主控台（Console）記錄面板設計

- 日期：2026-09-26
- 分支：`feat/log-console`

## 1. 目標與範圍

目前執行結果只能到 `app_data/logs/run.log` 查看。新增一個類似 VS Code Panel 的**主控台面板**，把程式從啟動、讀取 WSDL、執行請求到關閉期間的 loguru 記錄即時顯示在 UI 上。

**範圍內**

- 右側區域下方可收合的主控台面板，與上方內容以可拖曳的分割線隔開；工作區與設定頁（F11）共用
- 側欄底部「關於」後面新增「主控台」按鈕切換開關；快捷鍵 `Ctrl+`` ` 同樣可切換；面板標題列有 ✕ 可關閉
- 收集 TRACE 以上的全部記錄（loguru 7 個內建等級）；程式啟動後、面板建立前的記錄也會保留並補顯示
- 等級篩選：7 個等級（TRACE、DEBUG、INFO、SUCCESS、WARNING、ERROR、CRITICAL）各一顆可複選的切換鈕，不合併；預設開啟 DEBUG、INFO、SUCCESS；選擇結果記在 `settings.ini`，下次啟動沿用
- 關鍵字搜尋（不分大小寫，只顯示符合的記錄）
- 清除、複製（複製目前篩選後可見的內容）
- 開關狀態與面板高度記在 `settings.ini`
- 補上幾個目前沒有記錄的重要時點（啟動、讀取 WSDL、關閉），讓主控台有完整流程可看

**不在範圍內**

- 匯出記錄檔、讀取歷史 `run.log`
- 正規表示式搜尋、搜尋結果高亮
- 在主控台輸入指令
- 更改 `run.log` 本身的等級或格式（仍由 `ws_tool.yaml` 的 `log.level` 決定）

**相容性要求**

- `ws_tool.yaml`、`connections.profile` 格式不變
- `settings.ini` 只新增 `console/*` 鍵；沒有這些鍵（舊檔）時使用預設值
- `MainWindow` 建構子新增的參數皆為選填，既有呼叫端與測試不需修改即可運作

## 2. 架構

```
src/core/log_buffer.py   新增：LogEntry、LogBuffer（執行緒安全的環狀暫存 + loguru sink），不依賴 Qt
src/ui/log_console.py    新增：LogBridge（跨執行緒轉成 Qt 訊號）、ConsolePanel（面板元件）、ConsoleSettings
src/ui/icons.py          修改：新增 console_icon()
src/ui/theme.py          修改：主控台相關 QSS（面板、等級切換鈕、footer 按鈕 checked 狀態）
src/ui/main_window.py    修改：右側改為上下 QSplitter（stack ＋ 主控台）、footer 按鈕、Ctrl+`、補記錄
src/ws_tool.py           修改：建立 LogBuffer 並註冊為 loguru sink，傳給 MainWindow
```

**資料流**

```
任何執行緒 logger.xxx()
  → loguru sink：LogBuffer.write(message)       （加鎖寫入 deque，通知 listener）
  → LogBridge listener：entryAdded.emit(entry)  （從背景執行緒 emit，Qt 以 QueuedConnection 送回主執行緒）
  → ConsolePanel.append(entry)                  （符合篩選才加入文字區）
```

面板第一次建立時先從 `LogBuffer.snapshot()` 取得既有記錄，之後才接收新記錄，所以啟動階段的訊息也看得到。

## 3. 記錄暫存（`src/core/log_buffer.py`）

```python
# loguru 7 個內建等級，依嚴重度排列；篩選鈕一個等級一顆
LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
LEVEL_NO = {"TRACE": 5, "DEBUG": 10, "INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
DEFAULT_CAPACITY = 5000

@dataclass(frozen=True)
class LogEntry:
    seq: int        # 寫入順序（遞增），面板用來避免 snapshot 與即時通知重複
    time: datetime
    level: str      # LEVELS 其中之一
    message: str    # 含例外 traceback（多行）

def normalize_level(name: str, no: int) -> str
    # 內建等級原樣回傳（不合併）
    # 自訂等級（logger.level("XXX", no=...) 新增的）依數值歸到不超過它的最高內建等級，
    # 例如 no=35 → WARNING；低於 5 → TRACE

class LogBuffer:
    def __init__(self, capacity: int = DEFAULT_CAPACITY)
    def write(self, message) -> None       # loguru sink；從 message.record 取 time、level、message、exception
    def snapshot(self) -> list[LogEntry]
    def clear(self) -> None
    def add_listener(self, callback: Callable[[LogEntry], None]) -> None
    def remove_listener(self, callback) -> None
    def attach(self) -> int                # 以 SINK_OPTIONS 註冊為 loguru sink，回傳 handler id

SINK_OPTIONS = dict(level="TRACE", format="{message}", colorize=False, backtrace=False, diagnose=False)
```

- 內部以 `collections.deque(maxlen=capacity)` 保存，`threading.Lock` 保護；超過上限自動丟掉最舊的
- listener 在鎖外呼叫，listener 丟出的例外吞掉，避免記錄動作把主流程弄壞
- `ws_tool.setup_logging()`（由 `main()` 呼叫）在加入 `run.log` sink 之後立刻 `buffer.attach()`
- 實測 loguru 0.7.3：function sink 收到的字串已經是 `{message}` 加上換行，有例外時 loguru 會自動把 traceback 接在後面；`write()` 直接取 `str(message).rstrip("
")`，不用自己格式化。`diagnose=False` 避免 traceback 印出變數值
- `run.log` sink 的等級不受影響，仍依 `ws_tool.yaml`

## 4. 面板（`src/ui/log_console.py`）

### 4.1 `LogBridge(QObject)`

- `entryAdded = Signal(object)`；建構時 `buffer.add_listener(self._on_entry)`，`_on_entry` 只做 `entryAdded.emit(entry)`；`detach()` 移除 listener
- 面板一律以 `Qt.ConnectionType.QueuedConnection` 連接 `entryAdded`：就算在主執行緒寫記錄，也等回到事件迴圈才更新面板。否則面板更新是在 loguru sink 呼叫裡同步執行，面板內任何程式再寫記錄會觸發 loguru 的重入保護（`RuntimeError: ... deadlock avoided`）
- 面板先連接訊號、再取 `snapshot()`；收到 `seq` 不大於已顯示最後一筆的記錄直接略過，避免兩者之間寫入的記錄重複出現
- emit 時若物件已被刪除（程式關閉中）忽略 `RuntimeError`，比照 `workers.py`

### 4.2 `ConsolePanel(QWidget)`，objectName `ConsolePanel`

版面：

```
┌ 主控台                                        [🔍 搜尋記錄…        ] [清除][複製] ✕ ┐
│ (TRACE 0)(DEBUG 12)(INFO 30)(SUCCESS 4)(WARNING 1)(ERROR 3)(CRITICAL 1)            │
│ 14:02:11.532  INFO     程式啟動 · TIPTOP WebService Tool v2.0.1                      │
│ 14:02:15.880  SUCCESS  讀取完成 · 12 個方法                                          │
│ …（QPlainTextEdit，唯讀、等寬字型、不自動換行）                                       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- **標題列分兩列**：第一列為標題、搜尋框、清除／複製／✕；第二列為 7 顆等級切換鈕（靠左排列）。7 顆鈕約 490 px，加上搜尋框與按鈕後超過最小視窗寬度下右側區域的 640 px，所以不擠在同一列
- **等級切換鈕**：7 個 checkable `QPushButton`（`variant="level"`，`level` 屬性對應 QSS 顏色），依 `LEVELS` 順序排列，文字為「等級 ＋ 目前暫存中的筆數」。預設只開 DEBUG、INFO、SUCCESS 時，其他等級的筆數仍會顯示，使用者看得出有被隱藏的警告或錯誤
- **搜尋框**：`QLineEdit`，含清除鈕；輸入後延遲 200 ms 重新篩選（避免每打一個字就重建）；比對 `message` 與等級文字，不分大小寫
- **文字區**：`QPlainTextEdit`（objectName `ConsoleView`），不使用 `setMaximumBlockCount`（一筆 traceback 佔多行，以行數限制會切壞記錄），由面板自己保存記錄清單，超過 `DEFAULT_CAPACITY` 的 110% 時一次修剪回 `DEFAULT_CAPACITY` 筆並重建文字區（分批修剪，避免每筆新記錄都重建）；每行格式 `HH:MM:SS.mmm  LEVEL    訊息`，多行訊息（traceback）後續行縮排
- **上色**：以 `QTextCharFormat` 分段上色，顏色取自主題色票（見 §6.1）——時間 `text_muted`；等級欄位粗體、用該等級的 `fg`；訊息 TRACE／DEBUG `text_muted`、INFO `text`、SUCCESS／WARNING／ERROR／CRITICAL 用該等級的 `fg`；主題切換時 `set_palette()` 重新上色（重建內容）
- **自動捲動**：新增記錄前捲軸在最底端才跟著捲到底；使用者往上捲查看時保持位置
- **篩選／搜尋變更**：以面板自己保存的記錄清單重新產生文字區內容
- **清除**：清空面板與 `LogBuffer`（關掉再開不會跑回來）
- **複製**：複製目前可見（已套用篩選與搜尋）的純文字；沒有內容時不動作
- **✕**：發出 `closeRequested`，由 MainWindow 處理隱藏與記錄狀態

介面：

```python
class ConsolePanel(QWidget):
    closeRequested = Signal()
    levelsChanged = Signal(object)          # frozenset[str]，讓 MainWindow 寫入 settings.ini

    def __init__(self, buffer: LogBuffer, palette: ThemePalette, levels: Iterable[str], parent=None)
    def levels(self) -> frozenset[str]
    def set_levels(self, levels: Iterable[str]) -> None
    def set_search(self, text: str) -> None     # 測試用：立即套用，不經延遲
    def visible_text(self) -> str
    def set_palette(self, palette: ThemePalette) -> None
```

### 4.3 `ConsoleSettings`（同檔，包裝 QSettings）

| 鍵 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `console/visible` | bool | `false` | 面板是否開啟 |
| `console/height` | int | `220` | 面板高度（px） |
| `console/levels` | str | `debug,info,success` | 開啟的等級，逗號分隔、小寫，可用值為 7 個等級名稱；可手動編輯，例如改成 `debug,info,success,error,critical` 啟動就會顯示這五種 |

- 實測 QSettings INI：手動寫的 `levels=debug,info,error`（未加引號）會讀成 list，程式寫入的字串會被加上引號讀回 str；讀取時兩種都接受（list 先以逗號串接）
- 讀取時忽略未知等級與空白；結果為空集合時（例如全部取消勾選）照樣保存為空字串，代表全部隱藏——使用者自己選的狀態要被尊重；只有鍵**不存在**時才用預設值
- 每次變更立即 `setValue` ＋ `sync()`，比照 `ThemeManager`

## 5. 主視窗整合（`src/ui/main_window.py`）

- 建構子新增選填參數 `settings: QSettings | None = None`、`log_buffer: LogBuffer | None = None`；未提供時各自建立暫時物件（記憶體中的 LogBuffer、不落地的設定），既有測試不需修改
- 右側由 `root.addWidget(self.stack, 1)` 改為垂直 `QSplitter`：上方 `stack`、下方 `ConsolePanel`；`setChildrenCollapsible(False)`，面板最小高度 120 px
- 面板在建構時就建立（啟動時若 `console/visible=true` 直接顯示）；程式關閉時 `console_panel.detach()` 移除 listener；隱藏時以 `hide()` 處理，splitter 自動把空間還給上方
- footer 新增 `self.console_button = styled_button("主控台", "footer", "開關主控台 (Ctrl+`)")`，`setCheckable(True)`，搭配 `console_icon()`，排在「關於」之後
- 新增 `toggle_console()`、`set_console_visible(bool)`：同步按鈕勾選、寫入 `console/visible`；面板高度在**關閉面板前**與**程式關閉時**寫入 `console/height`（不在拖曳過程中每移動一次就寫檔）
- 實測：splitter 設 `setStretchFactor(0, 1)`、`(1, 0)` 後，視窗顯示前以 `setSizes([總高 - 面板高, 面板高])` 設定的高度在顯示後維持，視窗放大時多出的空間只給上方
- `Ctrl+`` ` 為全域快捷鍵，不放進 `_workspace_shortcuts`，設定頁開著時也能用
- 設定頁模式（`_set_settings_mode`）目前停用整個 `sidebar`，但 footer 在 sidebar 內，主控台按鈕會跟著被停用。改為**只停用 `connection_list`**，footer 三顆按鈕（主題、關於、主控台）在設定頁都維持可用；`test_main_window.py` 中檢查 `sidebar.isEnabled()` 的兩處改為檢查 `connection_list.isEnabled()`
- `_on_theme_changed` 同時呼叫 `console_panel.set_palette(palette)`

**補充記錄點**（皆 INFO，除非另外註明）

| 時點 | 位置 | 內容 |
|---|---|---|
| 程式啟動 | `ws_tool.main()` | `程式啟動 · {name} {version}` |
| 設定與資料位置 | `ws_tool.main()` | `設定檔={config_path} · 連線資料={data_dir} · 記錄={log_dir}`（DEBUG） |
| 讀取 WSDL 開始 | `_on_load_clicked` | `讀取 WSDL · URL={url}` |
| 讀取 WSDL 完成 | `_on_methods_loaded` | `讀取完成 · {n} 個方法`（SUCCESS） |
| 請求完成 | `_on_call_finished` | 既有的 `請求完成 · …` 由 INFO 改為 SUCCESS（仍 ≥ INFO，`run.log` 照樣記錄） |
| 取消 | `_cancel` | `已取消 {讀取/執行}` |
| 關閉程式 | `closeEvent` 確認後 | `程式關閉` |

## 6. 主題與圖示

- `icons.py` 新增 `console_icon()`：漸層圓角方塊（`#10B981` → `#0D9488`）上畫白色 `>_`，風格與既有兩顆一致
- `theme.py` 新增 QSS（顏色一律用色票變數）：
  - `QWidget#ConsolePanel { background: $surface; border-top: 1px solid $border; }`
  - `QPlainTextEdit#ConsoleView`：無外框、等寬字型（`Cascadia Mono`、`Consolas`）
  - `QPushButton[variant="level"]`：膠囊形（`border-radius: 8px`、`padding: 1px 8px`、8.5pt 粗體），各等級顏色見 §6.1
  - `QPushButton[variant="footer"]:checked { border-color: $accent; background: $surface_hover; }`
- 側欄寬 260 px，內容寬 236 px。實測現有 footer 樣式（`padding: 6px 12px`、間距 8）三顆按鈕合計 264 px 會超出；改為 `QPushButton[variant="footer"]` 的 `padding: 6px 7px`、footer 間距 6，合計 230 px。不改側欄寬度
- `settings_page.palette_colors()` 目前傳出 `name`、`xml` 以外的所有欄位給外掛；改為只傳字串欄位（排除 `name`），新增的 `levels`、`level_alphas` 不會送進外掛

### 6.1 等級配色

7 個等級各有固定且互不相同的色相，讓人一眼分辨。淺色主題用較深的色階（白底上對比 ≥ 4.5:1），深色主題用較亮的色階（深底上清楚，按鈕上的字改用深色）。

| 等級 | 意義 | 色相 | 淺色 `fg` | 淺色 `hover` | 淺色 `on` | 深色 `fg` | 深色 `hover` | 深色 `on` |
|---|---|---|---|---|---|---|---|---|
| TRACE | 非常細的程式追蹤 | 青（cyan） | `#0E7490` | `#155E75` | `#FFFFFF` | `#22D3EE` | `#67E8F9` | `#042F36` |
| DEBUG | 開發除錯 | 灰藍（slate） | `#64748B` | `#475569` | `#FFFFFF` | `#94A3B8` | `#CBD5E1` | `#0F172A` |
| INFO | 正常流程 | 藍 | `#2563EB` | `#1D4ED8` | `#FFFFFF` | `#60A5FA` | `#93C5FD` | `#0B1B33` |
| SUCCESS | 成功完成 | 綠 | `#15803D` | `#166534` | `#FFFFFF` | `#4ADE80` | `#86EFAC` | `#052E16` |
| WARNING | 異常但可繼續 | 琥珀 | `#B45309` | `#92400E` | `#FFFFFF` | `#FBBF24` | `#FCD34D` | `#1F1300` |
| ERROR | 單次操作失敗 | 紅 | `#DC2626` | `#B91C1C` | `#FFFFFF` | `#F87171` | `#FCA5A5` | `#2A0A0A` |
| CRITICAL | 系統級嚴重問題 | 洋紅（fuchsia） | `#A21CAF` | `#86198F` | `#FFFFFF` | `#E879F9` | `#F0ABFC` | `#3B0764` |

- CRITICAL 刻意不用更深的紅：和 ERROR 同色相時，小膠囊上很難分辨，改用洋紅做出明顯區隔

- `fg`：主色。勾選按鈕的底色、未勾選按鈕的文字色、記錄行的等級欄位色
- `hover`：勾選按鈕滑鼠移入時的底色
- `on`：勾選按鈕（實心底）上的文字色
- WARNING 淺色不用常見的 `#D97706`：白字在上面對比只有約 3.2:1，改用 `#B45309`（約 5:1）

**按鈕狀態**（兩個狀態都有該等級的底色，靠「實心 vs 淡色」區分開關）

| 狀態 | 底色 | 文字 | 外框 |
|---|---|---|---|
| 勾選（顯示中） | `fg` 實心 | `on` | `fg` |
| 勾選＋懸浮 | `hover` | `on` | `hover` |
| 未勾選（隱藏中） | `fg` 淡色（淺色 α 0.12／深色 α 0.16） | `fg` | `fg` 半透明（淺色 α 0.35／深色 α 0.45） |
| 未勾選＋懸浮 | `fg` 淡色加深（淺色 α 0.24／深色 α 0.30） | `fg` | `fg` |

**實作方式**

- `theme.py` 新增 frozen dataclass `LevelColor(fg, hover, on)`；`ThemePalette` 新增欄位 `levels: tuple[LevelColor, ...]`（7 個，順序同 `LEVELS`）與 `level_alphas: tuple[float, float, float]`（淡底、懸浮、外框），以及方法 `level(name) -> LevelColor`；`LIGHT`／`DARK` 各自填入上表。用 tuple 而非 dict，`ThemePalette` 才能維持可 hash
- `build_stylesheet()` 依 `levels` 產生每個等級的 4 條 QSS 規則（`QPushButton[variant="level"][level="TRACE"]` 等，共 28 條），淡色以 `rgba(r, g, b, α)` 由 `fg` 換算，不另外寫死
- 膠囊 `border-radius` 必須小於按鈕高度的一半（實測 8px），否則 Qt 會忽略圓角畫成直角
- 記錄行上色與按鈕共用同一組 `LevelColor`，按鈕和文字的顏色保證一致
- 實測對比（WCAG）：淺色 `fg`/`surface` 4.76～6.32、`on`/`fg` 同值；深色 `fg`/`surface` 5.12～8.48、`on`/`fg` 6.09～10.93
- `test_theme.py` 新增：兩個主題的 `levels` 都剛好涵蓋 `LEVELS` 的 7 個等級且都產生了 QSS 規則；每個 `fg` 在 `surface` 上、`on` 在 `fg` 上的對比都 ≥ 4.5:1；同一主題內 7 個 `fg` 互不相同

## 7. 錯誤處理

- sink 內任何例外吞掉，不影響 loguru 其他 sink 與主流程
- 背景執行緒寫記錄時主視窗可能正在關閉：LogBridge emit 的 `RuntimeError` 忽略；`MainWindow.closeEvent` 接受關閉後 `buffer.remove_listener`
- `settings.ini` 中 `console/height` 非數字或超出範圍時回到預設值

## 8. 測試

`tests/test_log_buffer.py`（不需 Qt）

- `normalize_level`：7 個內建等級原樣保留（不合併）；自訂等級依數值歸類（no=35 → WARNING、no=1 → TRACE、no=60 → CRITICAL）
- `logger.trace()` 也會進 buffer（sink 等級為 TRACE）
- 以真實 `logger.add(buffer.write, ...)` 寫入後 `snapshot()` 內容、等級、時間正確；含例外時 message 帶 traceback
- 超過容量丟掉最舊的；`clear()`；listener 收到新記錄、`remove_listener` 後不再收到、listener 丟例外不影響寫入
- 多執行緒同時寫入不遺失（容量內）

`tests/test_log_console.py`

- 面板建立時補顯示既有記錄；之後的新記錄即時出現
- 從背景執行緒寫記錄，事件處理後出現在面板
- 面板有 7 顆等級鈕，依 TRACE→CRITICAL 順序排列
- 預設只顯示 DEBUG、INFO、SUCCESS；TRACE、SUCCESS、CRITICAL 各自獨立切換（例如只開 SUCCESS 時看不到 INFO）；`levelsChanged` 帶出正確集合
- 等級鈕上的筆數正確（含被隱藏的等級）
- 搜尋：不分大小寫、與等級篩選同時生效、清空搜尋還原
- 清除會清空面板與 buffer；複製只複製可見內容
- 主題切換後顏色改變（檢查 ERROR 行等級欄位的文字顏色 = 該主題 `level("ERROR").fg`）
- 自動捲動：在底端時跟著捲；往上捲後新增記錄不改變捲軸位置
- `ConsoleSettings`：無鍵時預設值、`debug,info,success,critical` 讀出四個等級、空字串為空集合、未知等級忽略、高度非法時回預設

`tests/test_main_window.py`（新增案例）

- footer 有「主控台」按鈕且排在「關於」之後
- 按鈕、`Ctrl+`` `、✕ 都能切換面板，按鈕勾選狀態同步，`console/visible` 寫入 settings.ini
- `console/visible=true` 啟動時面板直接顯示；`console/levels` 的值被套用
- 設定頁（F11）開啟時面板仍在、主控台按鈕可用、連線清單停用
- 執行請求後主控台出現「執行請求」（INFO）與「請求完成」（SUCCESS）記錄；讀取 WSDL 後出現「讀取完成」（SUCCESS）

`tests/test_entry_point.py`

- `ws_tool.py` 拆出 `setup_logging(log_dir, config) -> tuple[LogBuffer, list[int]]`（buffer 與新增的 loguru handler id），由 `main()` 呼叫；測試直接呼叫它：`logger.debug()` 會進 buffer，但 `level: info` 時不會寫進 `run.log`（測試結束移除加入的 sink）
