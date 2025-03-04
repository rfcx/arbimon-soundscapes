from .config.logs import get_logger
from .config.read_config import read_config
from .old.playlist_to_soundscape import playlist_to_soundscape

log = get_logger()

def main(config):
    job_id = config['job_id']
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
