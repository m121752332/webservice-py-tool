# 連線清單目錄（書籤管理）設計

- 日期：2026-09-25
- 分支：`feat/connection-folders`

## 1. 目標與範圍

左側連線清單支援類似 Postman 的目錄分組：連線可放進目錄、目錄可重新命名、可用拖曳或右鍵選單移動與排序。

**範圍內**

- 單層目錄：最外層可放目錄與連線，目錄內只放連線，不能巢狀
- 新增、重新命名（清單內直接編輯）、刪除目錄
- 拖曳：連線移進／移出目錄、連線排序、目錄排序
- 右鍵選單「移動到 ▸」
- 目錄展開／收合狀態記憶
- 搜尋時顯示符合項目所屬的目錄

**不在範圍內**

- 巢狀目錄
- 多選拖曳、多選刪除
- 目錄層級的設定（例如共用網址、預設逾時）
- 版本號與 `ws_tool.yaml` 變更

**相容性要求**

- 舊版 `connections.profile`（沒有 `folders`／`folder` 欄位）可直接讀取，所有連線視為在最外層
- 新格式只增加欄位，舊版程式仍可讀取（會忽略目錄資訊）

## 2. 資料層（`src/core/connection_store.py`）

### 2.1 資料結構

```python
@dataclass
class Folder:
    uuid: str
    name: str = ""
    expanded: bool = True

@dataclass
class Connection:
    uuid: str
    name: str = ""
    url: str = ""
    methods: list[str] = field(default_factory=list)
    folder: str | None = None      # 所屬目錄 uuid，None 表示最外層
```

### 2.2 檔案格式

```json
{
    "folders": [
        {"uuid": "...", "name": "TIPTOP", "expanded": true}
    ],
    "connections": [
        {"uuid": "...", "name": "...", "url": "...", "method": ["..."], "folder": "<目錄 uuid 或 null>"}
    ]
}
```

- `folders` 陣列順序 = 目錄顯示順序
- `connections` 陣列順序 = 全域順序；同一目錄（或最外層）內的連線依其在陣列中的相對先後排列

### 2.3 `ConnectionStore` 介面

既有方法（`all`、`get`、`remove`、`rename`、`set_url`、`set_methods`）不變。每次修改立即寫回檔案，對外只回傳複本。

| 方法 | 行為 |
|---|---|
| `folders() -> list[Folder]` | 依順序回傳所有目錄的複本 |
| `get_folder(uuid) -> Folder \| None` | 取得單一目錄的複本 |
| `add(folder: str \| None = None) -> Connection` | 新連線加在該目錄（或最外層）最後面；目錄不存在時拋 `KeyError` |
| `add_folder(name: str) -> Folder` | 新目錄排在所有目錄最後面 |
| `rename_folder(uuid, name)` | 重新命名目錄 |
| `remove_folder(uuid)` | 刪除目錄；其連線維持相對順序，移到最外層連線的最後面 |
| `set_folder_expanded(uuid, expanded: bool)` | 記錄展開狀態 |
| `move_connection(uuid, folder: str \| None, index: int)` | 將連線移到指定目錄（或最外層）群組中的第 `index` 個位置（以移除自身後的群組計算）；`index` 超出範圍時夾到群組結尾 |
| `move_folder(uuid, index: int)` | 將目錄移到第 `index` 個位置（以移除自身後的清單計算），超出範圍時夾到結尾 |

不存在的 uuid 一律拋 `KeyError`（與既有 `_find` 一致）。

### 2.4 讀檔容錯

| 狀況 | 處理 |
|---|---|
| 沒有 `folders` 鍵 | 視為空目錄清單 |
| 連線沒有 `folder` 鍵或為 `null` | 在最外層 |
| 連線的 `folder` 指向不存在的目錄 | 改為最外層，並寫回檔案 |
| 目錄沒有 `uuid` | 補新 uuid，並寫回檔案 |
| `folders` 不是清單、項目不是物件、`expanded` 不是布林 | 走既有損毀流程：備份為 `.bak` 後重建 |

