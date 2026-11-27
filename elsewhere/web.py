import os
from datetime import datetime
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from flask import Flask, Response, abort, g, redirect, render_template, request, url_for

from .db import MATCH_REPLY, connect, state

app = Flask(__name__)
SIZE = 12


@app.before_request
def choose_language():
    for candidate in (request.args.get("lang"), request.cookies.get("lang")):
        if candidate in ("en", "zh"):
            g.lang = candidate
            return
    g.lang = request.accept_languages.best_match(["en", "zh"], default="en")


@app.after_request
def remember_language(response):
    if request.endpoint != "static":
        response.headers["Content-Language"] = "zh-CN" if g.lang == "zh" else "en"
        response.vary.update(("Cookie", "Accept-Language"))
        if request.args.get("lang") == g.lang and request.cookies.get("lang") != g.lang:
            response.set_cookie("lang", g.lang, max_age=31536000, samesite="Lax",
                                httponly=True, secure=request.is_secure)
            response.cache_control.private = True
    return response


@app.template_global()
def t(english, chinese):
    return chinese if g.lang == "zh" else english


@app.template_global()
def compose_url(reply_to=None):
    tag = "#DearElsewhereDone" if reply_to else "#DearElsewhereQuest"
    params = {"text": f"{tag} @Dear_Elsewhere_"}
    if reply_to:
        params["in_reply_to"] = reply_to
    return "https://x.com/intent/tweet?" + urlencode(params)


@app.template_global()
def language_url(language):
    params = request.args.to_dict()
    params["lang"] = language
    return "?" + urlencode(params)


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
        from .demo import LETTERS, LETTERS_ZH
        letters = t(LETTERS, LETTERS_ZH)
    return dict(demo=demo, letters=letters, contact=os.getenv("DEAR_CONTACT_EMAIL"),
                analytics_token=os.getenv("CF_WEB_ANALYTICS_TOKEN", "").strip() if not demo else "")


@app.template_filter("date")
def format_date(value):
    day = datetime.fromisoformat(value)
    return t(day.strftime("%d %b %Y").lstrip("0"), f"{day.year}年{day.month}月{day.day}日")


def page(sql, params=()):
    number = request.args.get("page", 1, type=int)
    if not 1 <= number <= 1_000_000:
        abort(404)
    rows = db().execute(sql + " LIMIT ? OFFSET ?", (*params, SIZE + 1, (number - 1) * SIZE)).fetchall()
    if number > 1 and not rows:
        abort(404)
    return dict(rows=rows[:SIZE], number=number, more=len(rows) > SIZE)


@app.template_global()
def public_url(endpoint, **values):
    origin = os.environ.get("DEAR_PUBLIC_URL") or "https://dearelsewhere.anotherdayu.com"
    return origin.rstrip("/") + url_for(endpoint, **values)


@app.get("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\nSitemap: {public_url('sitemap')}\n",
                    mimetype="text/plain")


# Each invitation has two language URLs. Chunk well below the sitemap URL limit.
SITEMAP_BATCH = 10_000
PUBLIC_INVITATIONS = "FROM posts WHERE kind='invitation' AND hidden=0"


@app.get("/sitemap.xml", defaults={"part": None})
@app.get("/sitemap-<int:part>.xml")
def sitemap(part):
    demo = state(db(), "demo") == "1"
    count = 0 if demo else db().execute("SELECT count(*) " + PUBLIC_INVITATIONS).fetchone()[0]
    parts = max(1, (count + SITEMAP_BATCH - 1) // SITEMAP_BATCH)
    index = part is None and parts > 1
    if part is not None and not 1 <= part <= parts:
        abort(404)
    root = ET.Element("sitemapindex" if index else "urlset",
                      xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def add(url):
        ET.SubElement(ET.SubElement(root, "sitemap" if index else "url"), "loc").text = url

    if index:
        for n in range(1, parts + 1):
            add(public_url("sitemap", part=n))
    elif not demo:
        if part in (None, 1):
            for endpoint in ("home", "how_to_play", "about"):
                for lang in ("en", "zh"):
                    add(public_url(endpoint, lang=lang))
        invitations = db().execute("SELECT id " + PUBLIC_INVITATIONS +
                                   " ORDER BY created, id LIMIT ? OFFSET ?",
                                   (SITEMAP_BATCH, ((part or 1) - 1) * SITEMAP_BATCH))
        for row in invitations:
            for lang in ("en", "zh"):
                add(public_url("quest", ident=row["id"], lang=lang))
    return Response(ET.tostring(root, encoding="utf-8", xml_declaration=True),
                    mimetype="application/xml")


@app.get("/")
def home():
    visible = "kind='invitation' AND hidden=0"
    if "draw" in request.args:
        picks = db().execute(f"SELECT id FROM posts WHERE {visible} ORDER BY random() LIMIT 3")
        location = url_for("home", picks=",".join(row["id"] for row in picks), _anchor="draw")
        response = redirect(location, code=303)
        response.cache_control.no_store = True
        return response

    if "picks" in request.args:
        ids = list(dict.fromkeys(request.args["picks"].split(",")[:3]))
        rows = db().execute(f"SELECT * FROM posts WHERE {visible} AND id IN (?,?,?)",
                            (ids + [None] * 3)[:3])
        by_id = {row["id"]: row for row in rows}
        drawn = [by_id[ident] for ident in ids if ident in by_id]
        opened = set(request.args.get("open", "").split(",")[:3]) & set(by_id)
        return render_template("home.html", drawn=drawn, opened=opened)

    result = page(f"""SELECT q.*,
                      (SELECT count(*) FROM posts r WHERE {MATCH_REPLY}) AS replies,
                      preview.id AS reply_id, preview.created AS reply_created, preview.show_photos AS reply_photos,
                      preview.photo_ref AS reply_photo_ref
                      FROM posts q LEFT JOIN posts preview ON preview.id = (
                          SELECT r.id FROM posts r WHERE {MATCH_REPLY}
                          ORDER BY r.created DESC, length(r.id) DESC, r.id DESC LIMIT 1
                      )
                      WHERE q.kind='invitation' AND q.hidden=0
                      ORDER BY q.created DESC, length(q.id) DESC, q.id DESC""")
    return render_template("home.html", drawn=None, **result)


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


@app.get("/how-to-play")
def how_to_play():
    return render_template("how-to-play.html")


@app.get("/about")
def about():
    return render_template("about.html")


@app.errorhandler(404)
def missing(error):
    return render_template("missing.html", indexable=False), 404
