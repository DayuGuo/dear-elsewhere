"""Bounded X API reads. Never persist or log API bodies."""
import fcntl
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .db import DEFAULT_DB, index_post, photo_metadata, post_id, set_state, state

QUERY = "(#DearElsewhereQuest OR #DearElsewhereDone) -is:retweet"
FIELDS = "created_at,conversation_id,referenced_tweets,entities,note_tweet,withheld,attachments"
MEDIA_PARAMS = {"expansions": "attachments.media_keys", "media.fields": "type,url"}
LOG = logging.getLogger(__name__)


class SyncError(RuntimeError):
    pass


@contextmanager
def exclusive():
    path = Path(os.environ.get("DEAR_DB", DEFAULT_DB)).resolve()
    with open(str(path) + ".lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SyncError("another API job is running") from exc
        yield


def cooldown(headers):
    deadline = time.time() + 60
    retry = headers.get("Retry-After")
    if retry:
        try:
            deadline = time.time() + int(retry)
        except ValueError:
            deadline = parsedate_to_datetime(retry).timestamp()
    return max(deadline, int(headers.get("x-rate-limit-reset", 0))) + 1


def api(conn, endpoint, params, capacity, minimum):
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        raise SyncError("set X_BEARER_TOKEN in the server environment")
    limit = int(os.environ.get("X_MONTHLY_READ_LIMIT", "1500"))
    for attempt in range(3):
        if float(state(conn, "resume_after") or 0) > time.time():
            raise SyncError("rate-limit cooldown active; retry at a later timer tick")
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        # Reserve before network I/O; unknown outcomes stay charged locally.
        with conn:
            conn.execute("INSERT OR IGNORE INTO usage VALUES (?,0)", (month,))
            used = conn.execute("SELECT reads FROM usage WHERE month=?", (month,)).fetchone()[0]
            reserved = min(capacity, limit - used)
            if reserved < minimum:
                raise SyncError("monthly read allowance reached")
            conn.execute("UPDATE usage SET reads=reads+? WHERE month=?", (reserved, month))
        if endpoint.endswith("/recent"):
            params = dict(params, max_results=reserved)
        url = "https://api.x.com/2/" + endpoint + "?" + urlencode(params)
        request = Request(url, headers={"Authorization": "Bearer " + token})
        try:
            with urlopen(request, timeout=25) as response:
                result = json.load(response)
        except HTTPError as exc:
            if exc.code == 429:
                with conn:
                    set_state(conn, "resume_after", cooldown(exc.headers))
                raise SyncError("X rate limit reached; retry deferred") from exc
            if exc.code == 400 and params.get("next_token"):
                with conn:
                    conn.execute("DELETE FROM state WHERE key='batch'")
            if exc.code < 500 or attempt == 2:
                raise SyncError(f"X returned HTTP {exc.code}; cursor preserved") from exc
        except (URLError, TimeoutError, HTTPException) as exc:
            if attempt == 2:
                raise SyncError("network failure; cursor preserved") from exc
        else:
            data = result.get("data", [])
            if not isinstance(data, list):
                raise SyncError("unexpected API data")
            if not result.get("errors") and len(data) <= reserved:
                # Only refund after an unambiguous, correctly shaped response.
                is_search = endpoint.endswith("/recent")
                if (not is_search and "data" in result) or (
                    is_search and result.get("meta", {}).get("result_count") == len(data)
                ):
                    with conn:
                        conn.execute("UPDATE usage SET reads=reads-? WHERE month=?",
                                     (reserved - len(data), month))
            return result
        LOG.warning("temporary X failure; retry %d", attempt + 1)
        time.sleep(2 ** (attempt + 1))
    raise SyncError("retry limit reached")


def utc(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def media_by_key(result):
    return {m["media_key"]: m for m in result.get("includes", {}).get("media", [])
            if m.get("media_key")}


def new_batch(conn):
    end = int(time.time()) - 30
    batch = {"started": end}
    cursor = state(conn, "since_id")
    earliest = time.time() - 7 * 86400
    if cursor and ((int(cursor) >> 22) + 1288834974657) / 1000 > earliest:
        batch["since_id"] = cursor
        # Recent Search rejects ID bounds combined with time bounds.
        until_id = (end * 1000 - 1288834974657) << 22
        if until_id > int(cursor):
            batch["until_id"] = str(until_id)
    return batch


def sync(conn, fetch=api):
    limit = int(os.environ.get("X_MAX_PAGES", "12"))
    if limit < 1:
        raise SyncError("X_MAX_PAGES must be positive")
    saved = state(conn, "batch")
    batch = json.loads(saved) if saved else new_batch(conn)
    if "since_id" in batch and "end_time" in batch:
        batch = new_batch(conn)
    # Recent Search cannot recover results that have aged out while paused.
    horizon = time.time() - 7 * 86400
    if batch["started"] <= horizon:
        LOG.warning("unfinished batch expired outside the seven-day search window")
        batch = new_batch(conn)
    cursor = state(conn, "since_id")
    highest = int(batch.get("highest") or cursor or 0)
    for page in range(1, limit + 1):
        params = {k: v for k, v in batch.items() if k not in ("highest", "started")}
        params.update(query=QUERY, sort_order="recency", **{"tweet.fields": FIELDS}, **MEDIA_PARAMS)
        result = fetch(conn, "tweets/search/recent", params, 100, 10)
        rows = result.get("data", [])
        meta = result.get("meta", {})
        if result.get("errors") or meta.get("result_count") != len(rows):
            raise SyncError("partial or malformed search page; cursor preserved")
        nxt = meta.get("next_token")
        if nxt and nxt == batch.get("next_token"):
            raise SyncError("repeated pagination token")
        media = media_by_key(result)
        with conn:
            for row in rows:
                highest = max(highest, int(post_id(row["id"])))
                index_post(conn, row, media)
            if nxt:
                batch.update(next_token=nxt, highest=str(highest))
                set_state(conn, "batch", json.dumps(batch))
            else:
                if highest:
                    set_state(conn, "since_id", highest)
                conn.execute("DELETE FROM state WHERE key='batch'")
                set_state(conn, "last_success", utc(time.time()))
        LOG.info("search page %d: received %d; more=%s", page, len(rows), bool(nxt))
        if not nxt:
            LOG.info("search complete; since_id=%s", highest or "unset")
            return
    LOG.info("page limit reached; next run resumes this batch")


def check_links(conn, ids):
    ids = list(dict.fromkeys(post_id(ident) for ident in ids))
    if not 1 <= len(ids) <= 100:
        raise SyncError("provide 1 to 100 post IDs")
    result = api(conn, "tweets", {"ids": ",".join(ids), **MEDIA_PARAMS,
                                  "tweet.fields": "withheld,attachments,referenced_tweets"}, len(ids), len(ids))
    found = {p["id"] for p in result.get("data", [])}
    unavailable = {p["id"] for p in result.get("data", []) if p.get("withheld")}
    for error in result.get("errors", []):
        ident = error.get("resource_id") or error.get("value")
        if error.get("type", "").endswith(("/resource-not-found", "/not-authorized-for-resource")):
            if ident in ids:
                unavailable.add(ident)
    with conn:
        media = media_by_key(result)
        conn.executemany("UPDATE posts SET show_photos=?, photo_ref=? WHERE id=?",
                         [(*photo_metadata(p, media), p["id"]) for p in result.get("data", [])])
        conn.executemany("UPDATE posts SET hidden=1 WHERE id=?", [(i,) for i in unavailable])
    LOG.info("checked=%d unavailable=%d inconclusive=%d", len(ids), len(unavailable),
             len(set(ids) - found - unavailable))
