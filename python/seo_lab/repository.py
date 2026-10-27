"""SQLite storage for drafts and review states."""
import json
import sqlite3
from datetime import datetime, timezone
from seo_lab.config import DB_PATH


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_url TEXT NOT NULL,
            slug TEXT NOT NULL,
            page_path TEXT NOT NULL,
            original_version INTEGER NOT NULL,
            original_json TEXT NOT NULL,
            proposed_json TEXT NOT NULL,
            rationale TEXT NOT NULL,
            target_query TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','published')),
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            published_at TEXT
        )""")


def create_proposal(site_url, page, proposed, rationale, target_query):
    original = {
        "title": page.get("title", ""),
        "metaDescription": page.get("metaDescription", ""),
        "h1": page.get("h1", ""),
        "paragraphs": page.get("paragraphs", []),
    }
    proposed_json = {
        "title": proposed["title"].strip(),
        "metaDescription": proposed["metaDescription"].strip(),
        "h1": proposed["h1"].strip(),
        "paragraphs": proposed["paragraphs"],
    }
    with connect() as db:
        cur = db.execute("""INSERT INTO proposals
            (site_url, slug, page_path, original_version, original_json,
             proposed_json, rationale, target_query, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (site_url, page["slug"], page["path"], int(page.get("version", 1)),
             json.dumps(original, ensure_ascii=False), json.dumps(proposed_json, ensure_ascii=False),
             rationale, target_query, now()))
        return cur.lastrowid


def list_proposals(status=None):
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM proposals WHERE status=? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM proposals ORDER BY id DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["original"] = json.loads(item.pop("original_json"))
        item["proposed"] = json.loads(item.pop("proposed_json"))
        result.append(item)
    return result


def get_proposal(proposal_id):
    result = [x for x in list_proposals() if x["id"] == int(proposal_id)]
    return result[0] if result else None


def update_proposed(proposal_id, proposed):
    with connect() as db:
        cur = db.execute("UPDATE proposals SET proposed_json=? WHERE id=? AND status='pending'",
                          (json.dumps(proposed, ensure_ascii=False), int(proposal_id)))
        return cur.rowcount == 1


def set_status(proposal_id, new_status, expected_status):
    stamp = now()
    review = stamp if new_status in {"approved", "rejected"} else None
    published = stamp if new_status == "published" else None
    with connect() as db:
        cur = db.execute("""UPDATE proposals
            SET status=?, reviewed_at=COALESCE(?, reviewed_at),
                published_at=COALESCE(?, published_at)
            WHERE id=? AND status=?""",
            (new_status, review, published, int(proposal_id), expected_status))
        return cur.rowcount == 1
