import csv
import json

csv_file = 'products.csv'
json_file = 'products.json'

data = []

with open(csv_file, mode='r', encoding='utf-8') as file:
    csv_reader = csv.DictReader(file)
    
    for row in csv_reader:
        data.append(row)

with open(json_file, mode='w', encoding='utf-8') as file:
    json.dump(data, file, indent=4)

print("✅ CSV converted to JSON successfully!")
