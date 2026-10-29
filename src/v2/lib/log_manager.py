import time, os
from . import json_file

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
        json_file.write_json(os.path.join(self.log_folder, filename), empty_dic)
            
        return os.path.join(self.log_folder, filename)
    
    def update_log_file(self, file, data):
        with json_file.lock(file):
            current_data = json_file.read_json(file)

            if "data" in current_data and isinstance(current_data["data"], list):
                current_data["data"].append(data)
            else: return False

            json_file.write_json(file, current_data)

    def save_log_file(self, file: str):
        # upload_handler(file_manager.reset_device_log_updatelist)와 같은 Lock 안에서 읽고-고쳐-쓴다
        json_file.update_json(
            os.path.join(self.log_folder, "device-log.json"),
            lambda device_log: device_log["updated-list"].append(os.path.basename(file)),
        )