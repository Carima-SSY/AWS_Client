from lib import status_manager as sm
from lib import file_manager as fm
from lib import log_manager as lm
from lib import cam_manager as cam
from lib import aws
import json, time, datetime, threading, os, sys

class AWSClient: 
    def __init__(self, device_type, device_number, data_folder, recipe_folder, setting_folder, log_folder, history_folder, cam_folder, iotcore_endpoint, iotcore_clientid, iotcore_topic, iotcore_cacert, iotcore_certfile, iotcore_privatekey, apig_endpoint):
        self.iot_core = aws.ToIoTCore(endpoint=iotcore_endpoint, client_id=iotcore_clientid, topic=iotcore_topic, ca_cert=iotcore_cacert, cert_file=iotcore_certfile, private_key=iotcore_privatekey)
        self.iot_core.set_onmessage(self.iotcore_onmessage_handler)
        
        self.cam_core = aws.ToIoTCore(endpoint=iotcore_endpoint, client_id=f"{iotcore_clientid}-Cam", topic=f"{iotcore_topic}/Cam", ca_cert=iotcore_cacert, cert_file=iotcore_certfile, private_key=iotcore_privatekey)
        
        self.api_gateway = aws.ToAPIG(endpoint=apig_endpoint)

        self.client_status = sm.StatusManager(device_type=device_type, device_number=device_number, history_folder=history_folder)
        self.client_file = fm.FileManager(device_type=device_type, device_number=device_number, data_folder=data_folder, recipe_folder=recipe_folder, setting_folder=setting_folder, log_folder=log_folder, history_folder=history_folder, cam_folder=cam_folder)
        self.client_log = lm.LogManager(device_type=device_type, device_number=device_number, log_folder=log_folder)
        self.client_cam = cam.CamManager(camera_index=0, width=1280, height=720, fps=30, webp_quality=50, cam_folder=cam_folder)
        
    def request_file_transfer(self, ftype, fname, fcontent):
        if ftype == "data":
            self.client_file.add_print_data(name=fname, encoded_content=fcontent)
            return True
        elif ftype == "recipe":
            print("Recipe is Transfered")
            self.client_file.save_json_to_xml(folder=self.client_file.recipe_folder, file=fname, data=fcontent)
            return True
        else:
            return False

    def request_file_deletion(self, ftype, fname):
        if ftype == "data":
            self.client_file.delete_print_data(name=fname)
            return True
        elif ftype == "recipe":
            self.client_file.delete_print_recipe(name=fname)
            return True
        else:
            return False
        
    def request_add_printing(self, data):
        if self.client_status.device_type == "DM400":
            self.client_status.add_device_request({
                "type": "add-printing",
                "data": data
            })
        
    def request_change_printing(self, data):
        if self.client_status.device_type == "DM400":
            self.client_status.add_device_request({
                "type": "change-printing",
                "data": data
            })
            
    def request_delete_printing(self, data):
        if self.client_status.device_type == "DM400":
            self.client_status.add_device_request({
                "type": "delete-printing",
                "data": data
            })
        
    def request_print_start(self, user, data, recipe):
        self.client_status.add_device_request({
            "type": "print-start",
            "user": user,
            "data": data,
            "recipe": recipe
        })

    def request_print_abort(self):
        self.client_status.add_device_request({
            "type": "print-abort"
        })
        
    def request_print_pause(self):
        self.client_status.add_device_request({
            "type": "print-pause"
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
                self.client_file.save_json_to_xml(folder=self.client_file.setting_folder, file=name, data=content, root_name=None)
        elif self.client_file.device_type == "DM400":
            if type == "print-recipe":
                self.client_file.save_json_to_xml(folder=self.client_file.recipe_folder, file=name, data=content, root_name=None)
            elif type == "device-setting":  
                self.client_file.save_json_to_xml(folder=self.client_file.setting_folder, file=name, data=content, root_name=None)
        else: pass
        
    def iotcore_onmessage_handler(self, client, userdata, msg):
        topic = msg.topic
        message = dict(json.loads(msg.payload.decode()))
        # print (f"Message from {topic} is {message}")
        
        request = message.get("request")
        
        if request is None: 
            return 
        
        if request == "file-transfer":
            data = message.get("data")
            # url = self.api_gateway.get_presigned_url(method="get_object",key=data.get("key"))
            res = self.api_gateway.get_file_from_s3(get_url=data.get("url"))
            self.request_file_transfer(ftype=res.get("type"), fname=res.get("name"), fcontent=res.get("content"))
            
        elif request == "file-deletion":
            print("=========================================================\n=========================================================\nDEVICE REQUEST: FILE DELETE!!!!\n=========================================================\n=========================================================\n")
            message = dict(json.loads(msg.payload.decode()))
            print (f"Message from {topic} is {message}")
            data = message.get("data")
            self.request_file_deletion(ftype=data.get("type"), fname=data.get("name"))
            
        # elif request == "add-printing":
        #     # print("=========================================================\n=========================================================\nDEVICE REQUEST: ADD PRINTING!!!!\n=========================================================\n=========================================================\n")
        #     data = message.get("data")
        #     self.request_add_printing(data=data.get("data"))
        
        elif request == "change-printing":
            data = message.get("data")
            self.request_change_printing(data=data.get("data"))
        
        # elif request == "delete-printing":
        #     # print("=========================================================\n=========================================================\nDEVICE REQUEST: DELETE PRINTING!!!!\n=========================================================\n=========================================================\n")
        #     data = message.get("data")
        #     self.request_delete_printing(data=data.get("data"))
            
        elif request == "print-start":
            # print("=========================================================\n=========================================================\nDEVICE REQUEST: PRINT START!!!!\n=========================================================\n=========================================================\n")
            data = message.get("data")
            self.request_print_start(user=data.get("user"), data=data.get("data"), recipe=data.get("recipe"))
            
        elif request == "print-abort":
            # print("=========================================================\n=========================================================\nDEVICE REQUEST: PRINT ABORT!!!!\n=========================================================\n=========================================================\n")
            self.request_print_abort()
        
        elif request == "print-pause":
            # print("=========================================================\n=========================================================\nDEVICE REQUEST: PRINT PAUSE!!!!\n=========================================================\n=========================================================\n")
            self.request_print_pause()
        
        elif request == "select-data":
            # print("=========================================================\n=========================================================\nDEVICE REQUEST: SELECT DATA!!!!\n=========================================================\n=========================================================\n")
            data = message.get("data")
            self.request_select_file(type="select-data",name=data.get("data"))
        
        elif request == "select-recipe":
            # print("=========================================================\n=========================================================\nDEVICE REQUEST: SELECT RECIPE!!!!\n=========================================================\n=========================================================\n")
            data = message.get("data")
            self.request_select_file(type="select-recipe",name=data.get("recipe"))
        
        elif request == "change-recipe":
            # print("=========================================================\n=========================================================\nDEVICE REQUEST: CHANGE RECIPE!!!!\n=========================================================\n=========================================================\n")
            data = message.get("data")
            self.request_change_file(type="print-recipe", name=data.get("name"), content=data.get("content"))
            
        elif request == "change-setting":
            # print("=========================================================\n=========================================================\nDEVICE REQUEST: CHANGE SETTING!!!!\n=========================================================\n=========================================================\n")
            data = message.get("data")
            self.request_change_file(type="device-setting", name=data.get("name"), content=data.get("content"))
        
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
LOG_FOLDER = client_config["dir"]["log"]
HISTORY_FOLDER = client_config["dir"]["history"]
CAM_FOLDER = client_config["dir"]["cam"]

IOT_ENDPOINT = client_config["IoTCore"]["end_point"]       
CLIENT_ID = client_config["IoTCore"]["client_id"]  
TOPIC = f"Status/{DEVICE_TYPE}/{DEVICE_NUMBER}"
CA_CERT = client_config["IoTCore"]["ca_cert"]  
CERT_FILE = client_config["IoTCore"]["cert_file"]  
PRIVATE_KEY = client_config["IoTCore"]["private_key"]  

APIG_ENDPOINT = client_config["APIGateway"]["end_point"]  

CAPTURE_INTERVAL = 10
SAVE_INTERVAL = 1

def control_print_history(client_status: sm.StatusManager):
    if client_status.get_device_status()["status"] == "PRINTING":
        if os.path.exists(get_resource_path("print-history.json")) == False:
            client_status.create_print_history()
            current_history = client_status.get_print_history()
            current_history["name"] = f'{DEVICE_TYPE}-{DEVICE_NUMBER}-{int(time.time())}'
            current_history["database"]["user"] = client_status.get_print_status()["user"]
            current_history["database"]["print"]["data"] = client_status.get_print_status()["data"][client_status.get_print_status()["data-index"]]
            current_history["database"]["print"]["recipe"] = client_status.get_print_status()["recipe"]
            current_history["database"]["time"]["start"] = datetime.datetime.fromtimestamp(int(time.time())).strftime("%Y:%m:%d:%H:%M:%S")

            client_status.set_print_history(data=current_history)
        
        return False, None
    elif client_status.get_device_status()["status"] == "PRINTING_FINISH" or client_status.get_device_status()["status"] == "PRINTING_ABORT":
        if os.path.exists(get_resource_path("print-history.json")):
            current_history = client_status.get_print_history()
            if current_history["database"]["result"] == "-":
                current_history["database"]["result"] = client_status.get_device_status()["status"]
                current_history["database"]["time"]["end"] = datetime.datetime.fromtimestamp(int(time.time())).strftime("%Y:%m:%d:%H:%M:%S")

                with open(os.path.join(client_status.history_folder, f'{current_history["name"]}.json'), 'w', encoding='utf-8') as f:
                    json.dump(current_history, f, ensure_ascii=False, indent=4)
                    
                with open(os.path.join(client_status.history_folder, "print-history.json"), 'r', encoding='utf-8') as f:
                    print_history = json.load(f)
                    
                print_history['updated-list'].append(f'{current_history["name"]}.json')
                
                with open(os.path.join(client_status.history_folder, "print-history.json"), 'w', encoding='utf-8') as f:
                    json.dump(print_history, f, ensure_ascii=False, indent=4)
                    
                client_status.delete_print_history()
                
                return True, current_history
            else: return False, None
        else:
            return False, None
    else: 
        if os.path.exists(get_resource_path("print-history.json")):
            client_status.delete_print_history()
        return False, None

def captureimg_handler(apig_client: aws.ToAPIG, client_file: fm.FileManager, folder:str):
    try:
        if client_file.get_frame_count(folder=folder)[1] > 0:
            valid, zip_path = client_file.get_preview_zip(folder=folder)
            if valid == True:
                with open(zip_path, "rb") as zip_file:
                    zip_data = zip_file.read()
                apig_client.put_data_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="preview-zip", name=folder)["data"]["url"],
                    data=zip_data
                )
                print("Preview ZIP is processed Successfully.")
            else: 
                print("Preview ZIP is not available.")
                
                
            valid, video = client_file.get_timelapse_video(folder=folder)
            if valid == True:
                with open(video, "rb") as video_file:
                    video_data = video_file.read()
                result = apig_client.put_data_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="timelapse-video", name=folder)["data"]["url"],
                    data=video_data
                )
                if result == True:  
                    print(f"Timelapse video {folder} is processed Successfully.")
                else:
                    print(f"Timelapse video {folder} is processed Failed.")
            else: 
                print(f"Timelapse video for folder {folder} is not available.")
                
            client_file.clean_timelapse_frame(folder=folder)
    except Exception as e:
        print(f"Exception in captureimg_handler: {str(e)}")
        pass
        
