import tkinter as tk
from tkinter import ttk

from src.components.config_manager import ConfigManager
from src.sync.schema_sync_panel import SchemaSyncPanel
from src.export.export_schema_panel import ExportSchemaPanel


def run_app() -> None:
    root = tk.Tk()
    root.title("MySQL结构工具（同步/导出）")
    root.geometry("900x720")

    main_frame = ttk.Frame(root, padding="6")
    main_frame.pack(fill=tk.BOTH, expand=True)

    nb = ttk.Notebook(main_frame)
    nb.pack(fill=tk.BOTH, expand=True)

    config = ConfigManager()

    # Tab 1：结构同步（默认）
    tab_sync = SchemaSyncPanel(nb, config)
    nb.add(tab_sync, text="结构同步")

    # Tab 2：导出结构为Excel
    tab_export = ExportSchemaPanel(nb, config)
    nb.add(tab_export, text="导出为Excel")

    root.mainloop()


