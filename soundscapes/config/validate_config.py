import os

from .logs import get_logger

log = get_logger()

def validate_job_config(config: dict) -> None:
    not_set_classifier = not 'sou' in config and not 'classifier_path'in config

    expected_cloud_keys = ['project', 'sites', 'date_start', 'date_end', 'hours']
    not_set_source = not 'source_path' in config and all(item not in expected_cloud_keys for item in config.keys())

    not_set_classifier_for_cloud_output = 'classifier_id' not in config and 'destination' in config

    # if not_set_classifier or not_set_source or not_set_classifier_for_cloud_output:
    #     log.critical('Invalid batch configuration')
    #     exit(1)