def cam_handler(cam_client: aws.ToIoTCore, client_status: sm.StatusManager, client_cam: cam.CamManager):
    delay_time = CAPTURE_INTERVAL
    while True:
        try:
            if client_status.get_device_status()['status'] == "PRINTING" and client_status.get_print_history() is not None:
                if client_cam.exists_cam_folder(sub_folder=f"{client_status.get_print_history()['name']}") == False:
                    client_cam.create_sub_folder(sub_folder=f"{client_status.get_print_history()['name']}")
                encoded_image = client_cam.save_image(sub_folder=f"{client_status.get_print_history()['name']}")
                delay_time = SAVE_INTERVAL
                
            elif client_status.get_device_status()['status'] == "OFFLINE": 
                encoded_image = None
                delay_time = CAPTURE_INTERVAL
            
            else:
                encoded_image = client_cam.capture_image()
                delay_time = CAPTURE_INTERVAL

            cam_client.publish({
                    "target": ["browser"],
                    "action": "cam-image",
                    "device": {
                        "type": DEVICE_TYPE, 
                        "number": DEVICE_NUMBER
                    },
                    "data": {
                        "encoded": encoded_image
                    }
                    
                }
            )
            
            time.sleep(delay_time)
        except Exception as e:
            print(f"Exception in cam_handler: {str(e)}")
            pass

