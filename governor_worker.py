"""One-pass CureX Governor job.

Run `python governor_worker.py --once` manually or as an occasional Railway cron Job.
The API already performs admission-time moderation. This script re-checks older
public content after rule updates. Points attached to re-quarantined content are
held until a moderator decides. It never approves scientific results, suspends
users automatically or moves money.
"""
from __future__ import annotations
import argparse
import json
from app import db, now, record_case
from governor import assess


def run_once() -> dict:
    quarantined_threads = quarantined_replies = 0
    with db() as connection:
        connection.execute('DELETE FROM rate_entries')  # legacy table; rate limits now live in memory
        threads = connection.execute("SELECT id,title,body,sources FROM threads WHERE status='unreviewed' AND demo=0 ORDER BY id DESC LIMIT 500").fetchall()
        for t in threads:
            assessment = assess(t['title'] + ' ' + t['body'], len(json.loads(t['sources'] or '[]')))
            if not assessment.flags:
                continue
            connection.execute("UPDATE threads SET status='needs-review' WHERE id=?", (t['id'],))
            connection.execute("UPDATE points_ledger SET status='held' WHERE object_type='thread' AND object_id=? AND status='provisional'", (t['id'],))
            record_case(connection, 'thread', t['id'], assessment.flags)
            quarantined_threads += 1
        replies = connection.execute("SELECT id,body FROM replies WHERE status='visible' ORDER BY id DESC LIMIT 800").fetchall()
        for r in replies:
            assessment = assess(r['body'], kind='reply')
            if not assessment.flags:
                continue
            connection.execute("UPDATE replies SET status='needs-review' WHERE id=?", (r['id'],))
            connection.execute("UPDATE points_ledger SET status='held' WHERE object_type='reply' AND object_id=? AND status='provisional'", (r['id'],))
            record_case(connection, 'reply', r['id'], assessment.flags)
            quarantined_replies += 1
    return {'run_at': now(), 'quarantined_threads': quarantined_threads, 'quarantined_replies': quarantined_replies, 'scientific_approval': False, 'payouts': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Scan recent posts once then exit')
    opts = parser.parse_args()
    if not opts.once:
        parser.error('Use --once; long-running worker loops are intentionally not supported.')
    print(json.dumps(run_once()))
