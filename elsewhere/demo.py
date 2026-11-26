"""Fiction written for the offline preview. Never populated from X."""
from .db import index_post, set_state, state

LETTERS = {
    "101": "Find a street sign that still carries an old name.",
    "102": "Listen to one minute of a place you usually hurry through.",
    "103": "Show someone the view from the last bench on your walk.",
    "201": "At the edge of the market, the enamel blue sign still says Orchard Lane.",
    "202": "A bicycle bell, a wooden shutter, and then a few seconds of rain.",
    "203": "I heard the clock across the square for the first time.",
}


def seed(conn):
    if state(conn, "demo") != "1":
        for table in ("posts", "removed", "state", "usage"):
            if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise ValueError("choose an empty DEAR_DB for the demo")
    set_state(conn, "demo", 1)
    for ident, day, parent in [
        ("201", 8, "101"), ("202", 10, "102"), ("203", 11, "102"),
        ("101", 7, None), ("102", 9, None), ("103", 12, None),
    ]:
        post = dict(id=ident, created_at=f"2026-06-{day:02d}T09:00:00Z",
                    conversation_id=parent or ident, entities={"hashtags": [
                        {"tag": "DearElsewhereDone" if parent else "DearElsewhereQuest"}]})
        if parent:
            post["referenced_tweets"] = [{"type": "replied_to", "id": parent}]
        index_post(conn, post)
