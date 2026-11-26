import os
from datetime import datetime

from flask import Flask, abort, g, redirect, render_template, request, url_for

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
    visible = "kind='invitation' AND hidden=0"
    if "draw" in request.args:
        picks = db().execute(f"SELECT id FROM posts WHERE {visible} ORDER BY random() LIMIT 3")
        location = url_for("home", picks=",".join(row["id"] for row in picks), _anchor="draw")
        response = redirect(location, code=303)
        response.cache_control.no_store = True
        return response

    drawn = None
    if "picks" in request.args:
        ids = list(dict.fromkeys(request.args["picks"].split(",")[:3]))
        rows = db().execute(f"SELECT * FROM posts WHERE {visible} AND id IN (?,?,?)",
                            (ids + [None] * 3)[:3])
        by_id = {row["id"]: row for row in rows}
        drawn = [by_id[ident] for ident in ids if ident in by_id]

    result = page(f"""SELECT q.*,
                      (SELECT count(*) FROM posts r WHERE {MATCH_REPLY}) AS replies,
                      preview.id AS reply_id, preview.created AS reply_created
                      FROM posts q LEFT JOIN posts preview ON preview.id = (
                          SELECT r.id FROM posts r WHERE {MATCH_REPLY}
                          ORDER BY r.created DESC, length(r.id) DESC, r.id DESC LIMIT 1
                      )
                      WHERE q.kind='invitation' AND q.hidden=0
                      ORDER BY q.created DESC, length(q.id) DESC, q.id DESC""")
    return render_template("home.html", drawn=drawn, **result)


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
