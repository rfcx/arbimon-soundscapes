import base64
import hashlib
import os
from typing import Union

# mysql2pg Phase 5.5 (W5, 2026-07-16): dialect-aware DB layer.
# ARBIMON_DB_DIALECT=mysql (DEFAULT - byte-for-byte today's behavior) or
# postgres. The PG path activates ONLY via env at the coordinated jobs-plane
# flip; nothing changes for existing deploys. Env names stay DB_* for both
# dialects (the flip changes env VALUES, not names; ARBIMON_DB_PORT overrides
# DB_PORT when set). Mirrors the W1/W4 pattern.
#
# SQL portability changes carried across this worker (validated equivalent
# both ways):
#   - backticks stripped (the schema names are all lowercase; PG identifiers
#     unquoted, MySQL accepts unquoted lowercase identically)
#   - double-quoted STRING literals -> single quotes ("processing" is an
#     IDENTIFIER to PG and would hard-error)
#   - MySQL year()/DATE_FORMAT()/IF(LEFT()) -> dialect-appropriate expressions
#     (helpers below; identical results on both engines)
#   - cursor.lastrowid -> INSERT ... RETURNING on PG (helper below)

DIALECT = os.getenv('ARBIMON_DB_DIALECT', 'mysql').lower()
IS_PG = DIALECT in ('postgres', 'postgresql', 'pg')

if IS_PG:
    import psycopg2
    import psycopg2.errors  # noqa: F401
else:
    import mysql.connector

config = {
    'db_host': os.getenv('DB_HOST'),
    'db_port': int(os.getenv('ARBIMON_DB_PORT') or os.getenv('DB_PORT', '3306')),
    'db_user': os.getenv('DB_USER'),
    'db_password': os.getenv('DB_PASSWORD'),
    'db_name': os.getenv('DB_NAME'),
}


def connect():
    if IS_PG:
        return psycopg2.connect(
            host=config['db_host'],
            port=config['db_port'],
            user=config['db_user'],
            password=config['db_password'],
            dbname=config['db_name'],
            connect_timeout=10,
        )
    return mysql.connector.connect(
        host=config['db_host'],
        user=config['db_user'],
        password=config['db_password'],
        database=config['db_name']
    )


# --- tiny dialect helpers -------------------------------------------------

def year_expr(column):
    """MySQL year(col) -> PG EXTRACT(YEAR FROM col). Numeric both ways."""
    return 'EXTRACT(YEAR FROM {})'.format(column) if IS_PG else 'year({})'.format(column)


# MySQL DATE_FORMAT() spec -> PG to_char() pattern, for the aggregation date
# tokens used by soundscape.py (aggregations dict). %w is special: MySQL %w is
# 0=Sunday..6=Saturday; PG to_char 'D' is 1=Sunday..7=Saturday (off by one), so
# %w maps to EXTRACT(DOW ...) which is 0=Sunday..6=Saturday (matches MySQL).
_DATEFMT_MYSQL_TO_PG = {
    '%H': "to_char({col}, 'HH24')",   # hour 00-23
    '%d': "to_char({col}, 'DD')",     # day of month 01-31
    '%j': "to_char({col}, 'DDD')",    # day of year 001-366
    '%m': "to_char({col}, 'MM')",     # month 01-12
    '%Y': "to_char({col}, 'YYYY')",   # year
    '%w': "CAST(EXTRACT(DOW FROM {col}) AS INTEGER)",  # 0=Sun..6=Sat
}


def date_format_expr(column, mysql_fmt):
    """Return a dialect-appropriate expression equivalent to
    MySQL DATE_FORMAT(column, mysql_fmt) for the soundscape aggregation tokens.

    On MySQL this reproduces the exact original expression (double-quoted fmt,
    byte-identical). On PG it maps the token to the equivalent to_char/EXTRACT.
    """
    if not IS_PG:
        return 'DATE_FORMAT({}, "{}")'.format(column, mysql_fmt)
    tpl = _DATEFMT_MYSQL_TO_PG.get(mysql_fmt)
    if tpl is None:
        raise ValueError('unsupported DATE_FORMAT token for PG port: {!r}'.format(mysql_fmt))
    return tpl.format(col=column)


