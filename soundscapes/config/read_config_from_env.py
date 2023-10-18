import os


def read_config_from_env() -> dict:
    config = {}

    if "PROJECT" in os.environ:
        config['project'] = os.getenv("PROJECT")

    if "SITES" in os.environ:
        config['sites'] = os.getenv("SITES")

    if "YEAR" in os.environ:
        config['year'] = int(os.getenv("YEAR"))

    if "SOUNDSCAPE_BIN_SIZE" in os.environ:
        config['soundscape_bin_size'] = float(os.getenv("SOUNDSCAPE_BIN_SIZE"))

    if "SOUNDSCAPE_THRESHOLD" in os.environ:
        config['soundscape_threshold'] = float(os.getenv("SOUNDSCAPE_THRESHOLD"))

    if "SOUNDSCAPE_NORMALIZE" in os.environ:
        config['soundscape_normalize'] = float(os.getenv("SOUNDSCAPE_NORMALIZE"))

    return config
