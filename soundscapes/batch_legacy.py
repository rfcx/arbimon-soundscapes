import argparse
from .config.logs import get_logger
from .config.read_config import read_config
from .legacy.playlist_to_soundscape import playlist_to_soundscape
from .legacy.db import connect, get_automated_user, get_sites, create_playlist, create_job

log = get_logger()

def main(batch_config):
    log.info("PROCESS: Start")

    project_id = 1907
    sites = 'Park*'
    year = 2022
    soundscape_threshold = 0.05

    conn = connect()

    user_id = get_automated_user(conn)

    # Loop over sites
    sites = get_sites(conn, project_id, sites)
    for (site_id, site_name) in sites.items():
        print('Processing site', site_id, site_name)

        result = create_playlist(conn, project_id, site_id, site_name, year)
        if result is None:
            print('- No recordings for', year, '(skipping job)')
            continue
        playlist_id, playlist_name = result
        print('- Created playlist', playlist_id, playlist_name)

        job_id = create_job(conn, playlist_id, user_id, soundscape_threshold)
        print('- Created and initialized job', job_id)

        playlist_to_soundscape(job_id)
        print('- Completed job', job_id)

    log.info("PROCESS: End")

def get_args():
    parser = argparse.ArgumentParser()
    # Config files
    parser.add_argument('--config', help="Config file path", type=argparse.FileType('r'))
    parser.add_argument('--stdin', help="Config via stdin", action='store_true')
    # Overrides
    parser.add_argument('--destination', help="Send detections to", type=str)

    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    config = read_config(args)
    main(config)