def status_handler(iot_client: aws.ToIoTCore, client_status: sm.StatusManager, client_log: lm.LogManager):
    count = 0
    
    current_devconfig = dict()

    file_path = client_log.create_log_file()
    log_count = 0
    while True:
        try:
            status_target = ["browser"]
                     
            if count >= 60: 
                status_target.append("storage")
                count = 0
            elif client_status.get_device_status()['status'] == "OFFLINE":
                status_target.append("storage")
                
            iot_client.publish({
                    "target": status_target,
                    "action": "all-status",
                    "device": {
                        "type": DEVICE_TYPE,
                        "number": DEVICE_NUMBER
                    },
                    "data": {
                        "device": client_status.get_device_status(),
                        "sensor": client_status.get_sensor_status(),
                        "print": client_status.get_print_status()
                    }
                }
            )
            
            valid, data = control_print_history(client_status=client_status)
            if valid == True:
                print(f"NEW PRINT HISTORY: {data}")
                iot_client.publish({
                        "target": ["browser", "storage"],
                        "action": "print-history",
                        "device": {
                            "type": DEVICE_TYPE,
                            "number": DEVICE_NUMBER
                        },
                        "data": {
                            "name": data["name"],
                            "info": data["database"]
                        }
                    }
                )
            
            if log_count < 3600:
                
                client_log.update_log_file(file=file_path,data={
                    "timestamp": int(time.time()),
                    "device": aws_client.client_status.get_device_status(),
                    "sensor": aws_client.client_status.get_sensor_status(),
                    "print": aws_client.client_status.get_print_status()
                })    
                log_count += 1        
            else:  
                log_count = 0
                print("=========================================================\n=========================================================\nDEVICE LOG: SAVE AND UPDATE!!!!\n=========================================================\n=========================================================\n")
                client_log.save_log_file(file=file_path)
                file_path = client_log.create_log_file()
                client_log.update_log_file(file=file_path,data={
                    "timestamp": int(time.time()),
                    "device": client_status.get_device_status(),
                    "sensor": client_status.get_sensor_status(),
                    "print": client_status.get_print_status()
                })
                # log_count = 0
            
            if client_status.get_device_alarm()["subject"] != "-":
                iot_client.publish({
                        "target": ["browser", "storage"],
                        "action": "device-alarm",
                        "device": {
                            "type": DEVICE_TYPE,
                            "number": DEVICE_NUMBER
                        },
                        "data": client_status.get_device_alarm() 
                    }
                )
                
                client_status.set_device_alarm(client_status.device_alarm)
                
            if current_devconfig != client_status.get_device_config():
                current_devconfig = client_status.get_device_config()
                iot_client.publish({
                        "target": ["browser", "storage"],
                        "action": "device-config",
                        "device": {
                            "type": DEVICE_TYPE,
                            "number": DEVICE_NUMBER
                        },
                        "data": client_status.get_device_config() 
                    }
                )    
            
            time.sleep(1)
            
            count += 1
        except Exception as e:
            print(f"Exception in status_handler: {str(e)}")
            pass

