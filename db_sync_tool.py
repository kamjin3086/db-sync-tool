import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pymysql
import sqlparse
import re
import threading
import json
import os

class SchemaSyncApp:
    # 定义配置文件的名称
    CONFIG_FILE = 'db_sync_config.json'

    def __init__(self, root):
        self.root = root
        self.root.title("MySQL增量结构同步工具")
        self.root.geometry("800x700")

        # --- Main Frame ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Source SQL File ---
        source_frame = ttk.LabelFrame(main_frame, text="1. 选择源结构SQL文件 (来自服务器A)")
        source_frame.pack(fill=tk.X, padx=5, pady=5)

        self.sql_file_path = tk.StringVar()
        ttk.Entry(source_frame, textvariable=self.sql_file_path, width=80).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(source_frame, text="浏览...", command=self.browse_file).pack(side=tk.LEFT, padx=5, pady=5)

        # --- Target DB Config ---
        target_frame = ttk.LabelFrame(main_frame, text="2. 配置目标数据库连接 (服务器B)")
        target_frame.pack(fill=tk.X, padx=5, pady=5)

        labels = ["主机 (Host):", "端口 (Port):", "用户名 (User):", "密码 (Password):", "数据库名 (DB):"]
        self.db_entries = {}

        for i, label_text in enumerate(labels):
            ttk.Label(target_frame, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky=tk.W)
            entry_var = tk.StringVar() # 使用StringVar来简化值的设置
            entry = ttk.Entry(target_frame, width=30, textvariable=entry_var)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky=tk.EW)
            if label_text == "密码 (Password):":
                entry.config(show="*")
            self.db_entries[label_text.split(' ')[0]] = entry_var # 存储StringVar而不是Entry
        target_frame.columnconfigure(1, weight=1)

        # --- Actions ---
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=10)

        self.compare_button = ttk.Button(action_frame, text="3. 对比并生成增量SQL", command=self.start_comparison)
        self.compare_button.pack(side=tk.LEFT, padx=5)
        
        self.execute_button = ttk.Button(action_frame, text="4. 在目标库执行SQL", state=tk.DISABLED, command=self.execute_sql)
        self.execute_button.pack(side=tk.LEFT, padx=5)
        
        self.copy_button = ttk.Button(action_frame, text="复制脚本", state=tk.DISABLED, command=self.copy_to_clipboard)
        self.copy_button.pack(side=tk.LEFT, padx=5)

        # --- Output ---
        output_frame = ttk.LabelFrame(main_frame, text="生成的增量SQL脚本 (请在执行前仔细检查！)")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.sql_output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=20, font=("Courier New", 10))
        self.sql_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var.set("准备就绪。")
        
        # --- NEW: Load config on startup ---
        self._load_config()

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")])
        if file_path:
            self.sql_file_path.set(file_path)

    # --- NEW: Function to save configuration ---
    def _save_config(self):
        config_data = {
            'sql_file_path': self.sql_file_path.get(),
            'host': self.db_entries["主机"].get(),
            'port': self.db_entries["端口"].get(),
            'user': self.db_entries["用户名"].get(),
            'password': self.db_entries["密码"].get(),
            'database': self.db_entries["数据库名"].get()
        }
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            self.set_status("配置已自动保存。")
        except IOError as e:
            print(f"警告：无法保存配置文件: {e}")

    # --- NEW: Function to load configuration ---
    def _load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.sql_file_path.set(config.get('sql_file_path', ''))
                self.db_entries["主机"].set(config.get('host', 'localhost'))
                self.db_entries["端口"].set(config.get('port', '3306'))
                self.db_entries["用户名"].set(config.get('user', 'root'))
                self.db_entries["密码"].set(config.get('password', ''))
                self.db_entries["数据库名"].set(config.get('database', ''))
                self.set_status("已加载上次的配置。")
            except (json.JSONDecodeError, IOError) as e:
                self.set_status(f"加载配置失败: {e}", "orange")
                # 加载失败时使用默认值
                self.db_entries["端口"].set('3306')
                self.db_entries["用户名"].set('root')
        else:
            # 如果配置文件不存在，设置默认值
            self.db_entries["端口"].set('3306')
            self.db_entries["用户名"].set('root')

    def set_status(self, message, color="black"):
        self.status_var.set(message)
        self.status_bar.config(foreground=color)
        self.root.update_idletasks()

    def show_error(self, title, message):
        messagebox.showerror(title, message)
        self.set_status(f"错误: {message}", "red")

    def start_comparison(self):
        self.compare_button.config(state=tk.DISABLED)
        self.execute_button.config(state=tk.DISABLED)
        self.copy_button.config(state=tk.DISABLED)
        self.sql_output.delete(1.0, tk.END)
        self.set_status("正在开始对比...")
        thread = threading.Thread(target=self.run_comparison_logic)
        thread.start()

    def run_comparison_logic(self):
        try:
            sql_file = self.sql_file_path.get()
            if not sql_file:
                raise ValueError("请先选择一个SQL文件！")
            
            db_config = {
                'host': self.db_entries["主机"].get(),
                'port': int(self.db_entries["端口"].get()),
                'user': self.db_entries["用户名"].get(),
                'password': self.db_entries["密码"].get(),
                'database': self.db_entries["数据库名"].get(),
                'charset': 'utf8mb4',
            }
            if not all([db_config['host'], db_config['user'], db_config['database']]):
                 raise ValueError("数据库连接信息不完整！")

            # --- NEW: Save config after successful validation ---
            self._save_config()

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
                self.set_status("对比完成！请仔细检查生成的SQL脚本。", "blue")
                self.execute_button.config(state=tk.NORMAL)
                self.copy_button.config(state=tk.NORMAL)
            else:
                self.set_status("完成。源和目标结构一致，无需变更。", "green")

        except Exception as e:
            self.show_error("操作失败", str(e))
        finally:
            self.compare_button.config(state=tk.NORMAL)

    def _parse_sql_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        statements = sqlparse.parse(content)
        schema = {}
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

    def _get_table_name_from_create(self, stmt):
        tokens = stmt.tokens
        table_keyword_found = False
        for token in tokens:
            if token.is_keyword and token.normalized == 'TABLE':
                table_keyword_found = True
                continue
            if table_keyword_found and isinstance(token, sqlparse.sql.Identifier):
                return token.get_name().strip('`')
        return None

    def _get_columns_from_create(self, stmt):
        columns = {}
        for token in stmt.tokens:
            if token.is_group and str(token).startswith('('):
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

    def _get_db_schema(self, db_config):
        schema = {}
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
        
    def _generate_diff_sql(self, source_schema, target_schema, db_config):
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
                        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{db_config['database']}' AND TABLE_NAME = '{table_name}' ORDER BY ORDINAL_POSITION")
                        ordered_columns = [row[0] for row in cursor.fetchall()]
                        if ordered_columns:
                            last_known_column = ordered_columns[-1]
                except Exception as e:
                    print(f"警告：无法获取表 {table_name} 的列顺序，新增字段将无序添加: {e}")
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
-- ==========================================================\n
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;\n
"""
        footer = "\nSET FOREIGN_KEY_CHECKS = 1;\n-- ======================= 脚本结束 ========================"
        
        return header + "\n".join(diffs) + footer

    def execute_sql(self):
        sql_script = self.sql_output.get(1.0, tk.END).strip()
        if not sql_script:
            self.show_error("执行错误", "脚本为空，无可执行内容。")
            return
        if not messagebox.askyesno("执行确认", "警告：即将对目标数据库执行以上脚本！\n\n您是否已经备份了目标数据库，并确认要继续？"):
            return
        self.execute_button.config(state=tk.DISABLED)
        self.set_status("正在执行SQL脚本...", "blue")
        try:
            db_config = {
                'host': self.db_entries["主机"].get(),
                'port': int(self.db_entries["端口"].get()),
                'user': self.db_entries["用户名"].get(),
                'password': self.db_entries["密码"].get(),
                'database': self.db_entries["数据库名"].get(),
                'charset': 'utf8mb4'
            }
            conn = pymysql.connect(**db_config, client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS)
            try:
                with conn.cursor() as cursor:
                    cursor.execute(sql_script)
                conn.commit()
                messagebox.showinfo("成功", "SQL脚本已成功执行！")
                self.set_status("脚本执行成功。", "green")
            finally:
                conn.close()
        except Exception as e:
            self.show_error("执行失败", f"执行SQL脚本时发生错误:\n\n{e}")
        finally:
            self.execute_button.config(state=tk.NORMAL)
    
    def copy_to_clipboard(self):
        sql_script = self.sql_output.get(1.0, tk.END).strip()
        if sql_script:
            self.root.clipboard_clear()
            self.root.clipboard_append(sql_script)
            self.set_status("脚本已复制到剪贴板。")

if __name__ == "__main__":
    root = tk.Tk()
    root.iconbitmap("app_icon.ico")
    app = SchemaSyncApp(root)
    root.mainloop()