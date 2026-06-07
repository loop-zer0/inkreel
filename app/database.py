"""SQLite 数据库连接与表初始化"""

import sqlite3
import os

from app.config import DATABASE_PATH


def get_db() -> sqlite3.Connection:
    """获取数据库连接，自动创建目录和表"""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    """创建所有表（幂等）"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS novels (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL DEFAULT '（未命名）',
            author          TEXT    NOT NULL DEFAULT '（未知）',
            genre           TEXT    NOT NULL DEFAULT '通用',
            filename        TEXT    NOT NULL,
            file_format     TEXT    NOT NULL DEFAULT 'txt',
            total_chars     INTEGER NOT NULL DEFAULT 0,
            chapter_count   INTEGER NOT NULL DEFAULT 0,
            original_text   TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS novel_chapters (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id        INTEGER NOT NULL,
            chapter_number  REAL    NOT NULL,
            sort_order      INTEGER NOT NULL DEFAULT 0,
            title           TEXT    NOT NULL DEFAULT '',
            content         TEXT    NOT NULL DEFAULT '',
            char_count      INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_nc_novel ON novel_chapters(novel_id);

        CREATE TABLE IF NOT EXISTS scripts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id        INTEGER NOT NULL,
            title           TEXT    NOT NULL DEFAULT '（未命名）',
            status          TEXT    NOT NULL DEFAULT 'draft',
            yaml_content    TEXT    NOT NULL DEFAULT '',
            character_count INTEGER NOT NULL DEFAULT 0,
            scene_count     INTEGER NOT NULL DEFAULT 0,
            manually_edited INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_scripts_novel ON scripts(novel_id);

        CREATE TABLE IF NOT EXISTS script_chapters (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id       INTEGER NOT NULL,
            novel_id        INTEGER NOT NULL,
            chapter_number  REAL    NOT NULL,
            yaml_content    TEXT    NOT NULL DEFAULT '',
            scene_count     INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (script_id)  REFERENCES scripts(id) ON DELETE CASCADE,
            FOREIGN KEY (novel_id)   REFERENCES novels(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sch_script ON script_chapters(script_id);
        CREATE INDEX IF NOT EXISTS idx_sch_novel_ch ON script_chapters(novel_id, chapter_number);

        CREATE TABLE IF NOT EXISTS context_cache (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id        INTEGER NOT NULL,
            chapter_number  REAL    NOT NULL,
            summary         TEXT    NOT NULL DEFAULT '',
            key_events      TEXT    NOT NULL DEFAULT '',
            characters_intro TEXT   NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_novel_ch ON context_cache(novel_id, chapter_number);

        -- 迁移：为已有数据库补齐 manually_edited 列
        PRAGMA table_info('scripts');
    """)
    # 检查 scripts 表是否有 manually_edited 列，没有则添加
    cols = {r[1] for r in conn.execute("PRAGMA table_info('scripts')").fetchall()}
    if 'manually_edited' not in cols:
        conn.execute("ALTER TABLE scripts ADD COLUMN manually_edited INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    conn.executescript("""

        CREATE TABLE IF NOT EXISTS merged_scripts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id       INTEGER NOT NULL,
            novel_id        INTEGER NOT NULL,
            title           TEXT    NOT NULL DEFAULT '（未命名）',
            note            TEXT    NOT NULL DEFAULT '',
            yaml_content    TEXT    NOT NULL DEFAULT '',
            character_count INTEGER NOT NULL DEFAULT 0,
            scene_count     INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
            FOREIGN KEY (novel_id)  REFERENCES novels(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_ms_script ON merged_scripts(script_id);

        CREATE TABLE IF NOT EXISTS merged_script_items (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            merged_script_id  INTEGER NOT NULL,
            script_chapter_id INTEGER NOT NULL,
            chapter_number    REAL    NOT NULL,
            sort_order        INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (merged_script_id)  REFERENCES merged_scripts(id) ON DELETE CASCADE,
            FOREIGN KEY (script_chapter_id) REFERENCES script_chapters(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_msi_merge ON merged_script_items(merged_script_id);

        CREATE TABLE IF NOT EXISTS translations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type     TEXT    NOT NULL,
            target_id       INTEGER NOT NULL,
            language        TEXT    NOT NULL DEFAULT 'en',
            language_label  TEXT    NOT NULL DEFAULT 'English',
            translated_yaml TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_tr_target ON translations(target_type, target_id);

        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    NOT NULL DEFAULT '',
            phone           TEXT    NOT NULL DEFAULT '',
            password_hash   TEXT    NOT NULL,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email != '';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone) WHERE phone != '';
    """)
