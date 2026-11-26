import argparse
import logging
import sqlite3
import sys
from contextlib import closing

from .db import connect, init, post_id, state
from .demo import seed
from .sync import SyncError, check_links, exclusive, sync


def main():
    parser = argparse.ArgumentParser(description="Manage the Dear Elsewhere index")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("init", "demo", "sync", "status"):
        sub.add_parser(name)
    for name in ("hide", "show", "remove"):
        sub.add_parser(name).add_argument("id", type=post_id)
    sub.add_parser("check-links").add_argument("ids", nargs="+", type=post_id)
    args = parser.parse_args()
    with closing(connect()) as conn:
        init(conn)
        if args.action == "init":
            return
        if args.action == "demo":
            with exclusive(), conn:
                seed(conn)
        elif args.action in ("sync", "check-links"):
            with exclusive():
                if state(conn, "demo"):
                    raise SyncError("use a separate live database for API calls")
                if args.action == "sync":
                    sync(conn)
                else:
                    check_links(conn, args.ids)
        elif args.action == "status":
            for key in ("demo", "since_id", "last_success", "resume_after"):
                print(key, state(conn, key) or "—")
            print("unfinished batch", bool(state(conn, "batch")))
            for row in conn.execute("SELECT month,reads FROM usage ORDER BY month DESC LIMIT 3"):
                print("reserved or consumed reads", *row)
        elif args.action == "remove":
            with conn:
                conn.execute("INSERT OR IGNORE INTO removed VALUES (?)", (args.id,))
                conn.execute("DELETE FROM posts WHERE id=?", (args.id,))
        else:
            with conn:
                changed = conn.execute("UPDATE posts SET hidden=? WHERE id=?",
                                       (args.action == "hide", args.id)).rowcount
                if not changed:
                    raise ValueError("post is absent from the index")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        main()
    except (SyncError, ValueError, KeyError, OSError, sqlite3.Error) as error:
        sys.exit(str(error))
