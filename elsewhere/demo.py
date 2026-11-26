"""Fiction written for the offline preview. Never populated from X."""
from .db import index_post, set_state, state

LETTERS = {
    "101": "Find a street sign that still carries an old name.",
    "102": "Listen to one minute of a place you usually hurry through.",
    "103": "Show someone the view from the last bench on your walk.",
    "104": "Find something growing where nobody planted it.",
    "105": "Follow the smell of bread and see where it takes you.",
    "106": "Walk until you find a patch of sunlight. What has gathered there?",
    "204": "A fern has found a home between two bricks at the station.",
    "205": "One cat, two empty chairs, and the shadow of a washing line.",
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
        ("104", 14, None), ("105", 16, None), ("106", 18, None),
        ("204", 15, "104"), ("205", 19, "106"),
    ]:
        post = dict(id=ident, created_at=f"2026-06-{day:02d}T09:00:00Z",
                    conversation_id=parent or ident, entities={"hashtags": [
                        {"tag": "DearElsewhereDone" if parent else "DearElsewhereQuest"}]})
        if parent:
            post["referenced_tweets"] = [{"type": "replied_to", "id": parent}]
        index_post(conn, post)
