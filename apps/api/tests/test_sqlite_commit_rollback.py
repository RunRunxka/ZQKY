"""A failed deferred COMMIT must roll back and leave the connection reusable."""
import sqlite3

import pytest

from app.core.sqlite import connect, transaction


def test_deferred_foreign_key_failure_rolls_back_and_connection_can_write(tmp_path):
    connection = connect(tmp_path / "deferred.sqlite3")
    try:
        connection.execute("CREATE TABLE parent(id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE child(id TEXT PRIMARY KEY,parent_id TEXT REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)")
        connection.execute("CREATE TABLE receipts(id TEXT PRIMARY KEY)")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with transaction(connection, immediate=True):
                connection.execute("INSERT INTO child VALUES('lost','missing')")
                connection.execute("INSERT INTO receipts VALUES('lost')")
        assert connection.in_transaction is False
        assert connection.execute("SELECT count(*) FROM child").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0
        with transaction(connection, immediate=True):
            connection.execute("INSERT INTO parent VALUES('present')")
            connection.execute("INSERT INTO child VALUES('kept','present')")
            connection.execute("INSERT INTO receipts VALUES('kept')")
        assert connection.execute("SELECT id FROM child").fetchone()[0] == "kept"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_body_failure_preserves_error_and_rolls_back(tmp_path):
    connection = connect(tmp_path / "body.sqlite3")
    try:
        connection.execute("CREATE TABLE values_table(value TEXT)")
        with pytest.raises(ValueError, match="original failure"):
            with transaction(connection, immediate=True):
                connection.execute("INSERT INTO values_table VALUES('uncommitted')")
                raise ValueError("original failure")
        assert connection.in_transaction is False
        assert connection.execute("SELECT count(*) FROM values_table").fetchone()[0] == 0
    finally:
        connection.close()
