"""One-off, resumable backfill of arbimon.soundscape_grids + soundscape_recordings
from each existing soundscape's index.scidx (2026-09-25).

Operator GO: goifirr 22:12 EDT (#2). Design + evidence: rfcx-local
runbooks/evidence/irr-ledger-20260925-soundscape-grid-and-membership.md.

Safety properties:
  * one soundscape per transaction; idempotent (ON CONFLICT) so re-running is safe;
  * RESUMABLE: skips soundscapes that already have a grid row (unless --force);
  * THROTTLED: --sleep between soundscapes, and pauses while the standby's replay
    lag exceeds --max-lag-bytes (replication is synchronous on this cluster);
  * never runs from a serving pod (rfcx-local OPEN-ITEMS §401);
  * --dry-run does everything except COMMIT (rolls each transaction back).

norm_vector: recomputed from the playlist when it still exists
('playlist-at-backfill'); for soundscapes whose playlist was deleted it is the
per-bin count of the scidx's OWN recordings ('scidx-recordings'), flagged as a
reconstruction, never presented as the original.

Usage (in a pod with the job image + worker DB creds + S3 creds):
  python -m soundscapes.backfill_grids [--ids 1,2,3] [--limit N] [--dry-run]
      [--sleep 0.2] [--max-lag-bytes 64000000] [--force]
"""
import argparse
import contextlib
import json
import os
import sys
import time

import boto3

from .old.db import connect, cursor_column_names, date_format_expr
from .old.soundscape import grid as G
from .old import playlist_to_soundscape as J

AGG = {
    'time_of_day':   {'date': ['%H'], 'projection': [1]},
    'day_of_month':  {'date': ['%d'], 'projection': [1]},
    'day_of_year':   {'date': ['%j'], 'projection': [1]},
    'month_in_year': {'date': ['%m'], 'projection': [1]},
    'day_of_week':   {'date': ['%w'], 'projection': [1]},
    'year':          {'date': ['%Y'], 'projection': [1]},
}

def log(**kw):
    kw['ts'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    print(json.dumps(kw), flush=True)

def replay_lag_bytes(cur):
    cur.execute("select coalesce(max(pg_wal_lsn_diff(sent_lsn, replay_lsn)), 0) from pg_stat_replication")
    return int(cur.fetchone()[0] or 0)

def norm_from_recordings(cur, aggregation, rec_ids, playlist_id):
    parts = [date_format_expr('R.datetime', dp) for dp in AGG[aggregation]['date']]
    sel = ', '.join('%s as dp_%d' % (d, i) for i, d in enumerate(parts))
    grp = ', '.join(parts)
    if playlist_id is not None:
        cur.execute('select 1 from playlists where playlist_id = %s', (playlist_id,))
        if cur.fetchone():
            cur.execute('SELECT {} , COUNT(*) as count FROM playlist_recordings PR '
                        'JOIN recordings R ON R.recording_id = PR.recording_id '
                        'WHERE PR.playlist_id = %s GROUP BY {}'.format(sel, grp), (playlist_id,))
            src = 'playlist-at-backfill'
        else:
            src = None
    else:
        src = None
    if src is None:
        cur.execute('SELECT {} , COUNT(*) as count FROM recordings R '
                    'WHERE R.recording_id = ANY(%s::bigint[]) GROUP BY {}'.format(sel, grp), (list(rec_ids),))
        src = 'scidx-recordings'
    nv = {}
    for row in [dict(zip(cursor_column_names(cur), r)) for r in cur.fetchall()]:
        idx = sum(int(row['dp_%d' % i]) * p for i, p in enumerate(AGG[aggregation]['projection']))
        nv[str(idx)] = int(row['count'])
    return nv, src

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--sleep', type=float, default=0.2)
    ap.add_argument('--max-lag-bytes', type=int, default=64 * 1024 * 1024)
    ap.add_argument('--bucket', default=os.getenv('S3_LEGACY_BUCKET_NAME', 'arbimon2'))
    a = ap.parse_args()

    s3 = boto3.client('s3', endpoint_url=os.getenv('S3_ENDPOINT'),
                      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                      verify=os.getenv('AWS_CA_BUNDLE') or True)
    db = connect()
    db.autocommit = False
    with contextlib.closing(db.cursor()) as cur:
        cur.execute("set statement_timeout = '120s'; set lock_timeout = '5s'")
        q = ('select s.soundscape_id, s.project_id, s.playlist_id, s.normalized, s.threshold,'
             ' s.threshold_type, s.visual_max_value, a.identifier'
             ' from soundscapes s join soundscape_aggregation_types a using (soundscape_aggregation_type_id)'
             ' where s.uri is not null')
        params = []
        if a.ids:
            q += ' and s.soundscape_id = any(%s::bigint[])'
            params.append([int(x) for x in a.ids.split(',') if x])
        if not a.force:
            q += ' and not exists (select 1 from soundscape_grids g where g.soundscape_id = s.soundscape_id)'
        q += ' order by s.soundscape_id'
        if a.limit:
            q += ' limit %d' % a.limit
        cur.execute(q, params)
        todo = cur.fetchall()
        db.commit()
    log(ev='start', todo=len(todo), dry_run=a.dry_run, bucket=a.bucket)

    ok = missing = failed = 0
    for sid, pid, plid, normalized, threshold, ttype, vmax, agg in todo:
        t0 = time.time()
        try:
            key = 'project_%d/soundscapes/%d/index.scidx' % (pid, sid)
            try:
                body = s3.get_object(Bucket=a.bucket, Key=key)['Body'].read()
            except s3.exceptions.NoSuchKey:
                missing += 1
                log(ev='missing_scidx', sid=sid, key=key)
                continue
            path = '/tmp/bf-%d.scidx' % sid
            with open(path, 'wb') as f:
                f.write(body)
            parsed = G.parse_scidx(body)
            with contextlib.closing(db.cursor()) as cur:
                while replay_lag_bytes(cur) > a.max_lag_bytes:
                    log(ev='throttle', sid=sid)
                    time.sleep(5)
                nv, src = (norm_from_recordings(cur, agg, set(parsed['recordings']), plid)
                           if int(normalized or 0) else (None, 'none'))
                rows = J.build_grid_rows(path, sid, dict(visual_max_value=vmax, normalized=normalized,
                                                          threshold=threshold, threshold_type=ttype), nv)
                rows['norm_source'] = src
                J.write_grid_rows(cur, rows)
                if a.dry_run:
                    db.rollback()
                else:
                    db.commit()
            os.unlink(path)
            ok += 1
            log(ev='ok', sid=sid, grid=len(rows['grid']), members=len(rows['recordings']),
                norm=src, ms=int((time.time() - t0) * 1000))
        except Exception as e:
            db.rollback()
            failed += 1
            log(ev='fail', sid=sid, err=repr(e)[:300])
        time.sleep(a.sleep)
    log(ev='done', ok=ok, missing=missing, failed=failed, dry_run=a.dry_run)
    db.close()
    return 1 if failed else 0

if __name__ == '__main__':
    sys.exit(main())