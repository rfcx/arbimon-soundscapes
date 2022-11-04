
def get_norm_vector(timestamps, aggregation):
    norm_vector = {}
    for timestamp in timestamps:
        bin = sum([ int(timestamp.strftime(aggregation['date'][i])) * p for i, p in enumerate(aggregation['projection']) ])
        if bin in norm_vector:
            norm_vector[bin] = norm_vector[bin] + 1
        else:
            norm_vector[bin] = 1
    return norm_vector
