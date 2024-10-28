
from .logs import get_logger

log = get_logger()

def validate_config(config: dict) -> None:
    not_set_project = 'project' not in config
    not_set_playlist_id = 'playlist_id' not in config

    if not_set_project or not_set_playlist_id:
        log.critical('Invalid configuration: project not set or playlist_id not set')
        exit(1)
