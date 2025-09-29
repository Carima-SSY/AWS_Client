from lib import status_manager as sm
from lib import file_manager as fm
from lib import aws 
import json, time, threading, os, sys

class AWSClient: 
    def __init__(self, device_type, device_number, data_folder, recipe_folder, setting_folder, iotcore_endpoint, iotcore_clientid, iotcore_topic, iotcore_cacert, iotcore_certfile, iotcore_privatekey, apig_endpoint):
        self.iot_core = aws.ToIoTCore(endpoint=iotcore_endpoint, client_id=iotcore_clientid, topic=iotcore_topic, ca_cert=iotcore_cacert, cert_file=iotcore_certfile, private_key=iotcore_privatekey)
        self.iot_core.set_onmessage(self.iotcore_onmessage_handler)
        
        self.api_gateway = aws.ToAPIG(endpoint=apig_endpoint)

        self.client_status = sm.StatusManager(device_type=device_type, device_number=device_number)
        self.client_file = fm.FileManager(device_type=device_type, device_number=device_number, data_folder=data_folder, recipe_folder=recipe_folder, setting_folder=setting_folder)
        
    def request_file_transfer(self, ftype, fname, fcontent):
        if ftype == "data":
            self.client_file.add_print_data(name=fname, encoded_content=fcontent)
            return True
        elif ftype == "recipe":
            self.client_file.add_print_recipe(name=fname, encoded_content=fcontent)
            return True
        else:
            return False

    def request_print_start(self, data, recipe):
        self.client_status.add_device_request({
            "type": "print-start",
            "data": data,
            "recipe": recipe
        })

    def request_print_abort(self):
        self.client_status.add_device_request({
            "type": "print-abort"
        })

    def request_select_file(self, type, name):
        self.client_status.add_device_request({
            "type": type,
            "name": name
        })
        
    def request_change_file(self, type, name, content):
        if self.client_file.device_type == "X1" or self.client_file.device_type == "DM400":
            if type == "print-recipe":
                self.client_file.save_json_to_xml(folder=self.client_file.recipe_folder, file=name, data=content, root_name=None)
            elif type == "device-setting":
                pass
        else: pass
    def iotcore_onmessage_handler(self, client, userdata, msg):
        topic = msg.topic
        message = dict(json.loads(msg.payload.decode()))
        print (f"Message from {topic} is {message}")
        
        request = message.get("request")
        
        if request is None: 
            return 
        
        if request == "file-transfer":
            data = message.get("data")
            url = self.api_gateway.get_presigned_url(method="get_object",key=data.get("key"))
            res = self.api_gateway.get_file_from_s3(url=url)
            self.request_file_transfer(ftype=res.get("type"), fname=res.get("name"), fcontent=res.get("content"))
            
        elif request == "print-start":
            data = message.get("data")
            self.request_print_start(data=data.get("data"), recipe=data.get("recipe"))
            
        elif request == "print-abort":
            self.request_print_abort()
        
        elif request == "select-data":
            print("=========================================================\n=========================================================\nDEVICE REQUEST: SELECT DATA!!!!\n=========================================================\n=========================================================\n")
            data = message.get("data")
            self.request_select_file(type="select-data",name=data.get("data"))
        
        elif request == "select-recipe":
            data = message.get("data")
            self.request_select_file(type="select-recipe",name=data.get("recipe"))
        
        elif request == "change-recipe":
            pass
        
        elif request == "change-setting":
            pass
        
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        # PyInstaller EXE
        base_path = os.path.dirname(sys.executable)
    else:
        # DEVELOP
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_client_config():
    with open(get_resource_path('client-config.json'), 'r', encoding='utf-8') as file:
        config_content = json.load(file) 
    return config_content 

client_config = get_client_config()

DEVICE_TYPE = client_config["device"]["type"]
DEVICE_NUMBER = client_config["device"]["number"]

DATA_FOLDER = client_config["dir"]["data"]
RECIPE_FOLDER = client_config["dir"]["recipe"]
SETTING_FOLDER = client_config["dir"]["setting"]

IOT_ENDPOINT = client_config["IoTCore"]["end_point"]       
CLIENT_ID = client_config["IoTCore"]["client_id"]  
TOPIC = f"Status/{DEVICE_TYPE}/{DEVICE_NUMBER}"
CA_CERT = client_config["IoTCore"]["ca_cert"]  
CERT_FILE = client_config["IoTCore"]["cert_file"]  
PRIVATE_KEY = client_config["IoTCore"]["private_key"]  

