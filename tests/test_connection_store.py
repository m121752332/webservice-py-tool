# -*- coding: utf-8 -*-
import json
import shutil
from pathlib import Path

import pytest

from src.core.connection_store import Connection, ConnectionStore

REPO_PROFILE = Path(__file__).resolve().parents[1] / "src" / "app_data" / "connections.profile"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_file_creates_empty_profile(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    assert store.all() == []
    assert read_json(path) == {"connections": []}
    assert store.recovered_from_corruption is False


def test_add_persists_blank_connection(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    conn = store.add()
    assert (conn.name, conn.url, conn.methods) == ("", "", [])
    assert len(conn.uuid) == 36
    assert read_json(path) == {"connections": [{"uuid": conn.uuid, "name": "", "url": "", "method": []}]}


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
    assert read_json(path) == {"connections": []}


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


def test_reads_repo_profile_copy(tmp_path):
    path = tmp_path / "connections.profile"
    shutil.copy(REPO_PROFILE, path)
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is False
    assert store.all()
    assert all(conn.uuid for conn in store.all())


def test_blank_uuid_gets_generated(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({"connections": [{"uuid": "", "name": "a", "url": "u", "method": []}]}), encoding="utf-8")
    store = ConnectionStore(path)
    uuid = store.all()[0].uuid
    assert len(uuid) == 36
    assert read_json(path)["connections"][0]["uuid"] == uuid
