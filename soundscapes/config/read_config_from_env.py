import os


def read_config_from_env() -> dict:
    config = {}

    if "JOB_ID" in os.environ:
        config['job_id'] = int(os.getenv("JOB_ID"))

    if "CLASSIFIER_ID" in os.environ:
        config['classifier_id'] = int(os.getenv("CLASSIFIER_ID"))

    if "CLASSIFIER_PATH" in os.environ:
        config['classifier_path'] = os.getenv("CLASSIFIER_PATH")

    if "STEP_SECONDS" in os.environ:
        config['parameters'] = {}
        config['parameters']['step_seconds'] = float(os.getenv("STEP_SECONDS"))

    if "PROJECT" in os.environ:
        config['project'] = os.getenv("PROJECT")

    if "SITES" in os.environ:
        config['sites'] = os.getenv("SITES").split(",") if os.getenv("SITES") else None

    if "DATE_START" in os.environ:
        config['date_start'] = os.getenv("DATE_START")

    if "DATE_END" in os.environ:
        config['date_end'] = os.getenv("DATE_END")

    if "HOURS" in os.environ:
        config['hours'] = os.getenv("HOURS") if os.getenv("HOURS") else '0-23'

    if "SOURCE_PATH" in os.environ:
        config['source_path'] = os.getenv("SOURCE_PATH")

    if "OUTPUT_MODE" in os.environ:
        config['output_mode'] = os.getenv("OUTPUT_MODE")

    if "OUTPUT_LOCAL_PATH" in os.environ:
        config['output_local_path'] = os.getenv("OUTPUT_LOCAL_PATH")

    return config