APIG_ENDPOINT = client_config["APIGateway"]["end_point"]  


def status_handler(iot_client: aws.ToIoTCore, client_status: sm.StatusManager):
    count = 0
    current_devconfig = dict()
    while True:
        try:
            status_target = ["browser"]
            if count >= 60: 
                status_target.append("storage")
                count = 0
                
            iot_client.publish({
                    "target": status_target,
                    "action": "all-status",
                    "device": {
                        "type": DEVICE_TYPE,
                        "number": DEVICE_NUMBER
                    },
                    "data": {
                        "device": aws_client.client_status.get_device_status(),
                        "sensor": aws_client.client_status.get_sensor_status(),
                        "print": aws_client.client_status.get_print_status()
                    }
                }
            )
            
            if client_status.get_device_alarm()["subject"] != "-":
                iot_client.publish({
                        "target": ["browser", "storage"],
                        "action": "device-alarm",
                        "device": {
                            "type": DEVICE_TYPE,
                            "number": DEVICE_NUMBER
                        },
                        "data": aws_client.client_status.get_device_alarm() 
                    }
                )
                
                client_status.set_device_alarm({
                        "subject": "-",
                        "content": "-",
                        "created_date": "0000:00:00:00:00:00"
                    }
                )
            if current_devconfig != client_status.get_device_config():
                current_devconfig = client_status.get_device_config()
                iot_client.publish({
                        "target": ["browser", "storage"],
                        "action": "device-config",
                        "device": {
                            "type": DEVICE_TYPE,
                            "number": DEVICE_NUMBER
                        },
                        "data": aws_client.client_status.get_device_config() 
                    }
                )    
            time.sleep(1)
            count += 1
        except Exception as e:
            print(f"Exception in status_handler: {str(e)}")
            

def file_handler(apig_client: aws.ToAPIG, client_file: fm.FileManager):
    while True:
        try:
            # Get Print Data
            print("=========================================================\n=========================================================\nCheck Data and Recipe!!!!\n=========================================================\n=========================================================\n")
            current_data = client_file.get_print_data()
            if client_file.print_data != current_data:
                client_file.print_data = current_data
                print("=========================================================\n=========================================================\nPrint Data Updated!!!!\n=========================================================\n=========================================================\n")
                apig_client.put_file_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="print-data")["data"]["url"], 
                    data=client_file.print_data
                )

            # Get Print Recipe
            current_recipe = client_file.get_print_recipe()[1]
            if client_file.print_recipe != current_recipe:
                client_file.print_recipe = current_recipe
                print(f"CURRENT PRINT RECIPE: {client_file.print_recipe}")
                print("=========================================================\n=========================================================\nPrint Recipe Updated!!!!\n=========================================================\n=========================================================\n")
                apig_client.put_file_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="print-recipe")["data"]["url"],
                    data=client_file.print_recipe
                )

            current_setting = client_file.get_device_setting()[1]
            if client_file.device_setting != current_setting:
                client_file.device_setting = current_setting
                print(f"CURRENT DEVICE SETTING: {client_file.device_setting}")
                print("=========================================================\n=========================================================\nDEVICE SETTING Updated!!!!\n=========================================================\n=========================================================\n")
                apig_client.put_file_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="device-setting")["data"]["url"],
                    data=client_file.device_setting
                )
            
            
            time.sleep(1)
        except Exception as e:
            print(f"Exception in file_handler: {str(e)}")
    
if __name__ == "__main__":
    aws_client = None
    try: 
        aws_client = AWSClient(
            device_type=DEVICE_TYPE,
            device_number=DEVICE_NUMBER,
            data_folder=DATA_FOLDER,
            recipe_folder=RECIPE_FOLDER,
            setting_folder=SETTING_FOLDER,
            iotcore_endpoint=IOT_ENDPOINT,
            iotcore_topic=TOPIC,
            iotcore_clientid=CLIENT_ID,  
            iotcore_cacert=CA_CERT,
            iotcore_certfile=CERT_FILE,
            iotcore_privatekey=PRIVATE_KEY,
            apig_endpoint=APIG_ENDPOINT
        )
        aws_client.iot_core.connect()

        status_thread = threading.Thread(target=status_handler, args=(aws_client.iot_core, aws_client.client_status))
        file_thread = threading.Thread(target=file_handler, args=(aws_client.api_gateway, aws_client.client_file))
        
        status_thread.start()
        file_thread.start()
        
        status_thread.join()
        file_thread.join()
    finally:
        aws_client.iot_core.disconnect()
        aws_client.client_status.delete_json_file()
