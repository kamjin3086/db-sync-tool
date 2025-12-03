import os
import json
from typing import Dict, Any


class ConfigManager:
    """
    负责读取/写入配置，保持与历史单文件键兼容：
    - 旧版：顶层包含 host/port/user/password/database/sql_file_path
    - 新版：分区存储：connection、sync、export
    """

    def __init__(self, config_filename: str = "db_sync_config.json") -> None:
        self.config_path = os.path.join(self._get_project_root(), config_filename)

    def _get_project_root(self) -> str:
        # src/components/ -> 项目根目录
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # --------------------- 基础读写 ---------------------
    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except IOError:
            # 安静失败：界面上会用状态条提示
            pass

    # --------------------- 连接配置 ---------------------
    def get_connection_config(self) -> Dict[str, str]:
        data = self.load()

        # 新版结构优先
        conn = data.get("connection", {})

        # 兼容旧版顶层键
        conn = {
            "host": conn.get("host", data.get("host", "localhost")),
            "port": str(conn.get("port", data.get("port", "3306"))),
            "user": conn.get("user", data.get("user", "root")),
            "password": conn.get("password", data.get("password", "")),
            "database": conn.get("database", data.get("database", "")),
        }
        return conn

    def set_connection_config(self, connection: Dict[str, str]) -> None:
        data = self.load()
        data["connection"] = {
            "host": connection.get("host", ""),
            "port": str(connection.get("port", "")),
            "user": connection.get("user", ""),
            "password": connection.get("password", ""),
            "database": connection.get("database", ""),
        }

        # 兼容旧版顶层键
        data["host"] = data["connection"]["host"]
        data["port"] = data["connection"]["port"]
        data["user"] = data["connection"]["user"]
        data["password"] = data["connection"]["password"]
        data["database"] = data["connection"]["database"]
        self.save(data)

    # --------------------- 同步面板配置 ---------------------
    def get_sync_sql_file_path(self) -> str:
        data = self.load()
        if isinstance(data.get("sync"), dict):
            v = data["sync"].get("sql_file_path", "")
            if v:
                return v
        # 兼容旧版
        return data.get("sql_file_path", "")

    def set_sync_sql_file_path(self, path: str) -> None:
        data = self.load()
        data.setdefault("sync", {})
        data["sync"]["sql_file_path"] = path
        # 兼容旧版
        data["sql_file_path"] = path
        self.save(data)