store 不檢查名稱是否為空，由 UI 負責。「至少一筆連線」的規則維持在 `MainWindow`。

## 3. 左側清單元件（`src/ui/connection_list.py`）

### 3.1 元件

- `QListWidget` 改為 `QTreeWidget`（隱藏標頭，`objectName` 維持 `ConnectionList`）
- 連線列沿用 `ConnectionItemWidget`（名稱 + 網址兩行，以 `setItemWidget` 放置）
- 目錄列為一般文字項目（可編輯旗標），顯示名稱；名稱為空時顯示「未命名目錄」
- `theme.py` 的 QSS 選擇器由 `QListWidget#ConnectionList` 改為 `QTreeWidget#ConnectionList`，並補上目錄列樣式

### 3.2 對外介面

| 成員 | 說明 |
|---|---|
| `set_tree(folders, connections, select_uuid=None)` | 取代 `set_connections`，依 store 資料重建整棵樹；`select_uuid` 可為連線或目錄 uuid，未指定時選第一筆連線 |
| `update_connection(conn)` | 不變 |
| `select(uuid)` | 可選取連線或目錄 |
| `current_uuid()` | 目前選取的連線 uuid；選到目錄或未選取時為 `None` |
| `current_folder()` | 選到目錄時回傳該目錄 uuid；選到連線時回傳其所屬目錄（可能為 `None`） |
| `edit_folder(uuid)` | 選取該目錄並進入清單內改名 |
| `request_delete_current()` | 依目前選取送出 `deleteRequested` 或 `deleteFolderRequested`（原 `_request_delete_current` 公開化） |
| `visible_uuids()` | 目前可見的連線 uuid（不含目錄） |
| `clear_search()`、`set_busy(busy)` | 不變；`set_busy` 也停用「+ 新增目錄」按鈕 |

**訊號**

| 訊號 | 時機 |
|---|---|
| `selectionChanged(str)` | 選取變更；選到目錄或未選取時送 `""` |
| `addRequested()` | 新增連線 |
| `addFolderRequested()` | 新增目錄 |
| `deleteRequested(str)` | 刪除連線 |
| `deleteFolderRequested(str)` | 刪除目錄 |
| `folderRenamed(str, str)` | 清單內改名完成；去除前後空白後為空字串時還原原名，不送訊號 |
| `folderExpandedChanged(str, bool)` | 使用者展開／收合目錄（搜尋造成的暫時展開不送） |
| `connectionMoved(str, object, int)` | 拖放或右鍵移動連線：uuid、目標目錄 uuid 或 `None`、群組內 index |
| `folderMoved(str, int)` | 拖放目錄：uuid、目錄清單 index |

### 3.3 互動

- 點一下目錄列：展開／收合
- Delete 鍵（清單焦點時）與 F2（主視窗快捷鍵）：刪除目前選取的連線或目錄
- 改名：右鍵「重新命名」，或新建目錄後自動進入改名；雙擊與 F2 不用於改名（避免與展開／刪除衝突）

**右鍵選單**

| 位置 | 選項 |
|---|---|
| 連線 | 移動到 ▸（最外層、各目錄；目前所在位置停用）、刪除 |
| 目錄 | 新增連線到此目錄、重新命名、刪除目錄 |
| 空白處 | 新增連線、新增目錄 |

「移動到」送出 `connectionMoved(uuid, folder, 目標群組結尾 index)`。「新增連線到此目錄」先選取該目錄再送 `addRequested`。

**底部按鈕**：「+ 新增連線」與「+ 新增目錄」並排。

### 3.4 拖放規則

拖放模式為 `InternalMove`，但覆寫 `dropEvent`：不呼叫預設實作（Qt 不自行搬移項目），只計算目標位置並送出訊號，由主視窗更新 store 後重建樹。位置計算獨立成純函式 `resolve_drop(...)` 以便測試。

拖曳連線：

| 放下位置 | 結果 |
|---|---|
| 目錄列上（OnItem） | 移到該目錄最後面 |
| 連線列上方／下方 | 移到該連線所在群組，位於其前／後 |
| 連線列上（OnItem） | 視同放在該連線下方 |
| 最外層目錄列上方／下方 | 移到最外層連線的第一個位置（最外層固定目錄在前、連線在後） |
| 清單空白處 | 移到最外層連線最後面 |

