import io
import json
import os
import tempfile
import time
import unittest
from xml.etree import ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from elsewhere import db
from elsewhere.demo import seed
from elsewhere.sync import SyncError, api, check_links, exclusive, sync
from elsewhere.web import app


def fixture(ident, parent=None, conversation=None):
    return {"id": str(ident), "conversation_id": str(conversation or parent or ident),
            "created_at": "2026-06-01T12:00:00Z", "text": "never persist this text",
            "referenced_tweets": [{"type": "replied_to", "id": str(parent)}] if parent else [],
            "entities": {"hashtags": [{"tag": "DearElsewhereDone" if parent else "DearElsewhereQuest"}]}}


def page(*posts, token=None):
    meta = {"result_count": len(posts)}
    if token:
        meta["next_token"] = token
    return {"data": list(posts), "meta": meta}


class IndexTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, DEAR_DB=str(Path(tmp.name) / "db"), X_BEARER_TOKEN="test",
                         X_MAX_PAGES="12", X_MONTHLY_READ_LIMIT="1500")
        env.start()
        self.addCleanup(env.stop)
        self.conn = db.connect()
        self.addCleanup(self.conn.close)
        db.init(self.conn)
        self.web = app.test_client()

    def test_demo_and_public_pages(self):
        with self.conn:
            seed(self.conn)
            seed(self.conn)
        home = self.web.get("/").data
        self.assertLess(home.index(b"last bench"), home.index(b"street sign"))
        self.assertIn(b"2 replies", home)
        self.assertNotIn(b"widgets.js", home)
        self.assertIn(b"wooden shutter", self.web.get("/quest/102").data)
        self.assertEqual(self.web.get("/about").status_code, 200)
        self.assertEqual(self.web.get("/quest/202").status_code, 404)

    def test_public_metadata_and_sitemap(self):
        with self.conn:
            for post in (fixture(1), fixture(2), fixture(3), fixture(4, parent=1)):
                db.index_post(self.conn, post)
            self.conn.execute("UPDATE posts SET hidden=1 WHERE id='3'")
        origin = "https://letters.example"
        with patch.dict(os.environ, DEAR_PUBLIC_URL=origin), patch("elsewhere.web.SITEMAP_BATCH", 1):
            self.assertIn(origin + "/sitemap.xml", self.web.get("/robots.txt").text)
            def locations(path):
                root = ET.fromstring(self.web.get(path).data)
                return [loc.text for loc in root.findall(".//{*}loc")]
            self.assertEqual(locations("/sitemap.xml"), [origin + "/sitemap-1.xml", origin + "/sitemap-2.xml"])
            urls = locations("/sitemap-1.xml") + locations("/sitemap-2.xml")
            self.assertEqual(len(set(urls)), 10)
            for url in urls:
                path = url.removeprefix(origin)
                html = self.web.get(path + "&utm_source=x").text
                self.assertIn(f'<link rel="canonical" href="{url}">', html)
                self.assertIn('hreflang="zh-Hans"', html)
                self.assertIn('property="og:image"', html)
            for path in ("/quest/3", "/quest/4", "/?picks=1", "/quest/1?page=2"):
                self.assertIn('content="noindex,follow"', self.web.get(path).text)
                self.assertFalse(any(path + "?" in url for url in urls))

    def test_draw_is_distinct_stable_and_uses_visible_invitations_only(self):
        with self.conn:
            seed(self.conn)
            self.conn.execute("UPDATE posts SET hidden=1 WHERE id='105'")
        response = self.web.get("/?draw=1")
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.cache_control.no_store)
        location = urlsplit(response.location)
        ids = parse_qs(location.query)["picks"][0].split(",")
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3)
        self.assertTrue(set(ids) <= {"101", "102", "103", "104", "106"})
        self.assertEqual(location.fragment, "draw")
        choice = self.web.get(response.location).data
        self.assertEqual(choice, self.web.get(response.location).data)
        self.assertEqual(choice.count(b"Choose this invitation"), 3)
        with self.conn:
            self.conn.execute("UPDATE posts SET hidden=1 WHERE id=?", (ids[0],))
        self.assertEqual(self.web.get(response.location).data.count(b"Choose this invitation"), 2)

    def test_language_choice_keeps_draw_and_translates_following_pages(self):
        with self.conn:
            seed(self.conn)
        response = self.web.get("/?picks=101,102,103", headers={"Accept-Language": "zh-CN"})
        self.assertEqual(response.headers["Content-Language"], "zh-CN")
        self.assertIn("选择这封邀请", response.get_data(as_text=True))
        self.assertIn("picks=101%2C102%2C103&amp;lang=en", response.get_data(as_text=True))
        self.web.get("/?picks=101,102,103&lang=zh")
        detail = self.web.get("/quest/102").get_data(as_text=True)
        self.assertIn("木百叶窗", detail)
        self.assertIn("2026年6月9日", detail)
        self.assertIn("关于致别处", self.web.get("/about").get_data(as_text=True))
        self.web.get("/about?lang=en")
        self.assertIn(b"wooden shutter", self.web.get("/quest/102").data)

    def test_open_letters_survive_a_shared_or_translated_draw(self):
        with self.conn:
            seed(self.conn)
        response = self.web.get("/?picks=101,106,104&open=106,999&lang=zh")
        html = response.get_data(as_text=True)
        self.assertIn('data-letter-id="106" open', html)
        self.assertNotIn('data-letter-id="101" open', html)
        self.assertNotIn('data-letter-id="999"', html)

    def test_empty_and_small_draws(self):
        empty = self.web.get("/?draw=1", follow_redirects=True)
        self.assertIn(b"no invitations available", empty.data)
        with self.conn:
            db.index_post(self.conn, fixture(1))
        single = self.web.get("/?draw=1", follow_redirects=True)
        self.assertEqual(single.data.count(b"Choose this invitation"), 1)
        self.assertIn(b"/status/1", single.data)

    def test_branch_preview_uses_latest_visible_direct_reply(self):
        with self.conn:
            for post in (fixture(1), fixture(2, 1), fixture(3, 1), fixture(4, 1), fixture(5, 2, 1)):
                db.index_post(self.conn, post)
            self.conn.execute("UPDATE posts SET hidden=1 WHERE id='4'")
        home = self.web.get("/").data
        self.assertIn(b"/status/3", home)
        for ident in (2, 4, 5):
            self.assertNotIn(f"/status/{ident}".encode(), home)
        self.assertIn(b"/status/2", self.web.get("/quest/1").data)

    def test_only_direct_replies_and_originals(self):
        with self.conn:
            for post in (fixture(2, 1), fixture(3, 2, 1), fixture(4, 1, 5), fixture(1), fixture(1)):
                db.index_post(self.conn, post)
            for ref in ("quoted", "retweeted"):
                post = fixture(9)
                post["referenced_tweets"] = [{"id": "1", "type": ref}]
                db.index_post(self.conn, post)
        self.assertIn(b"1 reply", self.web.get("/").data)
        detail = self.web.get("/quest/1").data
        self.assertIn(b"/status/2", detail)
        self.assertNotIn(b"/status/3", detail)
        self.assertNotIn(b"/status/4", detail)
        self.assertNotIn("never persist", "\n".join(self.conn.iterdump()))
        self.assertEqual(self.web.get("/quest/9").status_code, 404)

    def test_resume_pages_and_commit_cursor_only_at_end(self):
        ident = (int(time.time() * 1000) - 60000 - 1288834974657) << 22
        with self.conn:
            db.set_state(self.conn, "since_id", ident - 1)
        fetch = Mock(side_effect=[page(fixture(ident+1, ident), token="more"),
                                  SyncError("outage"), page(fixture(ident))])
        with self.assertRaises(SyncError):
            sync(self.conn, fetch)
        self.assertEqual(db.state(self.conn, "since_id"), str(ident-1))
        sync(self.conn, fetch)
        first, failed, resumed = [call.args[2] for call in fetch.call_args_list]
        self.assertEqual(first["since_id"], str(ident-1))
        self.assertEqual(failed, resumed)
        self.assertEqual(resumed["until_id"], first["until_id"])
        self.assertNotIn("end_time", first)
        self.assertGreater(int(first["until_id"]), ident)
        self.assertEqual(resumed["next_token"], "more")
        self.assertEqual(db.state(self.conn, "since_id"), str(ident+1))
        self.assertIsNone(db.state(self.conn, "batch"))
        self.assertIn(b"1 reply", self.web.get("/").data)

    def test_page_limit_and_partial_response(self):
        with patch.dict(os.environ, X_MAX_PAGES="1"):
            sync(self.conn, Mock(return_value=page(fixture(2), token="more")))
        self.assertIsNone(db.state(self.conn, "since_id"))
        with self.assertRaises(SyncError):
            sync(self.conn, Mock(return_value={**page(), "errors": [{"title": "partial"}]}))
        self.assertTrue(db.state(self.conn, "batch"))

    def test_legacy_batch_restarts_at_last_committed_cursor(self):
        cursor = str((int(time.time() * 1000) - 120000 - 1288834974657) << 22)
        with self.conn:
            db.set_state(self.conn, "since_id", cursor)
            db.set_state(self.conn, "batch", json.dumps({"started": int(time.time()) - 50,
                         "since_id": cursor, "end_time": "2026-06-01T00:00:00Z", "next_token": "old"}))
        fetch = Mock(return_value=page())
        sync(self.conn, fetch)
        params = fetch.call_args.args[2]
        self.assertEqual(params["since_id"], cursor)
        self.assertNotIn("end_time", params)
        self.assertNotIn("next_token", params)
        self.assertEqual(db.state(self.conn, "since_id"), cursor)

    def test_media_visibility_follows_attachments_across_all_pages(self):
        gallery, video, mixed, unknown, gif = (fixture(i, 1 if i > 1 else None) for i in range(1, 6))
        for post, keys in zip((gallery, video, mixed, unknown, gif),
                              (["a", "b"], ["v"], ["a", "v"], ["a", "missing"], ["g"])):
            post["attachments"] = {"media_keys": keys}
        result = page(video, mixed, unknown, gif, gallery)
        result["includes"] = {"media": [{"media_key": k, "type": typ}
                                       for k, typ in (("a", "photo"), ("b", "photo"),
                                                      ("v", "video"), ("g", "animated_gif"))]}
        for m in result["includes"]["media"]:
            m["url"] = f"https://pbs.twimg.com/media/test_{m['media_key']}.jpg"
        result["includes"]["media"][0]["url"] = "https://pbs.twimg.com/media/test_a?format=jpg&name=large"
        fetch = Mock(return_value=result)
        sync(self.conn, fetch)
        self.assertIn("url", fetch.call_args.args[2]["media.fields"].split(","))
        refs = dict(self.conn.execute("SELECT id, photo_ref FROM posts"))
        self.assertEqual(refs, {"1": "test_a.jpg", "2": None, "3": "test_a.jpg",
                                "4": "test_a.jpg", "5": None})
        self.assertEqual(fetch.call_args.args[2]["expansions"], "attachments.media_keys")
        for path in ("/", "/?picks=1&open=1", "/quest/1"):
            html = self.web.get(path).get_data(as_text=True)
            self.assertIn('data-post="1" data-photos', html)
            self.assertEqual(html.count(" data-photos"), 1)
        thumbnail = 'src="https://pbs.twimg.com/media/test_a?format=jpg&amp;name=small"'
        self.assertEqual(self.web.get("/").text.count(thumbnail), 1)
        self.assertNotIn(thumbnail, self.web.get("/quest/1").text)
        # Rechecking a reply can enable its photos on both the branch and its detail page.
        gif["attachments"] = {"media_keys": ["a"]}
        with patch("elsewhere.sync.api", return_value={"data": [gif], "includes": result["includes"]}):
            check_links(self.conn, ["5"])
        self.assertEqual(self.web.get("/").text.count(thumbnail), 2)
        for path in ("/", "/quest/1"):
            self.assertIn('data-post="5" data-photos', self.web.get(path).get_data(as_text=True))

    def test_allowance_reserves_before_retry(self):
        with patch.dict(os.environ, X_MONTHLY_READ_LIMIT="110"), patch("elsewhere.sync.time.sleep"), \
             patch("elsewhere.sync.urlopen", side_effect=[URLError("timeout"),
                   io.BytesIO(json.dumps(page(fixture(1))).encode())]) as network:
            sync(self.conn)
            self.assertIn("max_results=10", network.call_args.args[0].full_url)
            with self.assertRaisesRegex(SyncError, "allowance"):
                sync(self.conn)
            self.assertEqual(network.call_count, 2)
        self.assertEqual(self.conn.execute("SELECT reads FROM usage").fetchone()[0], 101)

    def test_rate_limit_survives_next_job(self):
        error = HTTPError("https://api.x.com", 429, "rate", {"Retry-After": "180"}, None)
        with patch("elsewhere.sync.urlopen", side_effect=error) as network:
            for _ in range(2):
                with self.assertRaises(SyncError):
                    sync(self.conn)
            self.assertEqual(network.call_count, 1)
        self.assertGreater(float(db.state(self.conn, "resume_after")), time.time())

    def test_moderation_and_inconclusive_lookup(self):
        with self.conn:
            db.index_post(self.conn, fixture(1))
            db.index_post(self.conn, fixture(2, 1))
        with patch("elsewhere.sync.api", return_value={"errors": [{"type": "unknown"}]}):
            check_links(self.conn, ["1"])
        self.assertEqual(self.web.get("/quest/1").status_code, 200)
        with patch("elsewhere.sync.api", return_value={"errors": [
            {"resource_id":"1", "type":"https://api.x.com/2/problems/resource-not-found"}]}):
            check_links(self.conn, ["1"])
        self.assertEqual(self.web.get("/quest/1").status_code, 404)
        self.assertNotIn(b"/status/2", self.web.get("/").data)
        with patch("sys.argv", ["elsewhere", "remove", "1"]):
            from elsewhere.__main__ import main
            main()
        with self.conn:
            db.index_post(self.conn, fixture(1))
        self.assertIsNone(self.conn.execute("SELECT id FROM posts WHERE id='1'").fetchone())

    def test_no_search_overlap_or_mixed_demo(self):
        with exclusive(), self.assertRaises(SyncError), exclusive():
            pass
        with self.conn:
            db.index_post(self.conn, fixture(1))
        with self.assertRaises(ValueError):
            seed(self.conn)
        with patch.dict(os.environ, X_BEARER_TOKEN=""), self.assertRaises(SyncError):
            api(self.conn, "tweets", {}, 1, 1)
