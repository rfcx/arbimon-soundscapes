import argparse
from .config.logs import get_logger
from .new.process import process

log = get_logger()

def main():
    log.info("PROCESS: Start")

    projects = ['zy5jbxx4cs9f', '6db1us3z9w7x']
    limit = 10

    # Run job
    for project in projects:
        number_processed = process(project, limit)
        if number_processed >= limit:
            log.info('Limit reached')
            break
        limit = limit - number_processed

    log.info("PROCESS: End")


if __name__ == "__main__":
    main()
