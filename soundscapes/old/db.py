import contextlib
import os
import mysql.connector

config = {
    'db_host': os.getenv('DB_HOST'),
    'db_user': os.getenv('DB_USER'),
    'db_password': os.getenv('DB_PASSWORD'),
    'db_name': os.getenv('DB_NAME'),
}

def connect():
    return mysql.connector.connect(
        host=config['db_host'],
        user=config['db_user'],
        password=config['db_password'], 
        database=config['db_name']
    )

def get_automated_user(conn):
    cursor = conn.cursor()
    automated_user = 'automated-user'

    cursor.execute('select user_id from users where login = %s', (automated_user, ))
    result = cursor.fetchone()
    if result is not None:
        cursor.close()
        (user_id,) = result
        return user_id
    
    cursor.execute('''insert into users (login, password, firstname, lastname, email) values (%s, '',  'Automated', 'Job', 'automated-user@arbimon.org')''', (automated_user,))
    conn.commit()
    user_id = cursor.lastrowid

    cursor.close()
    return user_id


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

    cursor.execute('select count(*) from recordings where site_id = %s and year(datetime) = %s', (site_id, year))
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
    cursor.execute('insert into playlists (project_id, name, playlist_type_id, total_recordings) values (%s, %s, 1, %s)', (project_id, playlist_name, total_recordings))
    conn.commit()
    playlist_id = cursor.lastrowid

    # Create playlist_recordings rows
    cursor.execute('''insert into playlist_recordings (playlist_id, recording_id)
        select %s, recording_id from recordings where site_id = %s and year(datetime) = %s''', (playlist_id, site_id, year))
    conn.commit()

    if cursor.rowcount != total_recordings:
        print('WARN: total recordings does not match inserted recordings for playlist', playlist_id)

    cursor.close()
    return playlist_id, playlist_name

def create_job(conn, playlist_id, user_id, threshold = 0.05):
    cursor = conn.cursor()

    cursor.execute('select project_id, name, total_recordings from playlists where playlist_id = %s', (playlist_id, ))
    (project_id, playlist_name, total_recordings) = cursor.fetchone()

    cursor.execute(
        '''insert into jobs (job_type_id, date_created, last_update, project_id, user_id, state, progress_steps, remarks, uri, hidden) 
        values (4, now(), now(), %s, %s, 'initializing', %s, '', '', 0)''',
        (project_id, user_id, total_recordings))
    conn.commit()
    job_id = cursor.lastrowid

    cursor.execute(
        '''insert into job_params_soundscape (job_id, playlist_id, max_hertz, bin_size, soundscape_aggregation_type_id, name, threshold, normalize) 
        values (%s, %s, 24000, 344, 1, %s, %s, 1)''',
        (job_id, playlist_id, playlist_name, threshold))
    conn.commit()
    cursor = conn.cursor()

    return job_id