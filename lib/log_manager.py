import json,time, os

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

    def save_log_file(self, file: str):
        with open(f"{self.log_folder}/device-log.json", 'r', encoding='utf-8') as f:
            device_log = json.load(f)
            
        device_log["updated-list"].append(os.path.basename(file))

        with open(f"{self.log_folder}/device-log.json", 'w', encoding='utf-8') as f:
            json.dump(device_log, f, ensure_ascii=False, indent=4)