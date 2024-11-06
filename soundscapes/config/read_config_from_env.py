import os


def read_config_from_env() -> dict:
    config = {}

    if "PROJECT" in os.environ:
        config['project'] = os.getenv("PROJECT")

    if "SITES" in os.environ:
        config['sites'] = os.getenv("SITES")

    if "YEAR" in os.environ:
        config['year'] = int(os.getenv("YEAR"))

    if "SOUNDSCAPE_AGGREGATION" in os.environ:
        config['soundscape_aggregation'] = os.getenv("SOUNDSCAPE_AGGREGATION")

    if "SOUNDSCAPE_BIN_SIZE" in os.environ:
        config['soundscape_bin_size'] = float(os.getenv("SOUNDSCAPE_BIN_SIZE"))

    if "SOUNDSCAPE_THRESHOLD" in os.environ:
        config['soundscape_threshold'] = float(os.getenv("SOUNDSCAPE_THRESHOLD"))

    if "SOUNDSCAPE_NORMALIZE" in os.environ:
        config['soundscape_normalize'] = float(os.getenv("SOUNDSCAPE_NORMALIZE"))

    if "PLAYLIST_ID" in os.environ:
        config['playlist_id'] = int(os.getenv("PLAYLIST_ID")) if os.getenv("PLAYLIST_ID") is not None else None

    if "JOB_NAME" in os.environ:
        config['job_name'] = os.getenv("JOB_NAME")
        
    if "CREATED_BY_USER_ID" in os.environ:
        config['created_by_user_id'] = int(os.getenv("CREATED_BY_USER_ID")) if os.getenv("CREATED_BY_USER_ID") is not None else None

    return config
