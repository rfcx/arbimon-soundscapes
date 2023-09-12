
from .logs import get_logger

log = get_logger()

def validate_config(config: dict) -> None:
    not_set_project = not 'project' in config

    if not_set_project:
        log.critical('Invalid configuration: project not set')
        exit(1)
