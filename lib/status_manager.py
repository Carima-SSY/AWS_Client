import json
import sys
import os
import status as st

class StatusManager:
    def __init__(self, device_type, device_number):
        self.device_type = device_type
        self.device_number = device_number
        
        self.print_status = st.PRINT_STATUS
        self.device_status = st.DEVICE_STATUS
        self.sensor_status = st.SENSOR_STATUS
        self.device_alarm = st.DEVICE_ALARM
        self.device_config = st.DEVICE_CONFIG

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
        self.put_json_content('print-status.json', self.print_status)
        self.put_json_content('device-status.json', self.device_status)
        self.put_json_content('sensor-status.json', self.sensor_status)
        self.put_json_content('device-alarm.json', self.device_alarm)
        self.put_json_content('device-config.json', self.device_config)
        
    def delete_json_file(self):
        os.remove('print-status.json')
        os.remove('device-status.json')
        os.remove('sensor-status.json')
        os.remove('device-alarm.json')
        os.remove('device-config.json')
        
    def get_device_status(self):
        return self.get_json_content('device-status.json')

    def get_print_status(self):
        return self.get_json_content('print-status.json')
    
    def get_sensor_status(self):
        return self.get_json_content('sensor-status.json')
    
    def get_device_alarm(self):
        return self.get_json_content('device-alarm.json')
    
    def set_device_status(self, data):
        self.set_json_content('device-status.json', data)
    
    def set_print_status(self, data):
        self.set_json_content('print-status.json', data)
    
    def set_sensor_status(self, data):
        self.set_json_content('sensor-status.json', data)
    
    def set_device_alarm(self, data):
        self.set_json_content('device-alarm.json', data)