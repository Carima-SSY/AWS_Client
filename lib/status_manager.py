import json
import sys
import os
from . import status as st
class StatusManager:
    def __init__(self, device_type, device_number):
        self.device_type = device_type
        self.device_number = device_number
        
        self.print_status = st.PRINT_STATUS
        self.device_status = st.DEVICE_STATUS
        self.sensor_status = st.SENSOR_STATUS
        self.device_alarm = st.DEVICE_ALARM
        self.device_config = st.DEVICE_CONFIG
        self.device_request = st.DEVICE_REQUEST
        
        self.create_json_file()
        
    def get_resource_path(self, relative_path: str):
        if getattr(sys, 'frozen', False):
            # PyInstaller EXE
            base_path = os.path.dirname(sys.executable)
        else:
            # DEVELOP
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def get_json_content(self, file: str):
        with open(self.get_resource_path(file), 'r', encoding='utf-8') as content:
            json_content = json.load(content) 
        return json_content 
    
    def set_json_content(self, file: str, data: dict):
        with open(self.get_resource_path(file), 'w', encoding='utf-8') as content:
            json.dump(data, content, ensure_ascii=False, indent=4)
        return True
    
    def create_json_file(self):
        self.set_json_content('print-status.json', self.print_status)
        self.set_json_content('device-status.json', self.device_status)
        self.set_json_content('sensor-status.json', self.sensor_status)
        self.set_json_content('device-alarm.json', self.device_alarm)
        self.set_json_content('device-config.json', self.device_config)
        self.set_json_content('device-request.json', self.device_request)
        
    def delete_json_file(self):
        os.remove(self.get_resource_path('print-status.json'))
        os.remove(self.get_resource_path('device-status.json'))
        os.remove(self.get_resource_path('sensor-status.json'))
        os.remove(self.get_resource_path('device-alarm.json'))
        os.remove(self.get_resource_path("device-config.json"))
        os.remove(self.get_resource_path("device-request.json"))
        
    def get_device_status(self):
        return self.get_json_content(self.get_resource_path('device-status.json'))

    def get_print_status(self):
        return self.get_json_content(self.get_resource_path('print-status.json'))
    
    def get_sensor_status(self):
        return self.get_json_content(self.get_resource_path('sensor-status.json'))
    
    def get_device_alarm(self):
        return self.get_json_content(self.get_resource_path('device-alarm.json'))
    
    def set_device_status(self, data):
        self.set_json_content(self.get_resource_path('device-status.json'), data)
    
    def set_print_status(self, data):
        self.set_json_content(self.get_resource_path('print-status.json'), data)
    
    def set_sensor_status(self, data):
        self.set_json_content(self.get_resource_path('sensor-status.json'), data)
    
    def set_device_alarm(self, data):
        self.set_json_content(self.get_resource_path('device-alarm.json'), data)
        
    def add_device_request(self, data):
        with open(self.get_resource_path("device-request.json"), 'r', encoding='utf-8') as file:
                requestlist_dic = json.load(file)
                
        requestlist_dic["request-list"].append(data)
        
        with open(self.get_resource_path("device-request.json"), 'w', encoding='utf-8') as file:
            json.dump(requestlist_dic, file, indent=4, ensure_ascii=False)