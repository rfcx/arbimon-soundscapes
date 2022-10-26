import sys
import yaml
from argparse import Namespace
from .logs import get_logger
from .read_config_from_yaml import read_config_from_yaml
from .read_config_from_env import read_config_from_env
from .read_config_from_args import read_config_from_args
from .validate_config import validate_job_config

log = get_logger()

def read_config(args: Namespace) -> dict:
    raw_config = _get_yaml_file(args)
    yaml_config = read_config_from_yaml(raw_config)
    env_config = read_config_from_env()
    args_config = read_config_from_args(args)

    config = {**yaml_config, **env_config, **args_config}
    for k, v in config.items():
        log.info(f'{k}: {v}')

    validate_job_config(config)

    return config

def _get_yaml_file(args: Namespace) -> dict:
    raw_config = {}
    if args.stdin:
        log.info('Read config from stdin')
        raw_config = yaml.load(sys.stdin, Loader=yaml.SafeLoader)
    elif args.config:
        raw_config = yaml.load(args.config, Loader=yaml.SafeLoader)

    return raw_config