def datetime_str_expr(column):
    """MySQL DATE_FORMAT(col, '%Y-%m-%d %H:%i:%s') -> PG to_char(col,
    'YYYY-MM-DD HH24:MI:SS'). Both yield a string later parsed with
    strptime('%Y-%m-%d %H:%M:%S'); identical text on both engines."""
    if IS_PG:
        return "to_char({}, 'YYYY-MM-DD HH24:MI:SS')".format(column)
    return "DATE_FORMAT({}, '%Y-%m-%d %H:%i:%s')".format(column)

# IF(LEFT(uri,8)='project_',1,0) equivalent, identical result both engines.
# MySQL IF() does not exist in PG; CASE is identical on both.
LEGACY_EXPR = "CASE WHEN LEFT(r.uri, 8) = 'project_' THEN 1 ELSE 0 END"


def cursor_column_names(cursor):
    """mysql.connector exposes cursor.column_names; psycopg2 uses
    cursor.description. Return the column-name tuple dialect-neutrally."""
    if IS_PG:
        return tuple(col.name for col in cursor.description)
    return cursor.column_names


def insert_returning_id(cursor, sql, params, id_column):
    """INSERT and return the generated id, dialect-appropriately.

    MySQL: execute + cursor.lastrowid. PG: append RETURNING <id_column> and
    fetch. The caller's SQL must NOT already carry RETURNING.
    """
    if IS_PG:
        cursor.execute(sql + ' RETURNING ' + id_column, params)
        return cursor.fetchone()[0]
    cursor.execute(sql, params)
    return cursor.lastrowid


def get_automated_user(conn):
    cursor = conn.cursor()
    automated_user = 'automated-user'

    cursor.execute('select user_id from users where login = %s', (automated_user, ))
    result = cursor.fetchone()
    if result is not None:
        cursor.close()
        (user_id,) = result
        return user_id

    user_id = insert_returning_id(
        cursor,
        '''insert into users (login, password, firstname, lastname, email) values (%s, '',  'Automated', 'Job', 'automated-user@arbimon.org')''',
        (automated_user,),
        'user_id')
    conn.commit()

    cursor.close()
    return user_id

def find_project(conn, url_or_id):
    cursor = conn.cursor()
    
    conditions = [
        'url = %s',
        'external_id = %s',
        'project_id = %s'
    ]
    for condition in conditions:
        cursor.execute(f'select project_id from projects where {condition}', (url_or_id, ))
        result = cursor.fetchone()
        if result is not None:
            cursor.close()
            (project_id,) = result
            return project_id
    
    cursor.close()
    return None

