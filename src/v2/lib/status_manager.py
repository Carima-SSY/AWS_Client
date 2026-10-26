import json
import sys
import os
from . import status as st
from . import json_file
class StatusManager:
    def __init__(self, device_type, device_number, history_folder):
        self.device_type = device_type
        self.device_number = device_number
        
        self.print_status = st.PRINT_STATUS
        self.device_status = st.DEVICE_STATUS
        self.sensor_status = st.SENSOR_STATUS
        self.device_alarm = st.DEVICE_ALARM
        self.device_config = st.DEVICE_CONFIG
        self.device_request = st.DEVICE_REQUEST
        self.print_history = st.PRINT_HISTORY
        
        self.history_folder = history_folder
        
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
        try: 
            return json_file.read_json(self.get_resource_path(file))
        except Exception as e:
            print(f"Exception in get_json_content ->{file}: {e}")
            return None
    
    def set_json_content(self, file: str, data: dict):
        try:
            json_file.write_json(self.get_resource_path(file), data)
            return True
        except Exception as e:
            print(f"Exception in set_json_content ->{file}: {e}")
            return False
    
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
        if os.path.exists(self.get_resource_path("print-history.json")):
            os.remove(self.get_resource_path("print-history.json"))
        
    def get_device_status(self):
        return self.get_json_content(self.get_resource_path('device-status.json'))

    def get_print_status(self):
        return self.get_json_content(self.get_resource_path('print-status.json'))
    
    def get_sensor_status(self):
        return self.get_json_content(self.get_resource_path('sensor-status.json'))
    
    def get_device_alarm(self):
        return self.get_json_content(self.get_resource_path('device-alarm.json'))
    
    def get_device_config(self):
        return self.get_json_content(self.get_resource_path('device-config.json'))
    
    def set_device_status(self, data):
        self.set_json_content(self.get_resource_path('device-status.json'), data)
    
    def set_print_status(self, data):
        self.set_json_content(self.get_resource_path('print-status.json'), data)
    
    def set_sensor_status(self, data):
        self.set_json_content(self.get_resource_path('sensor-status.json'), data)
    
    def set_device_alarm(self, data):
        self.set_json_content(self.get_resource_path('device-alarm.json'), data)
           
    def create_print_history(self):
        self.set_json_content('print-history.json', self.print_history)
        
    def get_print_history(self):
        return self.get_json_content(self.get_resource_path('print-history.json'))
    
    def set_print_history(self, data):
        self.set_json_content('print-history.json', data)
        
    def delete_print_history(self):
        if os.path.exists(self.get_resource_path("print-history.json")):
            os.remove(self.get_resource_path("print-history.json"))
        
    def add_device_request(self, data):
        json_file.update_json(
            self.get_resource_path("device-request.json"),
            lambda requestlist_dic: requestlist_dic["request-list"].append(data),
        )  