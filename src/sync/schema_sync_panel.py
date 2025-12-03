import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pymysql
import sqlparse
import re
import threading
from typing import Dict

from src.components.connection_frame import DbConnectionFrame
from src.components.config_manager import ConfigManager


class SchemaSyncPanel(ttk.Frame):
    """
    “结构同步”面板（将原单窗口工具改造成可插拔面板，便于与其他功能并存）
    """

    def __init__(self, master, config_manager: ConfigManager) -> None:
        super().__init__(master, padding="10")
        self.config_manager = config_manager

        # --- 源SQL文件 ---
        source_frame = ttk.LabelFrame(self, text="1. 选择源结构SQL文件 (来自服务器A)")
        source_frame.pack(fill=tk.X, padx=5, pady=5)

        self.sql_file_path = tk.StringVar(value=self.config_manager.get_sync_sql_file_path())
        ttk.Entry(source_frame, textvariable=self.sql_file_path, width=80).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(source_frame, text="浏览...", command=self.browse_file).pack(side=tk.LEFT, padx=5, pady=5)

        # --- 目标连接 ---
        self.conn_frame = DbConnectionFrame(self, self.config_manager, text="2. 配置目标数据库连接 (服务器B)")
        self.conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # --- 操作按钮 ---
        action_frame = ttk.Frame(self)
        action_frame.pack(fill=tk.X, padx=5, pady=10)

        self.compare_button = ttk.Button(action_frame, text="3. 对比并生成增量SQL", command=self.start_comparison)
        self.compare_button.pack(side=tk.LEFT, padx=5)

        self.execute_button = ttk.Button(action_frame, text="4. 在目标库执行SQL", state=tk.DISABLED, command=self.execute_sql)
        self.execute_button.pack(side=tk.LEFT, padx=5)

        self.copy_button = ttk.Button(action_frame, text="复制脚本", state=tk.DISABLED, command=self.copy_to_clipboard)
        self.copy_button.pack(side=tk.LEFT, padx=5)

        # --- 输出 ---
        output_frame = ttk.LabelFrame(self, text="生成的增量SQL脚本 (请在执行前仔细检查！)")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.sql_output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=20, font=("Courier New", 10))
        self.sql_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- 状态 ---
        self.status_var = tk.StringVar(value="准备就绪。")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # -------------------- UI 事件 --------------------
    def set_status(self, message: str, color: str = "black") -> None:
        # Note: ttk.Label 不支持 foreground 配置在主题下统一，这里仅设置变量文本
        self.status_var.set(message)
        self.update_idletasks()

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)
        self.set_status(f"错误: {message}")

    def browse_file(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")])
        if file_path:
            self.sql_file_path.set(file_path)

    # -------------------- 同步主流程 --------------------
    def start_comparison(self) -> None:
        self.compare_button.config(state=tk.DISABLED)
        self.execute_button.config(state=tk.DISABLED)
        self.copy_button.config(state=tk.DISABLED)
        self.sql_output.delete(1.0, tk.END)
        self.set_status("正在开始对比...")
        threading.Thread(target=self.run_comparison_logic, daemon=True).start()

    def run_comparison_logic(self) -> None:
        try:
            sql_file = self.sql_file_path.get().strip()
            if not sql_file:
                raise ValueError("请先选择一个SQL文件！")

            db_config = self.conn_frame.get_config()
            if not all([db_config["host"], db_config["user"], db_config["database"]]):
                raise ValueError("数据库连接信息不完整！")

            # 保存配置
            self.conn_frame.save_to_config()
            self.config_manager.set_sync_sql_file_path(sql_file)

            self.set_status("正在解析源SQL文件...")
            source_schema = self._parse_sql_file(sql_file)
            if not source_schema:
                raise ValueError("未能从SQL文件中解析出任何CREATE TABLE语句。")

            self.set_status(f"正在连接并读取目标数据库 '{db_config['database']}' 的结构...")
            target_schema = self._get_db_schema(db_config)

            self.set_status("正在比对结构差异...")
            diff_sql = self._generate_diff_sql(source_schema, target_schema, db_config)

            if diff_sql:
                self.sql_output.insert(tk.END, diff_sql)
                self.set_status("对比完成！请仔细检查生成的SQL脚本。")
                self.execute_button.config(state=tk.NORMAL)
                self.copy_button.config(state=tk.NORMAL)
            else:
                self.set_status("完成。源和目标结构一致，无需变更。")

        except Exception as e:
            self.show_error("操作失败", str(e))
        finally:
            self.compare_button.config(state=tk.NORMAL)

    # -------------------- 解析/读取结构 --------------------
    def _parse_sql_file(self, file_path: str) -> Dict[str, Dict[str, object]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        statements = sqlparse.parse(content)
        schema: Dict[str, Dict[str, object]] = {}
        for stmt in statements:
            if stmt.get_type() == 'CREATE' and 'TABLE' in str(stmt).upper():
                table_name = self._get_table_name_from_create(stmt)
                if table_name:
                    columns = self._get_columns_from_create(stmt)
                    schema[table_name] = {
                        'create_sql': str(stmt).strip(),
                        'columns': columns
                    }
        return schema

    def _get_table_name_from_create(self, stmt) -> str:
        tokens = stmt.tokens
        table_keyword_found = False
        for token in tokens:
            if getattr(token, "is_keyword", False) and token.normalized == 'TABLE':
                table_keyword_found = True
                continue
            if table_keyword_found and getattr(token, "__class__", None).__name__ == "Identifier":
                return token.get_name().strip('`')
        return ""

    def _get_columns_from_create(self, stmt) -> Dict[str, str]:
        columns: Dict[str, str] = {}
        for token in stmt.tokens:
            if getattr(token, "is_group", False) and str(token).startswith('('):
                content = str(token).strip()[1:-1]
                column_lines = content.split('\n')
                for line in column_lines:
                    line = line.strip()
                    if not line or line.lower().startswith(('primary key', 'unique key', 'key', 'index', ')', 'constraint')):
                        continue
                    match = re.match(r'`(.+?)`', line)
                    if match:
                        col_name = match.group(1)
                        columns[col_name] = line.rstrip(',')
        return columns

    def _get_db_schema(self, db_config) -> Dict[str, set]:
        schema: Dict[str, set] = {}
        conn = pymysql.connect(**db_config)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
                for table in tables:
                    schema[table] = set()
                    cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                    for col_row in cursor.fetchall():
                        schema[table].add(col_row[0])
        finally:
            conn.close()
        return schema

    # -------------------- 生成增量脚本 --------------------
    def _generate_diff_sql(self, source_schema, target_schema, db_config) -> str:
        diffs = []
        for table_name, source_table_info in source_schema.items():
            if table_name not in target_schema:
                diffs.append(f"-- >>> [新增表] 表 '{table_name}' 在目标数据库中不存在，创建它。 <<<")
                diffs.append(source_table_info['create_sql'] + ";\n")
            else:
                new_columns_scripts = []
                target_columns = target_schema[table_name]
                source_columns = source_table_info['columns']

                conn = None
                last_known_column = None
                try:
                    conn = pymysql.connect(**db_config)
                    with conn.cursor() as cursor:
                        cursor.execute(
                            f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{db_config['database']}' AND TABLE_NAME = '{table_name}' ORDER BY ORDINAL_POSITION"
                        )
                        ordered_columns = [row[0] for row in cursor.fetchall()]
                        if ordered_columns:
                            last_known_column = ordered_columns[-1]
                except Exception:
                    if target_columns:
                        last_known_column = list(target_columns)[-1]
                finally:
                    if conn:
                        conn.close()

                for col_name, col_def in source_columns.items():
                    if col_name not in target_columns:
                        add_sql = f"ALTER TABLE `{table_name}` ADD COLUMN {col_def}"
                        if last_known_column:
                            add_sql += f" AFTER `{last_known_column}`"
                        add_sql += ";"
                        new_columns_scripts.append(add_sql)
                        last_known_column = col_name

                if new_columns_scripts:
                    diffs.append(f"-- >>> [新增字段] 为表 '{table_name}' 添加缺失的字段。 <<<")
                    diffs.extend(new_columns_scripts)
                    diffs.append("")

        if not diffs:
            return ""

        header = """-- ==========================================================
--  MySQL 增量结构同步脚本
--  自动生成
--  请在执行前仔细检查每一行，确保它符合您的预期！
-- ==========================================================\\n
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;\\n
"""
        footer = "\nSET FOREIGN_KEY_CHECKS = 1;\n-- ======================= 脚本结束 ========================"
        return header + "\n".join(diffs) + footer

    # -------------------- 执行与复制 --------------------
    def execute_sql(self) -> None:
        sql_script = self.sql_output.get(1.0, tk.END).strip()
        if not sql_script:
            self.show_error("执行错误", "脚本为空，无可执行内容。")
            return
        if not messagebox.askyesno("执行确认", "警告：即将对目标数据库执行以上脚本！\n\n您是否已经备份了目标数据库，并确认要继续？"):
            return
        self.execute_button.config(state=tk.DISABLED)
        self.set_status("正在执行SQL脚本...")
        try:
            db_config = self.conn_frame.get_config()
            conn = pymysql.connect(**db_config, client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS)
            try:
                with conn.cursor() as cursor:
                    cursor.execute(sql_script)
                conn.commit()
                messagebox.showinfo("成功", "SQL脚本已成功执行！")
                self.set_status("脚本执行成功。")
            finally:
                conn.close()
        except Exception as e:
            self.show_error("执行失败", f"执行SQL脚本时发生错误:\n\n{e}")
        finally:
            self.execute_button.config(state=tk.NORMAL)

    def copy_to_clipboard(self) -> None:
        sql_script = self.sql_output.get(1.0, tk.END).strip()
        if sql_script:
            top = self.winfo_toplevel()
            top.clipboard_clear()
            top.clipboard_append(sql_script)
            self.set_status("脚本已复制到剪贴板。")


