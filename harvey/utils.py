import json
import yaml 

def load_json(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        text = json.load(f)
    return text 

def loads_prompt(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        text = yaml.safe_load(f)
    return text 