拖曳目錄：

| 放下位置 | 結果 |
|---|---|
| 目錄列上方 | 移到該目錄之前 |
| 目錄列下方或目錄列上（OnItem） | 移到該目錄之後 |
| 目錄內的連線列 | 移到該連線所屬目錄之後 |
| 最外層連線列或空白處 | 移到所有目錄最後面 |

目錄永遠不會被放進其他目錄。

搜尋欄有文字時停用拖放（篩選後的畫面位置與實際順序不對應）。

### 3.5 搜尋

- 連線名稱或網址符合 → 顯示該連線與其所屬目錄
- 目錄名稱符合 → 顯示該目錄與其所有連線
- 有符合項目的目錄在搜尋期間強制展開，不寫回展開狀態；清除搜尋後還原為 store 記錄的展開狀態
- 沒有任何符合項目的目錄隱藏

## 4. 主視窗串接（`src/ui/main_window.py`）

新增 `_refresh_tree(select_uuid=None)`：`connection_list.set_tree(store.folders(), store.all(), select_uuid)`。所有結構變動都先更新 store 再呼叫此方法。

| 觸發 | 處理 |
|---|---|
| `addRequested`／F1 | 保存欄位 → `store.add(connection_list.current_folder())` → 清除搜尋 → 重建並選取新連線 → 焦點移到名稱欄位 |
| `addFolderRequested` | 保存欄位 → 清除搜尋 → `store.add_folder("新目錄")` → 重建 → `edit_folder(新目錄)` |
| `folderRenamed` | `store.rename_folder`（畫面文字已更新，不重建） |
| `deleteFolderRequested` | 確認「確定要刪除目錄「X」嗎？裡面的 N 筆連線會移到最外層。」（N 為 0 時省略後半句）→ `store.remove_folder` → 重建並保留原選取連線 |
| `connectionMoved`／`folderMoved` | `store.move_connection`／`store.move_folder` → 重建並保留原選取 |
| `folderExpandedChanged` | `store.set_folder_expanded` |
| F2 | `connection_list.request_delete_current()` |

- 以上操作在 `_pending`（讀取 WSDL／執行請求中）時一律忽略；清單本身也已停用
- 刪除最後一筆連線時自動在最外層新增一筆（沿用既有規則）
- `_load_initial_connections` 改用 `_refresh_tree()`

## 5. 測試

**`tests/test_connection_store.py`**

- 新增／改名／刪除目錄；刪除後連線依原順序回到最外層結尾
- `add(folder)` 放在目錄結尾；目錄不存在時 `KeyError`
- `move_connection` 跨目錄與同群組排序、index 夾限
- `move_folder` 排序
- `set_folder_expanded` 寫回
- 舊格式檔案讀取；`folder` 指向不存在目錄時修正並寫回；目錄缺 uuid 補齊
- `folders` 型別錯誤走損毀流程
- 存檔後重新載入結果一致

**`tests/test_connection_list.py`**

- 樹狀呈現：目錄在前、連線在後，連線在正確目錄下，展開狀態套用
- 選到目錄時 `selectionChanged("")`、`current_folder()` 正確
- 改名送出 `folderRenamed`；空白名稱還原且不送訊號
- `resolve_drop` 各規則
- 搜尋時目錄顯示／隱藏、暫時展開、清除後還原，且不送 `folderExpandedChanged`
- 搜尋中停用拖放
- 右鍵選單項目內容與「移動到」訊號
- Delete 鍵依選取類型送出對應訊號

**`tests/test_main_window.py`**

- 選到目錄時新增連線，新連線在該目錄
- 新增目錄後進入改名，改名寫入檔案
- 刪除目錄後連線移到最外層，檔案內容正確
- 選到目錄按 F2 刪除該目錄
- 移動訊號寫入檔案並保留選取
- 忙碌時「+ 新增目錄」停用
