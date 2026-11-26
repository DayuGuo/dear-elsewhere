import os
from datetime import datetime

from flask import Flask, abort, g, render_template, request

from .db import MATCH_REPLY, connect, state

app = Flask(__name__)
SIZE = 12


def db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(error):
    if "db" in g:
        g.db.close()


@app.context_processor
def settings():
    demo = state(db(), "demo") == "1"
    letters = {}
    if demo:
        from .demo import LETTERS
        letters = LETTERS
    return dict(demo=demo, letters=letters, contact=os.getenv("DEAR_CONTACT_EMAIL"))


@app.template_filter("date")
def format_date(value):
    return datetime.fromisoformat(value).strftime("%d %b %Y").lstrip("0")


def page(sql, params=()):
    number = request.args.get("page", 1, type=int)
    if not 1 <= number <= 1_000_000:
        abort(404)
    rows = db().execute(sql + " LIMIT ? OFFSET ?", (*params, SIZE + 1, (number - 1) * SIZE)).fetchall()
    if number > 1 and not rows:
        abort(404)
    return dict(rows=rows[:SIZE], number=number, more=len(rows) > SIZE)


@app.get("/")
def home():
    result = page(f"""SELECT q.*, (SELECT count(*) FROM posts r WHERE {MATCH_REPLY}) AS replies
                      FROM posts q WHERE q.kind='invitation' AND q.hidden=0
                      ORDER BY q.created DESC, length(q.id) DESC, q.id DESC""")
    return render_template("home.html", **result)


@app.get("/quest/<ident>")
def quest(ident):
    invitation = db().execute(
        "SELECT * FROM posts WHERE id=? AND kind='invitation' AND hidden=0", (ident,)
    ).fetchone()
    if invitation is None:
        abort(404)
    result = page(f"""SELECT r.* FROM posts q JOIN posts r ON {MATCH_REPLY}
                      WHERE q.id=? ORDER BY r.created, length(r.id), r.id""", (ident,))
    return render_template("quest.html", invitation=invitation, **result)


@app.get("/about")
def about():
    return render_template("about.html")


@app.errorhandler(404)
def missing(error):
    return render_template("missing.html"), 404
