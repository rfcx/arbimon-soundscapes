from .config.logs import get_logger
from .config.read_config import read_config
from .old.playlist_to_soundscape import playlist_to_soundscape
from .old.db import connect, get_automated_user, create_job

log = get_logger()

def main(config):
    conn = connect()
    
    playlist_id = config['playlist_id']
    job_name = config['job_name']
    soundscape_aggregation = config['soundscape_aggregation']
    soundscape_bin_size = config['soundscape_bin_size']
    soundscape_threshold = config['soundscape_threshold']
    soundscape_normalize = config['soundscape_normalize']

    user_id = get_automated_user(conn)

    job_id = create_job(conn, playlist_id, user_id, soundscape_aggregation, soundscape_bin_size, soundscape_threshold, soundscape_normalize, job_name)
    print('- Created and initialized job', job_id)
    if job_id is None:
        print('Something went wrong creating the job')
        exit(1)

    playlist_to_soundscape(job_id)
    print('- Completed job', job_id)


if __name__ == "__main__":
    log.info('PROCESS: Initialization')
    config = read_config()
    log.info('PROCESS: Job started')
    main(config)
    log.info('PROCESS: Job completed')
