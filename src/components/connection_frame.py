import tkinter as tk
from tkinter import ttk
from .config_manager import ConfigManager
from typing import Dict


class DbConnectionFrame(ttk.LabelFrame):
    """
    可复用的数据库连接面板：主机/端口/用户名/密码/数据库名
    暴露 get_config()/save_to_config()/load_from_config()
    """

    def __init__(self, master, config_manager: ConfigManager, text: str = "配置数据库连接") -> None:
        super().__init__(master, text=text)
        self.config_manager = config_manager

        labels = ["主机 (Host):", "端口 (Port):", "用户名 (User):", "密码 (Password):", "数据库名 (DB):"]
        self.entry_vars: Dict[str, tk.StringVar] = {}

        for i, label_text in enumerate(labels):
            ttk.Label(self, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky=tk.W)
            var = tk.StringVar()
            ent = ttk.Entry(self, width=30, textvariable=var)
            if label_text.startswith("密码"):
                ent.config(show="*")
            ent.grid(row=i, column=1, padx=5, pady=2, sticky=tk.EW)
            # 中文短键：主机/端口/用户名/密码/数据库名
            self.entry_vars[label_text.split(' ')[0]] = var

        self.columnconfigure(1, weight=1)
        self.load_from_config()

    def get_config(self) -> Dict[str, object]:
        port_value = self.entry_vars["端口"].get().strip() or "3306"
        try:
            port_int = int(port_value)
        except ValueError:
            port_int = 3306
        return {
            "host": self.entry_vars["主机"].get().strip(),
            "port": port_int,
            "user": self.entry_vars["用户名"].get().strip(),
            "password": self.entry_vars["密码"].get(),
            "database": self.entry_vars["数据库名"].get().strip(),
            "charset": "utf8mb4",
        }

    def load_from_config(self) -> None:
        cfg = self.config_manager.get_connection_config()
        self.entry_vars["主机"].set(cfg.get("host", "localhost"))
        self.entry_vars["端口"].set(str(cfg.get("port", "3306")))
        self.entry_vars["用户名"].set(cfg.get("user", "root"))
        self.entry_vars["密码"].set(cfg.get("password", ""))
        self.entry_vars["数据库名"].set(cfg.get("database", ""))

    def save_to_config(self) -> None:
        self.config_manager.set_connection_config({
            "host": self.entry_vars["主机"].get().strip(),
            "port": self.entry_vars["端口"].get().strip(),
            "user": self.entry_vars["用户名"].get().strip(),
            "password": self.entry_vars["密码"].get(),
            "database": self.entry_vars["数据库名"].get().strip(),
        })