def file_handler(apig_client: aws.ToAPIG, client_file: fm.FileManager):
    
    while True:
        try:
            # Get Print Data
            # print("=========================================================\n=========================================================\nCheck Data and Recipe!!!!\n=========================================================\n=========================================================\n")
            current_data = client_file.get_print_data()
            if client_file.print_data != current_data and current_data is not None:
                client_file.print_data = current_data
                # print("=========================================================\n=========================================================\nPrint Data Updated!!!!\n=========================================================\n=========================================================\n")
                apig_client.put_file_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="print-data")["data"]["url"], 
                    data=client_file.print_data
                )

            # Get Print Recipe
            valid,current_recipe = client_file.get_print_recipe()
            if client_file.print_recipe != current_recipe and valid == True:
                client_file.print_recipe = current_recipe
                # print(f"CURRENT PRINT RECIPE: {client_file.print_recipe}")
                # print("=========================================================\n=========================================================\nPrint Recipe Updated!!!!\n=========================================================\n=========================================================\n")
                apig_client.put_file_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="print-recipe")["data"]["url"],
                    data=client_file.print_recipe
                )
                
            current_setting = client_file.get_device_setting()[1]
            if client_file.device_setting != current_setting:
                client_file.device_setting = current_setting
                # print(f"CURRENT DEVICE SETTING: {client_file.device_setting}")
                # print("=========================================================\n=========================================================\nDEVICE SETTING Updated!!!!\n=========================================================\n=========================================================\n")
                apig_client.put_file_to_s3(
                    put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="device-setting")["data"]["url"],
                    data=client_file.device_setting
                )
                
            valid, current_logs = client_file.get_device_log_updatelist()
            if valid == True:
                for current_log in current_logs:
                    valid, updated_log = client_file.get_device_log(current_log)
                    # print(f"CURRENT DEVICE LOG: {updated_log}")
                    # print("=========================================================\n=========================================================\nDEVICE LOG Updated!!!!\n=========================================================\n=========================================================\n")
                    if valid == True:
                        print(f"CURRENT DEVICE LOG: {updated_log}")
                        apig_client.put_file_to_s3(
                            put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="device-log", name=str(current_log).split('.')[0])["data"]["url"],
                            data=updated_log
                        )
                client_file.reset_device_log_updatelist()
                
            valid, current_historys = client_file.get_print_history_updatelist()
            if valid == True:
                for current_history in current_historys:
                    #print(f"CURRENT HISTORY: {current_history}")
                    _, updated_history =client_file.get_print_history(current_history)
                    
                    #print(f"UPDATED HISTORY: {updated_history}")
                    apig_client.put_file_to_s3(
                        put_url=apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data="print-history", name=updated_history["name"])["data"]["url"],
                        data=updated_history["storage"]
                    )
                    threading.Thread(target=captureimg_handler, args=(apig_client, client_file, updated_history["name"])).start()
                    
                client_file.reset_print_history_updatelist()
            
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
            log_folder=LOG_FOLDER,
            history_folder=HISTORY_FOLDER,
            cam_folder=CAM_FOLDER,
            iotcore_endpoint=IOT_ENDPOINT,
            iotcore_topic=TOPIC,
            iotcore_clientid=CLIENT_ID,  
            iotcore_cacert=CA_CERT,
            iotcore_certfile=CERT_FILE,
            iotcore_privatekey=PRIVATE_KEY,
            apig_endpoint=APIG_ENDPOINT
        )
        aws_client.iot_core.connect()
        aws_client.cam_core.connect()   
        
        status_thread = threading.Thread(target=status_handler, args=(aws_client.iot_core, aws_client.client_status, aws_client.client_log))
        file_thread = threading.Thread(target=file_handler, args=(aws_client.api_gateway, aws_client.client_file))
        cam_thread = threading.Thread(target=cam_handler, args=(aws_client.cam_core, aws_client.client_status, aws_client.client_cam))
        
        status_thread.start()
        file_thread.start()
        cam_thread.start()
        
        status_thread.join()
        file_thread.join()
        cam_thread.join()

    finally:
        aws_client.iot_core.disconnect()
        aws_client.client_status.delete_json_file()
        aws_client.cam_core.disconnect()