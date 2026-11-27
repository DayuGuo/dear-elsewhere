import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

DEFAULT_DB = Path("instance/index.sqlite3")
SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('invitation','reply')),
    created TEXT NOT NULL,
    parent TEXT,
    conversation TEXT,
    hidden INTEGER NOT NULL DEFAULT 0,
    show_photos INTEGER NOT NULL DEFAULT 0,
    photo_ref TEXT
);
CREATE INDEX IF NOT EXISTS invitations ON posts(kind, hidden, created DESC, id DESC);
CREATE INDEX IF NOT EXISTS replies ON posts(parent, hidden, created, id);
CREATE TABLE IF NOT EXISTS removed (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage (month TEXT PRIMARY KEY, reads INTEGER NOT NULL);
"""
# Requiring the direct parent prevents a reply to a reply from appearing on a card.
MATCH_REPLY = """r.kind='reply' AND r.hidden=0 AND r.parent=q.id
                 AND (r.conversation IS NULL OR r.conversation=q.id)"""


def connect():
    path = Path(os.environ.get("DEAR_DB", DEFAULT_DB))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init(conn):
    conn.executescript(SCHEMA)
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(posts)")}
        if "show_photos" not in columns:
            conn.execute("ALTER TABLE posts ADD COLUMN show_photos INTEGER NOT NULL DEFAULT 0")
        if "photo_ref" not in columns:
            conn.execute("ALTER TABLE posts ADD COLUMN photo_ref TEXT")


def state(conn, key):
    row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_state(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, str(value)))


def post_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        raise ValueError("invalid post ID")
    return value


def photo_metadata(post, media):
    keys = post.get("attachments", {}).get("media_keys", [])
    if not keys or any(ref["type"] == "quoted" for ref in post.get("referenced_tweets", [])):
        return False, None
    photos = [media[key] for key in keys if media.get(key, {}).get("type") == "photo"]
    # Retain only the first usable X image filename; never use video poster frames.
    for photo in photos:
        path, _, query = (photo.get("url") or "").partition("?")
        match = re.fullmatch(r"https://pbs\.twimg\.com/media/([A-Za-z0-9_-]+)(?:\.([a-z]+))?", path)
        if match:
            ext = match[2] or parse_qs(query).get("format", [""])[0]
            if ext in ("jpg", "jpeg", "png", "webp"):
                return len(photos) == len(keys), f"{match[1]}.{ext}"
    return len(photos) == len(keys), None


def index_post(conn, post, media=None):
    ident = post_id(post["id"])
    conversation = post_id(post["conversation_id"]) if post.get("conversation_id") else None
    refs = post.get("referenced_tweets", [])
    if post.get("withheld"):
        conn.execute("UPDATE posts SET hidden=1 WHERE id=?", (ident,))
        return
    if any(r["type"] == "retweeted" for r in refs):
        return
    tags = {
        item["tag"].casefold()
        for content in (post, post.get("note_tweet", {}))
        for item in content.get("entities", {}).get("hashtags", [])
    }
    parent = next((post_id(r["id"]) for r in refs if r["type"] == "replied_to"), None)
    if parent and "dearelsewheredone" in tags:
        kind = "reply"
    elif not refs and "dearelsewherequest" in tags and conversation in (None, ident):
        kind = "invitation"
    else:
        return
    created = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
    if created.utcoffset() is None:
        raise ValueError("missing timezone")
    conn.execute("""
        INSERT INTO posts(id,kind,created,parent,conversation,show_photos,photo_ref)
        SELECT ?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM removed WHERE id=?)
        ON CONFLICT(id) DO UPDATE SET show_photos=excluded.show_photos, photo_ref=excluded.photo_ref
    """, (ident, kind, created.astimezone(timezone.utc).isoformat(), parent, conversation,
          *photo_metadata(post, media or {}), ident))
