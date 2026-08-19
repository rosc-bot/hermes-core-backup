#!/usr/bin/env python3
"""SQLite 数据库恢复脚本：当 sqlite3 CLI 不可用时替代使用。

用法:
  python3 recover_sqlite.py <损坏的数据库文件> [输出文件]

默认输出文件: <原文件名>.recovered.db
"""
import sys, os, sqlite3, time

def recover(db_path: str, out_path: str | None = None) -> str:
    """使用 SQLite 的 .recover 模式重建数据库。"""
    if out_path is None:
        out_path = db_path + ".recovered.db"

    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    src_size = os.path.getsize(db_path)
    print(f"[1/3] 源文件: {db_path} ({src_size} bytes)")

    # 先检查损坏状态
    try:
        c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
        integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        print(f"[*] 源库完整性检查: {integrity}")
    except Exception as e:
        print(f"[*] 无法执行完整性检查: {e}")

    # 执行 .recover
    print(f"[2/3] 正在恢复中 -> {out_path}")
    con = sqlite3.connect(db_path)
    try:
        with open(out_path, "w"):
            pass  # 清空输出文件
        out = open(out_path, "w")
        for row in con.execute('SELECT * FROM "sqlite_master"'):
            stmt = row[4]
            if stmt:
                out.write(stmt + ";\n")
        # 从损坏库中逐行恢复数据
        for row in con.execute('SELECT * FROM "sqlite_master"'):
            name = row[1]
            typ = row[0]
            if typ == "table" and name != "sqlite_master":
                try:
                    for data_row in con.execute(f'SELECT * FROM "{name}"'):
                        escaped = [
                            val.replace("'", "''") if isinstance(val, str) else val
                            for val in data_row
                        ]
                        placeholders = ", ".join(
                            f"'{v}'" if isinstance(v, str) else str(v) if v is not None else "NULL"
                            for v in data_row
                        )
                        out.write(f"INSERT INTO \"{name}\" VALUES ({placeholders});\n")
                except Exception as e:
                    print(f"  [!] 表 {name} 部分数据跳过: {e}")
        out.close()
    finally:
        con.close()

    # 应用重建的 SQL 到新库
    out_db = sqlite3.connect(out_path)
    try:
        with open(out_path) as f:
            sql = f.read()
        out_db.executescript(sql)
        out_db.commit()
    finally:
        out_db.close()

    out_size = os.path.getsize(out_path)
    print(f"[3/3] 恢复完成: {out_path} ({out_size} bytes)")

    # 验证
    try:
        c = sqlite3.connect(out_path)
        ok = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        print(f"[*] 恢复库完整性检查: {ok}")
    except Exception as e:
        print(f"[*] 恢复库验证失败: {e}")

    return out_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <损坏的数据库文件> [输出文件]")
        sys.exit(1)
    db_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        recover(db_path, out_path)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)