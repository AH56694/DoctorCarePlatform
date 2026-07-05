from core.mysql_client import MySQLClient


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""

    def execute(self, sql):
        self.sql = sql

    def fetchall(self):
        return self.rows


def test_writable_columns_keep_default_generated_timestamps():
    client = MySQLClient()
    cursor = FakeCursor(
        [
            ("create_time", "datetime(6)", None, "NO", "", "CURRENT_TIMESTAMP(6)", "DEFAULT_GENERATED", "", ""),
            (
                "update_time",
                "datetime(6)",
                None,
                "NO",
                "",
                "CURRENT_TIMESTAMP(6)",
                "DEFAULT_GENERATED on update CURRENT_TIMESTAMP(6)",
                "",
                "",
            ),
            ("created_at", "datetime(6)", None, "YES", "", None, "VIRTUAL GENERATED", "", ""),
            ("legacy_created_at", "datetime(6)", None, "NO", "", "0000-00-00 00:00:00.000000", "", "", ""),
        ]
    )

    columns = client._get_writable_columns(cursor, "knowledge_chunk")

    assert "create_time" in columns
    assert "update_time" in columns
    assert "legacy_created_at" in columns
    assert "created_at" not in columns
