import argparse
from .config.logs import get_logger
from .config.read_config import read_config

log = get_logger()

def main(batch_config):
    log.info("PROCESS: Start")

    # Setup

    # Run job

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
