# 主控台（Console）記錄面板設計

- 日期：2026-09-26
- 分支：`feat/log-console`

## 1. 目標與範圍

目前執行結果只能到 `app_data/logs/run.log` 查看。新增一個類似 VS Code Panel 的**主控台面板**，把程式從啟動、讀取 WSDL、執行請求到關閉期間的 loguru 記錄即時顯示在 UI 上。

**範圍內**

- 右側區域下方可收合的主控台面板，與上方內容以可拖曳的分割線隔開；工作區與設定頁（F11）共用
- 側欄底部「關於」後面新增「主控台」按鈕切換開關；快捷鍵 `Ctrl+`` ` 同樣可切換；面板標題列有 ✕ 可關閉
- 收集 DEBUG 以上的全部記錄；程式啟動後、面板建立前的記錄也會保留並補顯示
- 等級篩選（可複選的等級切換鈕），預設開啟 DEBUG、INFO；選擇結果記在 `settings.ini`，下次啟動沿用
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
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")   # 篩選鈕的四個等級，依嚴重度排列
DEFAULT_CAPACITY = 5000

@dataclass(frozen=True)
class LogEntry:
    time: datetime
    level: str      # 已正規化為 LEVELS 其中之一
    message: str    # 含例外 traceback（多行）

def normalize_level(name: str) -> str
    # TRACE、DEBUG → DEBUG；INFO、SUCCESS → INFO；WARNING → WARNING；ERROR、CRITICAL → ERROR
    # 自訂或未知等級依 loguru 數值（no）歸到最接近的較低等級

class LogBuffer:
    def __init__(self, capacity: int = DEFAULT_CAPACITY)
    def write(self, message) -> None       # loguru sink；從 message.record 取 time、level、message、exception
    def snapshot(self) -> list[LogEntry]
    def clear(self) -> None
    def add_listener(self, callback: Callable[[LogEntry], None]) -> None
    def remove_listener(self, callback) -> None
```

- 內部以 `collections.deque(maxlen=capacity)` 保存，`threading.Lock` 保護；超過上限自動丟掉最舊的
- listener 在鎖外呼叫，listener 丟出的例外吞掉，避免記錄動作把主流程弄壞
- `ws_tool.setup_logging()`（由 `main()` 呼叫）在加入 `run.log` sink 之後立刻 `logger.add(buffer.write, level="DEBUG", format="{message}")`；例外內容從 `record["exception"]` 自行格式化成 traceback 文字附在 message 後
- `run.log` sink 的等級不受影響，仍依 `ws_tool.yaml`

## 4. 面板（`src/ui/log_console.py`）

### 4.1 `LogBridge(QObject)`

- `entryAdded = Signal(object)`；建構時 `buffer.add_listener(self._on_entry)`，`_on_entry` 只做 `entryAdded.emit(entry)`
- QObject 住在主執行緒，背景執行緒 emit 時 Qt 自動以佇列方式送到主執行緒
- emit 時若物件已被刪除（程式關閉中）忽略 `RuntimeError`，比照 `workers.py`

### 4.2 `ConsolePanel(QWidget)`，objectName `ConsolePanel`

版面：

```
┌ 主控台  [DEBUG 12][INFO 30][WARNING 1][ERROR 0]   [🔍 搜尋記錄…      ] [清除][複製] ✕ ┐
│ 14:02:11.532  INFO     程式啟動 · TIPTOP WebService Tool v2.0.1                      │
│ 14:02:15.004  INFO     讀取 WSDL · URL=http://…                                        │
│ …（QPlainTextEdit，唯讀、等寬字型、不自動換行）                                       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- **等級切換鈕**：四個 checkable `QPushButton`（`variant="level"`，`level` 屬性對應 QSS 顏色），文字為「等級 ＋ 目前暫存中的筆數」。預設只開 DEBUG、INFO 時，WARNING/ERROR 的筆數仍會顯示，使用者看得出有被隱藏的錯誤
- **搜尋框**：`QLineEdit`，含清除鈕；輸入後延遲 200 ms 重新篩選（避免每打一個字就重建）；比對 `message` 與等級文字，不分大小寫
- **文字區**：`QPlainTextEdit`（objectName `ConsoleView`），不使用 `setMaximumBlockCount`（一筆 traceback 佔多行，以行數限制會切壞記錄），由面板自己保存記錄清單，超過 `DEFAULT_CAPACITY` 的 110% 時一次修剪回 `DEFAULT_CAPACITY` 筆並重建文字區（分批修剪，避免每筆新記錄都重建）；每行格式 `HH:MM:SS.mmm  LEVEL    訊息`，多行訊息（traceback）後續行縮排
- **上色**：以 `QTextCharFormat` 依等級上色，顏色取自主題色票——DEBUG `text_muted`、INFO `text`、WARNING `warning`、ERROR `danger`；主題切換時 `set_palette()` 重新上色（重建內容）
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
| `console/levels` | str | `debug,info` | 開啟的等級，逗號分隔、小寫；可手動編輯，例如改成 `debug,info,error` 啟動就會顯示 ERROR |

- 讀取時忽略未知等級與空白；結果為空集合時（例如全部取消勾選）照樣保存為空字串，代表全部隱藏——使用者自己選的狀態要被尊重；只有鍵**不存在**時才用預設值
- 每次變更立即 `setValue` ＋ `sync()`，比照 `ThemeManager`

## 5. 主視窗整合（`src/ui/main_window.py`）

