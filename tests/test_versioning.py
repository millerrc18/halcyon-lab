"""Tests for model versioning."""

import os
import sqlite3
import tempfile

from src.training.versioning import (
    get_active_model_name,
    get_active_model_version,
    get_model_history,
    init_training_tables,
    register_model_version,
    rollback_model,
)


def _tmp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    return path


def test_get_active_model_name_returns_base_when_empty():
    db = _tmp_db()
    init_training_tables(db)
    assert get_active_model_name(db) == "base"


def test_register_model_version_creates_active():
    db = _tmp_db()
    init_training_tables(db)
    vid = register_model_version("halcyon-v1", 100, 80, 20, "/path/model.gguf", db)
    assert vid is not None
    active = get_active_model_version(db)
    assert active is not None
    assert active["version_name"] == "halcyon-v1"
    assert active["status"] == "active"
    assert active["training_examples_count"] == 100


def test_register_retires_previous():
    db = _tmp_db()
    init_training_tables(db)
    register_model_version("halcyon-v1", 100, 80, 20, "/path/v1.gguf", db)
    register_model_version("halcyon-v2", 200, 150, 50, "/path/v2.gguf", db)

    active = get_active_model_version(db)
    assert active["version_name"] == "halcyon-v2"

    history = get_model_history(db)
    statuses = {h["version_name"]: h["status"] for h in history}
    assert statuses["halcyon-v1"] == "retired"
    assert statuses["halcyon-v2"] == "active"


def test_rollback_restores_previous():
    db = _tmp_db()
    init_training_tables(db)
    register_model_version("halcyon-v1", 100, 80, 20, "/path/v1.gguf", db)
    register_model_version("halcyon-v2", 200, 150, 50, "/path/v2.gguf", db)

    restored = rollback_model(db)
    assert restored is not None
    assert restored["version_name"] == "halcyon-v1"

    active = get_active_model_version(db)
    assert active["version_name"] == "halcyon-v1"


def test_rollback_returns_none_when_no_previous():
    db = _tmp_db()
    init_training_tables(db)
    register_model_version("halcyon-v1", 100, 80, 20, "/path/v1.gguf", db)
    restored = rollback_model(db)
    assert restored is None


def test_get_model_history_order():
    db = _tmp_db()
    init_training_tables(db)
    register_model_version("halcyon-v1", 100, 80, 20, "/path/v1.gguf", db)
    register_model_version("halcyon-v2", 200, 150, 50, "/path/v2.gguf", db)
    register_model_version("halcyon-v3", 300, 200, 100, "/path/v3.gguf", db)

    history = get_model_history(db)
    names = [h["version_name"] for h in history]
    assert names == ["halcyon-v3", "halcyon-v2", "halcyon-v1"]
