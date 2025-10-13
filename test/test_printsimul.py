import json, time


def read_json(file: str):
    with open(file, 'r', encoding='utf-8') as content:
        json_content = json.load(content) 
    return json_content 

def write_json(file: str, data: dict):
    with open(file, 'w', encoding='utf-8') as content:
        json.dump(data, content, ensure_ascii=False, indent=4)
    return True

write_json(file='../device-status.json',data={
    "allow-remote-control": 0,
    "status": "PRINTING",
    "selected":{
        "data": ["test.crmaslice"],
        "recipe": "sample.xml"
    }
})

write_json(file='../print-status.json',data={
    "user": "on-device",
    "data-index": 0,
    "data": ["test.crmaslice"],
    "recipe": "sample.xml",
    "current-layer": 0,
    "total-layer": 0,
    "remaining-time": 0,
    "progress": 0
})

time.sleep(10)

write_json(file='../device-status.json',data={
    "allow-remote-control": 0,
    "status": "PRINTING_FINISH",
    "selected":{
        "data": ["test.crmaslice"],
        "recipe": "sample.xml"
    }
})


time.sleep(3)

write_json(file='../device-status.json',data={
    "allow-remote-control": 0,
    "status": "IDLE",
    "selected":{
        "data": [],
        "recipe": "-"
    }
})
write_json(file='../print-status.json',data={
    "user": "-",
    "data-index": -1,
    "data": [],
    "recipe": "-",
    "current-layer": 0,
    "total-layer": 0,
    "remaining-time": 0,
    "progress": 0
})
print("TEST END!!!")