- 建構子新增選填參數 `settings: QSettings | None = None`、`log_buffer: LogBuffer | None = None`；未提供時各自建立暫時物件（記憶體中的 LogBuffer、不落地的設定），既有測試不需修改
- 右側由 `root.addWidget(self.stack, 1)` 改為垂直 `QSplitter`：上方 `stack`、下方 `ConsolePanel`；`setChildrenCollapsible(False)`，面板最小高度 120 px
- 面板在建構時就建立（啟動時若 `console/visible=true` 直接顯示）；隱藏時以 `hide()` 處理，splitter 自動把空間還給上方
- footer 新增 `self.console_button = styled_button("主控台", "footer", "開關主控台 (Ctrl+`)")`，`setCheckable(True)`，搭配 `console_icon()`，排在「關於」之後
- 新增 `toggle_console()`、`set_console_visible(bool)`：同步按鈕勾選、寫入 `console/visible`；splitter 拖曳結束（`splitterMoved`）時寫入 `console/height`
- `Ctrl+`` ` 為全域快捷鍵，不放進 `_workspace_shortcuts`，設定頁開著時也能用
- 設定頁模式（`_set_settings_mode`）目前停用整個 `sidebar`，但 footer 在 sidebar 內，主控台按鈕會跟著被停用。改為**只停用 `connection_list`**，footer 三顆按鈕（主題、關於、主控台）在設定頁都維持可用；`test_main_window.py` 中檢查 `sidebar.isEnabled()` 的兩處改為檢查 `connection_list.isEnabled()`
- `_on_theme_changed` 同時呼叫 `console_panel.set_palette(palette)`

**補充記錄點**（皆 INFO，除非另外註明）

| 時點 | 位置 | 內容 |
|---|---|---|
| 程式啟動 | `ws_tool.main()` | `程式啟動 · {name} {version}` |
| 設定與資料位置 | `ws_tool.main()` | `設定檔={config_path} · 連線資料={data_dir} · 記錄={log_dir}`（DEBUG） |
| 讀取 WSDL 開始 | `_on_load_clicked` | `讀取 WSDL · URL={url}` |
| 讀取 WSDL 完成 | `_on_methods_loaded` | `讀取完成 · {n} 個方法` |
| 取消 | `_cancel` | `已取消 {讀取/執行}` |
| 關閉程式 | `closeEvent` 確認後 | `程式關閉` |

## 6. 主題與圖示

- `icons.py` 新增 `console_icon()`：漸層圓角方塊（`#10B981` → `#0D9488`）上畫白色 `>_`，風格與既有兩顆一致
- `theme.py` 新增 QSS（顏色一律用色票變數）：
  - `QWidget#ConsolePanel { background: $surface; border-top: 1px solid $border; }`
  - `QPlainTextEdit#ConsoleView`：無外框、等寬字型（`Cascadia Mono`、`Consolas`）
  - `QPushButton[variant="level"]`：小尺寸膠囊；`:checked` 時底色 `$surface_hover`、外框用對應等級色（`level="WARNING"` → `$warning`，`ERROR` → `$danger`，其餘 `$accent`）；未勾選時文字 `$text_muted`
  - `QPushButton[variant="footer"]:checked { border-color: $accent; background: $surface_hover; }`
- 側欄寬 260 px，三顆 footer 按鈕（圖示 20 px ＋ 2～3 個中文字）可排在同一列；若實測超出，改縮小按鈕左右 padding，不改側欄寬度

## 7. 錯誤處理

- sink 內任何例外吞掉，不影響 loguru 其他 sink 與主流程
- 背景執行緒寫記錄時主視窗可能正在關閉：LogBridge emit 的 `RuntimeError` 忽略；`MainWindow.closeEvent` 接受關閉後 `buffer.remove_listener`
- `settings.ini` 中 `console/height` 非數字或超出範圍時回到預設值

## 8. 測試

`tests/test_log_buffer.py`（不需 Qt）

- `normalize_level`：TRACE/DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL 對應正確，自訂等級依數值歸類
- 以真實 `logger.add(buffer.write, ...)` 寫入後 `snapshot()` 內容、等級、時間正確；含例外時 message 帶 traceback
- 超過容量丟掉最舊的；`clear()`；listener 收到新記錄、`remove_listener` 後不再收到、listener 丟例外不影響寫入
- 多執行緒同時寫入不遺失（容量內）

`tests/test_log_console.py`

- 面板建立時補顯示既有記錄；之後的新記錄即時出現
- 從背景執行緒寫記錄，事件處理後出現在面板
- 預設只顯示 DEBUG、INFO；切換 ERROR 後顯示；`levelsChanged` 帶出正確集合
- 等級鈕上的筆數正確（含被隱藏的等級）
- 搜尋：不分大小寫、與等級篩選同時生效、清空搜尋還原
- 清除會清空面板與 buffer；複製只複製可見內容
- 主題切換後顏色改變（檢查 ERROR 行的文字顏色 = 色票 `danger`）
- 自動捲動：在底端時跟著捲；往上捲後新增記錄不改變捲軸位置
- `ConsoleSettings`：無鍵時預設值、`debug,info,error` 讀出三個等級、空字串為空集合、未知等級忽略、高度非法時回預設

`tests/test_main_window.py`（新增案例）

- footer 有「主控台」按鈕且排在「關於」之後
- 按鈕、`Ctrl+`` `、✕ 都能切換面板，按鈕勾選狀態同步，`console/visible` 寫入 settings.ini
- `console/visible=true` 啟動時面板直接顯示；`console/levels` 的值被套用
- 設定頁（F11）開啟時面板仍在、主控台按鈕可用、連線清單停用
- 執行請求後主控台出現「執行請求」與「請求完成」記錄

`tests/test_entry_point.py`

- `ws_tool.py` 拆出 `setup_logging(log_dir, config) -> LogBuffer`，由 `main()` 呼叫；測試直接呼叫它：`logger.debug()` 會進 buffer，但 `level: info` 時不會寫進 `run.log`（測試結束移除加入的 sink）