def find_aggregation(conn, identifier) -> Union[int,None]:
    cursor = conn.cursor()

    # Get aggregation id from identifier
    cursor.execute('select soundscape_aggregation_type_id from soundscape_aggregation_types where identifier = %s', (identifier,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        return None
    
    cursor.close()
    (aggregation_type_id, ) = row
    return aggregation_type_id

def get_sites(conn, project_id, query = None):
    cursor = conn.cursor()

    if query is None:
        # all sites in project
        sql = 'select site_id, name from sites where project_id = %s and deleted_at is null'
        cursor.execute(sql, (project_id,))
        results = {site_id: name for (site_id, name) in cursor}
    else:
        # only sites matching a query term, e.g. AB*,CD*,EF05,EF06
        results = {}
        for term in query.split(','):
            term = term.replace('*', '%')
            cursor.execute('select site_id, name from sites where name like %s and project_id = %s and deleted_at is null', (term, project_id))
            for (site_id, name) in cursor:
                results[site_id] = name

    cursor.close()
    return results

def create_playlist(conn, project_id, site_id, site_name, year):
    playlist_name = f'{site_name} ({site_id}) {year}'
    cursor = conn.cursor()

    cursor.execute('select count(*) from recordings where site_id = %s and ' + year_expr('datetime') + ' = %s', (site_id, year))
    (total_recordings,) = cursor.fetchone()

    # No recordings
    if total_recordings == 0:
        return None

    # Shallow check for duplicate playlist
    cursor.execute('select playlist_id, name from playlists where project_id = %s and name = %s and total_recordings = %s', (project_id, playlist_name, total_recordings))
    result = cursor.fetchone()
    if result is not None:
        cursor.close()
        return result

    # Find unique playlist name
    cursor.execute('select playlist_id from playlists where project_id = %s and name = %s', (project_id, playlist_name))
    result = cursor.fetchone()
    if result is not None:
        playlist_name += f' {total_recordings}'
    
    # Create playlists row
    playlist_id = insert_returning_id(
        cursor,
        'insert into playlists (project_id, name, playlist_type_id, total_recordings) values (%s, %s, 1, %s)',
        (project_id, playlist_name, total_recordings),
        'playlist_id')
    conn.commit()

    # Create playlist_recordings rows
    cursor.execute('''insert into playlist_recordings (playlist_id, recording_id)
        select %s, recording_id from recordings where site_id = %s and ''' + year_expr('datetime') + ' = %s', (playlist_id, site_id, year))
    conn.commit()

    if cursor.rowcount != total_recordings:
        print('WARN: total recordings does not match inserted recordings for playlist', playlist_id)

    cursor.close()
    return playlist_id, playlist_name

def create_job(conn, playlist_id, user_id, aggregation = 'time_of_day', bin_size = 344, threshold = 0.05, normalize = 1, soundscape_name = None) -> Union[int,None]:
    cursor = conn.cursor()

    # Get aggregation id from identifier
    aggregation_type_id = find_aggregation(conn, aggregation)
    if aggregation_type_id is None:
        cursor.close()
        return None

    # Get the playlist
    cursor.execute('select project_id, name, total_recordings from playlists where playlist_id = %s', (playlist_id, ))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        return None
    (project_id, playlist_name, total_recordings) = row

    # Additional parameters
    max_hertz = 24000 # TODO compute this from the recordings
    job_name = playlist_name if soundscape_name is None else soundscape_name
    # job_name_suffix = soundscape_hash(playlist_id, aggregation_type_id, bin_size, threshold, normalize) # TODO make job name unique

    job_id = insert_returning_id(
        cursor,
        '''insert into jobs (job_type_id, date_created, last_update, project_id, user_id, state, progress_steps, remarks, uri, hidden) 
        values (4, now(), now(), %s, %s, 'initializing', %s, '', '', 0)''',
        (project_id, user_id, total_recordings),
        'job_id')
    conn.commit()

    cursor.execute(
        '''insert into job_params_soundscape (job_id, playlist_id, name, max_hertz, soundscape_aggregation_type_id, bin_size, threshold, normalize) 
        values (%s, %s, %s, %s, %s, %s, %s, %s)''',
        (job_id, playlist_id, job_name, max_hertz, aggregation_type_id, bin_size, threshold, normalize))
    conn.commit()
    cursor.close()

    return job_id

def soundscape_exists(conn, playlist_id, aggregation, bin_size, threshold, normalize) -> bool:
    aggregation_type_id = find_aggregation(conn, aggregation)
    if aggregation_type_id is None:
        return False
    
    # Find a matching soundscape
    cursor = conn.cursor()
    cursor.execute('''select soundscape_id from soundscapes where playlist_id = %s and soundscape_aggregation_type_id = %s and bin_size = %s and abs(threshold - %s) < 0.001 and normalized = %s limit 1''',
                   (playlist_id, aggregation_type_id, bin_size, threshold, normalize))
    row = cursor.fetchone()
    cursor.close()
    return row is not None

def soundscape_hash(playlist_id: int, aggregation_id: int, bin_size: int, threshold: float, normalize: int) -> str:
    plain = f'{playlist_id}_{aggregation_id}_{bin_size}_{threshold}_{normalize}'
    d = hashlib.md5(plain).digest()
    return str(base64.b64encode(d))[:5]
