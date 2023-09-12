import os


def read_config_from_env() -> dict:
    config = {}

    if "PROJECT" in os.environ:
        config['project'] = os.getenv("PROJECT")

    if "SITES" in os.environ:
        config['sites'] = os.getenv("SITES")

    if "YEAR" in os.environ:
        config['year'] = int(os.getenv("YEAR"))

    if "SOUNDSCAPE_THRESHOLD" in os.environ:
        config['soundscape_threshold'] = float(os.getenv("SOUNDSCAPE_THRESHOLD"))

    return config
