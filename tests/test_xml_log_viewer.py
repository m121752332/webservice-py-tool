# -*- coding: utf-8 -*-
from dataclasses import replace
from datetime import datetime

import pytest

from src.core.xml_log import CallRecord, format_record
from src.ui.theme import DARK, LIGHT
from src.ui.xml_log_viewer import TAB_FIELDS, XmlLogViewer, matches
from tests.helpers import wait_until

BASE = CallRecord(
    time=datetime(2026, 9, 26, 9, 0, 0), connection="訂單服務", url="http://h/order?wsdl", method="GetOrder",
    status="success", elapsed=0.5, size=10, params="<Req>A-001</Req>", response="<ok/>",
)
RECORDS = [
    BASE,
    replace(BASE, time=datetime(2026, 9, 26, 10, 0, 0), method="CancelOrder", params="<Req>A-002</Req>"),
    replace(BASE, time=datetime(2026, 9, 26, 11, 0, 0), connection="", url="http://h/stock?wsdl",
            method="GetStock", status="failed", error="TimeoutError: 逾時", response=""),
]


def write_log(path, records, content="params"):
    path.write_text("".join(format_record(r, content) for r in records), encoding="utf-8")


@pytest.fixture
def viewer(qapp, tmp_path):
    write_log(tmp_path / "ws_xml.log", RECORDS)
    write_log(tmp_path / "ws_xml_20260925.log", [replace(BASE, time=datetime(2026, 9, 25, 8, 0, 0))])
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    wait_until(lambda: window.table.rowCount() == 3)
    yield window
    window.close()
    window.deleteLater()


def column(viewer, index):
    return [viewer.table.item(row, index).text() for row in range(viewer.table.rowCount())]


def combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_matches_keyword_is_case_insensitive():
    assert matches(BASE, None, None, "a-001")
    assert not matches(BASE, None, None, "zzz")
    assert matches(RECORDS[2], None, None, "逾時")
    assert not matches(BASE, "http://h/stock?wsdl", None, "")


def test_lists_newest_first_with_dates(viewer):
    assert column(viewer, 0) == ["11:00:00", "10:00:00", "09:00:00"]
    assert column(viewer, 1) == ["http://h/stock?wsdl", "訂單服務", "訂單服務"]
    assert column(viewer, 3) == ["失敗", "成功", "成功"]
    assert viewer.date_combo.count() == 2
    assert viewer.count_label.text() == "共 3 筆"


def test_connection_and_method_filters(viewer):
    assert combo_items(viewer.connection_combo) == ["全部", "http://h/stock?wsdl", "訂單服務"]
    viewer.connection_combo.setCurrentText("訂單服務")
    assert combo_items(viewer.method_combo) == ["全部", "CancelOrder", "GetOrder"]
    assert column(viewer, 2) == ["CancelOrder", "GetOrder"]
    viewer.method_combo.setCurrentText("GetOrder")
    assert column(viewer, 2) == ["GetOrder"]
    assert viewer.count_label.text() == "共 1 筆（全部 3 筆）"


def test_keyword_filter(viewer):
    viewer.search_edit.setText("a-002")
    wait_until(lambda: viewer.table.rowCount() == 1)
    assert column(viewer, 2) == ["CancelOrder"]


def test_switch_date_loads_archive(viewer):
    viewer.date_combo.setCurrentIndex(1)
    wait_until(lambda: viewer.table.rowCount() == 1)
    assert column(viewer, 0) == ["08:00:00"]


def test_detail_tabs_follow_content(viewer):
    viewer.table.selectRow(2)  # 09:00 成功，params 模式
    assert viewer.editors["params"].toPlainText() == "<Req>A-001</Req>"
    visible = [viewer.tabs.isTabVisible(i) for i in range(len(TAB_FIELDS))]
    assert visible == [True, True, False, False]
    viewer.table.selectRow(0)  # 失敗：回應分頁顯示錯誤訊息
    assert viewer.editors["response"].toPlainText() == "TimeoutError: 逾時"


def test_envelope_only_record_shows_soap_tabs(qapp, tmp_path):
    write_log(tmp_path / "ws_xml.log", [replace(BASE, sent="<S/>", received="<R/>")], content="envelope")
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    wait_until(lambda: window.table.rowCount() == 1)
    assert [window.tabs.isTabVisible(i) for i in range(len(TAB_FIELDS))] == [False, False, True, True]
    assert window.tabs.currentIndex() == 2
    window.close()


def test_resend_emits_selected_record(viewer):
    emitted = []
    viewer.resendRequested.connect(emitted.append)
    viewer.table.selectRow(1)
    viewer.resend_button.click()
    assert emitted[0].method == "CancelOrder" and emitted[0].params == "<Req>A-002</Req>"


def test_empty_dir_shows_hint(qapp, tmp_path):
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    assert window.table.rowCount() == 0
    assert window.count_label.text() == "尚無請求紀錄"
    assert not window.resend_button.isEnabled()
    window.close()


def test_read_failure_shows_error(qapp, tmp_path, monkeypatch):
    write_log(tmp_path / "ws_xml.log", RECORDS)
    from src.ui import xml_log_viewer

    def boom(_path):
        raise PermissionError("拒絕存取")

    monkeypatch.setattr(xml_log_viewer, "read_records", boom)
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    wait_until(lambda: window.notification.level == "error")
    assert window.notification.level == "error" and "拒絕存取" in window.notification.text
    window.close()


def test_set_palette_updates_editors(viewer):
    viewer.set_palette(DARK)
    assert all(editor.colors == DARK.xml for editor in viewer.editors.values())
