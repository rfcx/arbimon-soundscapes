
def read_config_from_yaml(yaml: dict) -> dict:
    config = {}

    if 'classifier' in yaml:
        # Cloud
        if 'id' in yaml['classifier']:
            config['classifier_id'] = yaml['classifier']['id']
        # Local
        if 'path' in yaml['classifier']:
            config['classifier_path'] = yaml['classifier']['path']
        if 'parameters' in yaml['classifier']:
            parameters = yaml['classifier']['parameters']
            config['parameters'] = {}
            config['parameters']['step_seconds'] = parameters['step_seconds'] if 'step_seconds' in parameters else 1

    if 'source' in yaml:
        # Cloud
        config['project'] = yaml['source']['project'] if 'project' in yaml['source'] else None
        config['sites'] = yaml['source']['sites'] if 'sites' in yaml['source'] else None
        if 'date_start' in yaml['source']:
            config['date_start'] = yaml['source']['date_start']
        if 'date_end' in yaml['source']:
            config['date_end'] = yaml['source']['date_end']
        if 'hours' in yaml['source']:
            config['hours'] = yaml['source']['hours']
        # Local
        if 'path' in yaml['source']:
            config['source_path'] = yaml['source']['path']

    if 'output' in yaml:
        output_mode = yaml['output']['mode']
        config['output_mode'] = output_mode
        if 'local_path' in yaml['output']:
            config['output_local_path'] = yaml['output']['local_path']

    return config
