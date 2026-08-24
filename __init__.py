import os
import sqlite3
from pathlib import Path
from flask import Flask

DB_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "promoradar.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY AUTOINCREMENT, term TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1)')
        db.execute('''CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, external_id TEXT,
            title TEXT NOT NULL, url TEXT NOT NULL, image_url TEXT, price REAL,
            old_price REAL, discount REAL, score TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, external_id))''')
        db.commit()

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only")
    init_db()
    from .routes import bp
    app.register_blueprint(bp)
    return app
