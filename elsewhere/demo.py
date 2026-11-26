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


LETTERS_ZH = {
    "101": "找一块还留着旧地名的路牌。",
    "102": "在一个平日总是匆匆经过的地方，停下来听一分钟。",
    "103": "走到散步路上的最后一张长椅，把眼前的风景寄给别人。",
    "104": "找一株没有人栽种、却自己长出来的植物。",
    "105": "循着面包的香气走，看看它会把你带到哪里。",
    "106": "走到一片阳光里。看看都有谁在这里停留。",
    "201": "集市边缘那块蓝色搪瓷路牌上，还写着「果园巷」。",
    "202": "一声车铃，木百叶窗轻轻一响，接着是几秒钟的雨声。",
    "203": "我第一次听见了广场另一头的钟声。",
    "204": "车站的两块砖之间，住进了一株蕨。",
    "205": "一只猫，两把空椅子，还有一道晾衣绳的影子。",
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
