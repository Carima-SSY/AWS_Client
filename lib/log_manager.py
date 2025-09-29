import json,time
SENSOR_STATUS = {
    "control_board": {
        "connected": 0,
        "build-platform": -1,
        "level-tank": -1,
        "blade": -1,
        "print-blade": -1,
        "collect-blade": -1,
        "resin-pump": -1,
        "pneumatic-pump": -1,
        "autoleveling": 0
    },
    "temperature": {
        "connected": 0,
        "current": -1,
        "target": -1,
        "heating": 0
    },
    "waterlevel": {
        "connected": 0,
        "current": -1,
        "target": -1
    },
    "pressure":{
        "connected": 0,
        "current": -1,
        "target": -1
    },
    "engine": {
        "connected": 0,
        "ledon": 0,
        "ledtemp": {
            "left": -1,
            "right": -1,
            "one": -1
        }
    }
}

PRINT_STATUS = {
    "data-index": -1,
    "data": [],
    "recipe": "-",
    "current-layer": 0,
    "total-layer": 0,
    "remaining-time": 0,
    "progress": 0
}

DEVICE_STATUS = {
    "allow-remote-control": 0,
    "status": "OFFLINE",
    "selected":{
        "data": [],
        "recipe": "-"
    }
}

class LogManager:
    def __init__(self, device_type, device_number, log_folder):
        self.device_type = device_type
        self.device_number = device_number
        self.log_folder = log_folder
    
    def create_log_file(self):
        filename = f"{self.device_type}-{self.device_number}-{int(time.time())}.json"
        empty_dic = {
            "device":{
                "type": self.device_type,
                "number": self.device_number
            },
            "data": list()
        }
        with open(f"{self.log_folder}/{filename}", 'w', encoding='utf-8') as log_file:
            json.dump(empty_dic, log_file, indent=4) 
            
        return f"{self.log_folder}/{filename}"
    
    def update_log_file(self, file, data):
        current_data = {}
        with open(file, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
            
        if "data" in current_data and isinstance(current_data["data"], list):
            current_data["data"].append(data)
        else: return False

        with open(file, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, ensure_ascii=False, indent=4)
    
if __name__ == "__main__":
    lm = LogManager(device_type="DM400", device_number="888888", log_folder="/Users/carima/Documents/Programming/GitConn/AWS_Client")
    log_file = lm.create_log_file()
    
    for i in range(360):
        lm.update_log_file(file=log_file, data={"device": DEVICE_STATUS, "sensor": SENSOR_STATUS, "print": PRINT_STATUS})