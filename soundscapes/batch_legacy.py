import argparse
from .config.logs import get_logger
from .config.read_config import read_config
from .old.playlist_to_soundscape import playlist_to_soundscape
from .old.db import connect, get_automated_user, get_sites, create_playlist, create_job, find_project

log = get_logger()

def main(config):
    conn = connect()
    
    project_id = find_project(conn, config['project'])
    if project_id is None:
        log.critical('Project not found')
        exit(1)
    
    sites = config['sites'] if 'sites' in config else None
    year = config['year'] if 'year' in config else None
    soundscape_bin_size = config['soundscape_bin_size']
    soundscape_threshold = config['soundscape_threshold']
    soundscape_normalize = config['soundscape_normalize']

    user_id = get_automated_user(conn)

    # One soundscape (and playlist) for each site
    sites = get_sites(conn, project_id, sites)
    for (site_id, site_name) in sites.items():
        print('Processing site', site_id, site_name)

        result = create_playlist(conn, project_id, site_id, site_name, year)
        if result is None:
            print('- No recordings for', year, '(skipping job)')
            continue
        playlist_id, playlist_name = result
        print('- Created playlist', playlist_id, playlist_name)

        job_id = create_job(conn, playlist_id, user_id, soundscape_bin_size, soundscape_threshold, soundscape_normalize)
        print('- Created and initialized job', job_id)

        playlist_to_soundscape(job_id)
        print('- Completed job', job_id)


if __name__ == "__main__":
    log.info('PROCESS: Initialization')
    config = read_config()
    log.info('PROCESS: Job started')
    main(config)
    log.info('PROCESS: Job completed')
