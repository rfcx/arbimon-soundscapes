from array import array
import csv
import json

aggregations = {
    'time_of_day': {
        'date': ['%H'], 'projection': [1], 'range': [0,  23]
    },
    'day_of_month': {
        'date': ['%d'], 'projection': [1], 'range': [1,  31]
    },
    'day_of_year': {
        'date': ['%j'], 'projection': [1], 'range': [1, 366]
    },
    'month_in_year': {
        'date': ['%m'], 'projection': [1], 'range': [1,  12]
    },
    'day_of_week': {
        'date': ['%w'], 'projection': [1], 'range': [0,   6]
    },
    'year': {
        'date': ['%Y'], 'projection': [1], 'range': 'auto'
    }
}


class Indices():
    def __init__(self, aggregation):
        "Constructs index object"
        self.aggregation = aggregation
        self.values = {}
        self.indexVector = None
        starti = aggregation['range'][0]
        endi =  aggregation['range'][1]
        for i in range(starti,endi+1):
            self.values[i] = []
        self.aggregated = False
        
    def insert_value(self, date, value, rec_id):
        idx = int(sum([
            float(date.strftime(x)) * y for (x, y) in
            zip(self.aggregation['date'], self.aggregation['projection'])
        ]))
        self.values[idx].append({"red_id":rec_id,"value":value})
        
    def aggregate(self):
        starti = self.aggregation['range'][0]
        endi =  self.aggregation['range'][1]
        self.indexVector = []
        for i in range(starti,endi+1):
            current_values = self.values[i]
            if len(current_values) > 0 :
                accum = 0.0
                for j in range(len(current_values)):
                    accum = accum + float(current_values[j]['value'])
                accum = accum/float(len(current_values))
                self.indexVector.append(accum)
            else:
                self.indexVector.append(0.0)
    
    def write_index_aggregation(self,filename):          
        if not self.aggregated:
            self.aggregate()
        output_file = open(filename, 'wb')
        float_array = array('d', self.indexVector)
        float_array.tofile(output_file)
        output_file.close()
        
    def write_index_aggregation_csv(self,filename):          
        if not self.aggregated:
            self.aggregate()
        with open(filename, 'wb') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=',')
            spamwriter.writerow(self.indexVector)

    def write_index_aggregation_json(self,filename):          
        if not self.aggregated:
            self.aggregate()
        with open(filename, 'w') as outfile:
            json.dump(self.indexVector, outfile)
