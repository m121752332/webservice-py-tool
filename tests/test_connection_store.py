# -*- coding: utf-8 -*-
import json
import shutil
from pathlib import Path

import pytest

from src.core.connection_store import Connection, ConnectionStore, Folder

REPO_PROFILE = Path(__file__).resolve().parents[1] / "src" / "app_data" / "connections.profile"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_file_creates_empty_profile(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    assert store.all() == []
    assert read_json(path) == {"folders": [], "connections": []}
    assert store.recovered_from_corruption is False


def test_add_persists_blank_connection(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    conn = store.add()
    assert (conn.name, conn.url, conn.methods) == ("", "", [])
    assert len(conn.uuid) == 36
    assert read_json(path) == {
        "folders": [],
        "connections": [{"uuid": conn.uuid, "name": "", "url": "", "method": [], "folder": None}],
    }


def test_updates_persist_and_reload(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    uuid = store.add().uuid
    store.rename(uuid, "TIPTOP 正式區")
    store.set_url(uuid, "http://host/ws?WSDL")
    store.set_methods(uuid, ["GetPOData", "AddTwo"])
    reloaded = ConnectionStore(path)
    assert reloaded.all() == [Connection(uuid, "TIPTOP 正式區", "http://host/ws?WSDL", ["GetPOData", "AddTwo"])]
    assert "TIPTOP 正式區" in path.read_text(encoding="utf-8")


def test_remove(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    first = store.add().uuid
    second = store.add().uuid
    store.remove(first)
    assert [conn.uuid for conn in store.all()] == [second]


def test_get_returns_none_for_unknown_uuid(tmp_path):
    assert ConnectionStore(tmp_path / "c.profile").get("nope") is None


@pytest.mark.parametrize("action", [
    lambda store: store.remove("nope"),
    lambda store: store.rename("nope", "x"),
    lambda store: store.set_url("nope", "x"),
    lambda store: store.set_methods("nope", []),
])
def test_unknown_uuid_raises_key_error(tmp_path, action):
    with pytest.raises(KeyError):
        action(ConnectionStore(tmp_path / "c.profile"))


def test_returned_connections_are_copies(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    uuid = store.add().uuid
    store.get(uuid).methods.append("Injected")
    store.all()[0].name = "changed"
    assert store.get(uuid) == Connection(uuid, "", "", [])


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text("{ not json", encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is True
    assert store.all() == []
    assert store.backup_path == tmp_path / "connections.profile.bak"
    assert store.backup_path.read_text(encoding="utf-8") == "{ not json"
    assert read_json(path) == {"folders": [], "connections": []}


def test_wrong_structure_is_treated_as_corrupt(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is True
    assert store.all() == []


def test_reads_legacy_profile(tmp_path):
    path = tmp_path / "connections.profile"
    legacy = {"connections": [{
        "uuid": "3151eae3-ffd2-4d24-9e11-2744aa103521",
        "name": "TIPTOP_TOPTEST",
        "url": "http://172.20.3.22/web/ws/r/aws_ttsrv2_toptest?WSDL",
        "method": ["CRMGetCustomerData", "GetPOData"],
    }]}
    path.write_text(json.dumps(legacy, indent=4), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.all() == [Connection(
        "3151eae3-ffd2-4d24-9e11-2744aa103521",
        "TIPTOP_TOPTEST",
        "http://172.20.3.22/web/ws/r/aws_ttsrv2_toptest?WSDL",
        ["CRMGetCustomerData", "GetPOData"],
    )]
    assert store.recovered_from_corruption is False
    assert store.folders() == []


def test_reads_repo_profile_copy(tmp_path):
    path = tmp_path / "connections.profile"
    shutil.copy(REPO_PROFILE, path)
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is False
    assert store.all()
    assert all(conn.uuid for conn in store.all())


def test_string_method_is_treated_as_corrupt(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(
        json.dumps({"connections": [{"uuid": "u", "name": "", "url": "", "method": "abc"}]}),
        encoding="utf-8",
    )
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is True
    assert store.all() == []
    assert read_json(path) == {"folders": [], "connections": []}


def test_blank_uuid_gets_generated(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({"connections": [{"uuid": "", "name": "a", "url": "u", "method": []}]}), encoding="utf-8")
    store = ConnectionStore(path)
    uuid = store.all()[0].uuid
    assert len(uuid) == 36
    assert read_json(path)["connections"][0]["uuid"] == uuid


def group(store, folder):
    return [conn.uuid for conn in store.all() if conn.folder == folder]


def test_folder_add_rename_expand_persist(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("TIPTOP")
    assert folder == Folder(folder.uuid, "TIPTOP", True)
    assert len(folder.uuid) == 36
    store.rename_folder(folder.uuid, "ERP")
    store.set_folder_expanded(folder.uuid, False)
    assert ConnectionStore(path).folders() == [Folder(folder.uuid, "ERP", False)]
    assert read_json(path)["folders"] == [{"uuid": folder.uuid, "name": "ERP", "expanded": False}]


def test_get_folder_and_copies(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    uuid = store.add_folder("F").uuid
    assert store.get_folder("nope") is None
    store.get_folder(uuid).name = "changed"
    store.folders()[0].expanded = False
    assert store.get_folder(uuid) == Folder(uuid, "F", True)


def test_add_into_folder_appends_to_its_group(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F").uuid
    a = store.add(folder).uuid
    b = store.add().uuid
    c = store.add(folder).uuid
    assert group(store, folder) == [a, c]
    assert group(store, None) == [b]
    saved = read_json(path)["connections"]
    assert [item["folder"] for item in saved] == [folder, None, folder]


def test_remove_folder_moves_connections_to_root_end(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    folder = store.add_folder("F").uuid
    a = store.add(folder).uuid
    b = store.add().uuid
    c = store.add(folder).uuid
    d = store.add().uuid
    store.remove_folder(folder)
    assert store.folders() == []
    assert group(store, None) == [b, d, a, c]


def test_move_connection_between_groups_and_within_group(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F").uuid
    a = store.add().uuid
    b = store.add().uuid
    c = store.add(folder).uuid
    store.move_connection(a, folder, 0)
    assert group(store, folder) == [a, c] and group(store, None) == [b]
    store.move_connection(c, folder, 0)
    assert group(store, folder) == [c, a]
    store.move_connection(c, None, 99)  # 超出範圍夾到結尾
    assert group(store, None) == [b, c]
    store.move_connection(a, None, -5)  # 負數夾到開頭
    assert group(store, None) == [a, b, c] and group(store, folder) == []
    assert [conn.uuid for conn in ConnectionStore(path).all()] == [a, b, c]


def test_move_folder(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    f1, f2, f3 = (store.add_folder(name).uuid for name in ("1", "2", "3"))
    store.move_folder(f3, 0)
    assert [f.uuid for f in store.folders()] == [f3, f1, f2]
    store.move_folder(f3, 99)
    assert [f.uuid for f in store.folders()] == [f1, f2, f3]
    store.move_folder(f1, 1)
    assert [f.uuid for f in store.folders()] == [f2, f1, f3]


@pytest.mark.parametrize("action", [
    lambda store: store.add("nope"),
    lambda store: store.rename_folder("nope", "x"),
    lambda store: store.remove_folder("nope"),
    lambda store: store.set_folder_expanded("nope", False),
    lambda store: store.move_folder("nope", 0),
    lambda store: store.move_connection("nope", None, 0),
    lambda store: store.move_connection(store.add().uuid, "nope", 0),
])
def test_unknown_folder_uuid_raises_key_error(tmp_path, action):
    with pytest.raises(KeyError):
        action(ConnectionStore(tmp_path / "c.profile"))


def test_dangling_folder_reference_moves_to_root(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({"folders": [], "connections": [
        {"uuid": "u", "name": "", "url": "", "method": [], "folder": "gone"},
    ]}), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is False
    assert store.get("u").folder is None
    assert read_json(path)["connections"][0]["folder"] is None


def test_folder_defaults_and_blank_uuid(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({"folders": [{"uuid": "", "name": "F"}], "connections": []}), encoding="utf-8")
    store = ConnectionStore(path)
    folder = store.folders()[0]
    assert len(folder.uuid) == 36
    assert (folder.name, folder.expanded) == ("F", True)
    assert read_json(path)["folders"][0]["uuid"] == folder.uuid


@pytest.mark.parametrize("data", [
    {"folders": "abc", "connections": []},
    {"folders": [1], "connections": []},
    {"folders": [{"uuid": "f", "name": "F", "expanded": "yes"}], "connections": []},
    {"folders": [], "connections": [{"uuid": "u", "name": "", "url": "", "method": [], "folder": ["f"]}]},
])
def test_bad_folder_data_is_treated_as_corrupt(tmp_path, data):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps(data), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is True
    assert store.all() == [] and store.folders() == []
    assert read_json(path) == {"folders": [], "connections": []}


def test_colors_default_to_none_and_are_not_written(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F")
    conn = store.add(folder.uuid)
    assert store.get_folder(folder.uuid).color is None
    assert store.get(conn.uuid).color is None
    data = read_json(path)
    assert "color" not in data["folders"][0]  # 未設色不寫入，格式與舊版相同
    assert "color" not in data["connections"][0]


def test_set_colors_persist_reload_and_clear(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F")
    conn = store.add(folder.uuid)
    store.set_folder_color(folder.uuid, "blue")
    store.set_color(conn.uuid, "red")
    data = read_json(path)
    assert data["folders"][0]["color"] == "blue"
    assert data["connections"][0]["color"] == "red"
    reloaded = ConnectionStore(path)
    assert reloaded.get_folder(folder.uuid).color == "blue"
    assert reloaded.get(conn.uuid).color == "red"

    store.set_folder_color(folder.uuid, None)
    store.set_color(conn.uuid, "")
    data = read_json(path)
    assert "color" not in data["folders"][0]
    assert "color" not in data["connections"][0]


@pytest.mark.parametrize("value", [123, "", None, ["red"], {"k": "red"}])
def test_invalid_color_is_default_not_corruption(tmp_path, value):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({
        "folders": [{"uuid": "f", "name": "F", "expanded": True, "color": value}],
        "connections": [{"uuid": "u", "name": "", "url": "", "method": [], "folder": "f", "color": value}],
    }), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is False
    assert store.get_folder("f").color is None
    assert store.get("u").color is None


def test_unknown_color_key_is_kept_by_store(tmp_path):
    """核心層不認識色票，只保證型別；未知代號由 UI 當作預設色顯示"""
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({
        "folders": [],
        "connections": [{"uuid": "u", "name": "", "url": "", "method": [], "color": "magenta"}],
    }), encoding="utf-8")
    assert ConnectionStore(path).get("u").color == "magenta"


def test_removing_folder_keeps_connection_colors(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    folder = store.add_folder("F")
    conn = store.add(folder.uuid)
    store.set_folder_color(folder.uuid, "blue")
    store.set_color(conn.uuid, "green")
    store.remove_folder(folder.uuid)
    moved = store.get(conn.uuid)
    assert (moved.folder, moved.color) == (None, "green")


def test_set_color_unknown_uuid_raises_key_error(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    with pytest.raises(KeyError):
        store.set_color("nope", "red")
    with pytest.raises(KeyError):
        store.set_folder_color("nope", "red")
