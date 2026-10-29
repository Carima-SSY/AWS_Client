from lib import status_manager as sm
from lib import file_manager as fm
from lib import log_manager as lm
from lib import cam_manager as cam
from lib import aws
from lib import json_file
import json, time, datetime, threading, os, sys, traceback, queue
import urllib.parse

def parse_transfer_url(url):
    """file-transfer URL(S3 키 FILES/{type}/{number}/{data|recipe}/{파일명}.json)에서 파일 종류와 이름을 꺼낸다.
    내려받기에 실패해 내용을 모를 때도 결과에 어떤 파일인지 실어 보내기 위함. 알 수 없으면 (None, None)."""
    try:
        parts = urllib.parse.unquote(urllib.parse.urlparse(url or "").path).strip("/").split("/")
        if len(parts) >= 2 and parts[-2] in ("data", "recipe"):
            name = parts[-1]
            return parts[-2], name[:-len(".json")] if name.endswith(".json") else name
    except Exception:
        pass
    return None, None

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

        # 웹에서 온 파일 명령(file-transfer/file-deletion). MQTT 수신 스레드는 넣기만 하고
        # file_command_worker가 받은 순서대로 처리한다.
        self.file_commands = queue.Queue()

    def file_command_worker(self):
        """파일 명령을 MQTT 수신 스레드 밖에서 처리한다. 큰 슬라이스를 내려받고 푸는 동안에도
        다른 명령 수신과 접속 유지(keepalive)가 막히지 않는다. 명령마다 처리 결과를 웹으로 보낸다."""
        while True:
            request, data = self.file_commands.get()
            # 결과에 실을 파일 종류·이름. 업로드는 내려받은 내용에서, 내려받지 못하면 URL 경로에서 알아낸다.
            ftype, fname = data.get("type"), data.get("name")
            success, error = False, None
            try:
                if request == "file-transfer":
                    ftype, fname = parse_transfer_url(data.get("url"))
                    res = self.api_gateway.get_file_from_s3(get_url=data.get("url"))
                    if res is None:
                        error = "download-failed"
                        print(f"file-transfer: 파일을 내려받지 못함(URL 만료 등) -> 건너뜀")
                    else:
                        ftype, fname = res.get("type"), res.get("name")
                        success = self.request_file_transfer(ftype=ftype, fname=fname, fcontent=res.get("content"))
                elif request == "file-deletion":
                    success = self.request_file_deletion(ftype=ftype, fname=fname)
            except Exception as e:
                error = str(e)
                print(f"Exception in file_command_worker ({request}): {str(e)}\n{traceback.format_exc()}")

            self.publish_file_command_result(request, ftype, fname, success, error)

    def publish_file_command_result(self, request, ftype, fname, success, error=None):
        """파일 명령 처리 결과를 웹으로 보낸다(IoTCore_Handler가 action 이름 그대로 브라우저에 전달).
        웹은 실패한 업로드·삭제를 사용자에게 알리고 업로드 대기 표시를 정리한다."""
        try:
            self.iot_core.publish({
                "target": ["browser"],
                "action": "file-command-result",
                "device": {
                    "type": self.client_file.device_type,
                    "number": self.client_file.device_number
                },
                "data": {
                    "request": request,
                    "type": ftype,
                    "name": fname,
                    "success": success == True,
                    "error": error,
                    "timestamp": int(time.time() * 1000)
                }
            })
        except Exception as e:
            print(f"Exception in publish_file_command_result: {str(e)}")

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
            return self.client_file.delete_print_data(name=fname)
        elif ftype == "recipe":
            return self.client_file.delete_print_recipe(name=fname)
        else:
            return False
        
    def request_add_printing(self, data):
        if self.client_status.device_type in fm.PRINT_QUEUE_DEVICE_TYPES:
            self.client_status.add_device_request({
                "type": "add-printing",
                "data": data
            })
        
    def request_change_printing(self, data):
        if self.client_status.device_type in fm.PRINT_QUEUE_DEVICE_TYPES:
            self.client_status.add_device_request({
                "type": "change-printing",
                "data": data
            })
            
    def request_delete_printing(self, data):
        if self.client_status.device_type in fm.PRINT_QUEUE_DEVICE_TYPES:
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
        if self.client_file.device_type in fm.XML_DEVICE_TYPES:
            if type == "print-recipe":
                self.client_file.save_json_to_xml(folder=self.client_file.recipe_folder, file=name, data=content, root_name=None)
            elif type == "device-setting":
                self.client_file.save_json_to_xml(folder=self.client_file.setting_folder, file=name, data=content, root_name=None)
        else: pass
        
    def iotcore_onmessage_handler(self, client, userdata, msg):
        # 여기서 난 예외가 paho 통신 스레드까지 올라가면 그 스레드가 멈춰 이후 명령을 받지 못하므로 모두 잡는다
        try:
            self._handle_iotcore_message(msg)
        except Exception as e:
            print(f"Exception in iotcore_onmessage_handler: {str(e)}\n{traceback.format_exc()}")

    def _handle_iotcore_message(self, msg):
        topic = msg.topic
        message = dict(json.loads(msg.payload.decode()))
        # print (f"Message from {topic} is {message}")
        
        request = message.get("request")
        
        if request is None: 
            return 
        
        if request == "file-transfer":
            # 내려받기·압축 해제는 오래 걸릴 수 있어 file_command_worker로 넘긴다(받은 순서대로 처리)
            self.file_commands.put((request, message.get("data") or {}))

        elif request == "file-deletion":
            print("=========================================================\n=========================================================\nDEVICE REQUEST: FILE DELETE!!!!\n=========================================================\n=========================================================\n")
            print (f"Message from {topic} is {message}")
            # 앞서 받은 업로드보다 먼저 지워지지 않도록 같은 순서로 처리한다
            self.file_commands.put((request, message.get("data") or {}))
            
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
    if client_status.get_device_status()["status"] in ["PRINTING_READY", "PRINTING", "PRINTING_PAUSE", "PARTS_REMOVING", "WAIT_POSTPROCESS", "PUSH_PARTS"]:
        if os.path.exists(get_resource_path("print-history.json")) == False:
            client_status.create_print_history()
            current_history = client_status.get_print_history()
            current_history["name"] = f'{DEVICE_TYPE}-{DEVICE_NUMBER}-{int(time.time())}'
            current_history["database"]["user"] = client_status.get_print_status()["user"]
            current_history["database"]["print"]["data"] = client_status.get_print_status()["data"][client_status.get_print_status()["data-index"]]
            current_history["database"]["print"]["recipe"] = client_status.get_print_status()["recipe"]
            current_history["database"]["time"]["start"] = datetime.datetime.fromtimestamp(int(time.time())).strftime("%Y:%m:%d:%H:%M:%S")

            current = float(client_status.get_sensor_status()["temperature"]["current"])
            target = float(client_status.get_sensor_status()["temperature"]["target"])
            if current - target > 1 or target - current > 1:
                current_history["database"]["warning"] = f"HEATING: {target - current:.2f} DEGREE DIFFERENCE"
    
            client_status.set_print_history(data=current_history)
        
        return False, None
    
    elif client_status.get_device_status()["status"] in ["PRINTING_ABORT", "PRINTING_FINISH"]:
        if os.path.exists(get_resource_path("print-history.json")):
            current_history = client_status.get_print_history()
            if current_history["database"]["result"] == "-":
                current_history["database"]["result"] = client_status.get_device_status()["status"]
                current_history["database"]["time"]["end"] = datetime.datetime.fromtimestamp(int(time.time())).strftime("%Y:%m:%d:%H:%M:%S")

                json_file.write_json(os.path.join(client_status.history_folder, f'{current_history["name"]}.json'), current_history)

                # upload_handler(file_manager.reset_print_history_updatelist)와 같은 Lock 안에서 읽고-고쳐-쓴다
                json_file.update_json(
                    os.path.join(client_status.history_folder, "print-history.json"),
                    lambda print_history: print_history['updated-list'].append(f'{current_history["name"]}.json'),
                )
                    
                client_status.delete_print_history()
                
                return True, current_history
            else: return False, None
        else:
            return False, None
        
    elif client_status.get_device_status()["status"] in ["OFFLINE", "IDLE", "CONFIG_EDIT", "DEVICE_CONTROL"]:
        if os.path.exists(get_resource_path("print-history.json")):
            client_status.delete_print_history()
            print(f"\n=========================================================\n=========================================================\nDELETE PRINT HISTORY DUE TO DEVICE: {client_status.get_device_status()['status']}\n=========================================================\n=========================================================\n")
        return False, None
    
    else:
        print(f"\n=========================================================\n=========================================================\nINVALID STATUS: {client_status.get_device_status()['status']}\n=========================================================\n=========================================================\n")
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
            # 예외가 나도 쉬고 다음 주기로 — 안 그러면 같은 예외로 쉬지 않고 루프를 돈다
            print(f"Exception in cam_handler: {str(e)}\n{traceback.format_exc()}")
            time.sleep(delay_time)

def status_handler(iot_client: aws.ToIoTCore, client_status: sm.StatusManager, client_log: lm.LogManager):
    count = 0
    current_timestamp = int(time.time())
    
    current_devconfig = dict()

    file_path = client_log.create_log_file()
    log_count = 0
    while True:
        try:
            status_target = ["browser"]
                     
            if count >= 60 or int(time.time()) - current_timestamp >= 60: 
                status_target.append("storage")
                count = 0
                current_timestamp = int(time.time())
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
            # 예외가 나도 쉬고 다음 주기로 — 안 그러면 같은 예외로 쉬지 않고 루프를 돈다
            print(f"Exception in status_handler: {str(e)}\n{traceback.format_exc()}")
            time.sleep(1)

RESYNC_INTERVAL = 300  # seconds — 바뀌지 않아도 슬라이스·레시피 목록을 다시 올리는 주기
RETRY_INTERVAL = 10    # seconds — 업로드에 실패한 항목을 다시 시도하기까지 기다리는 시간

def upload_json(apig_client: aws.ToAPIG, data_name: str, data, name=None) -> bool:
    """업로드 URL을 받아 S3에 JSON을 올린다. 성공했을 때만 True."""
    try:
        res = apig_client.get_presigned_url(devtype=DEVICE_TYPE, devnum=DEVICE_NUMBER, method="put_object", data=data_name, name=name)
        if res is None:
            print(f"upload {data_name}: 업로드 URL을 받지 못함")
            return False
        if apig_client.put_file_to_s3(put_url=res["data"]["url"], data=data) != True:
            print(f"upload {data_name}: S3 업로드 실패")
            return False
        return True
    except Exception as e:
        print(f"upload {data_name}: {str(e)}")
        return False

def file_sync_handler(apig_client: aws.ToAPIG, client_file: fm.FileManager):
    """슬라이스·레시피·장비 설정 목록을 S3(웹)에 맞춰 둔다.
    - 업로드에 성공했을 때만 "올린 목록"을 바꾼다. 실패하면 RETRY_INTERVAL 뒤 다시 올린다.
    - 슬라이스·레시피 목록은 바뀌지 않아도 RESYNC_INTERVAL마다 다시 올려, 어떤 이유로 웹과
      어긋나도 그 안에 다시 맞춰지게 한다(장비 설정은 웹에서 편집 중일 수 있어 바뀔 때만 올림).
    """
    last_upload = {"print-data": 0, "print-recipe": 0, "device-setting": 0}
    retry_at = {"print-data": 0, "print-recipe": 0, "device-setting": 0}

    def sync(data_name, valid, current, attr, resync):
        now = time.time()
        if valid != True or now < retry_at[data_name]:
            return
        changed = getattr(client_file, attr) != current
        if not changed and not (resync and now - last_upload[data_name] >= RESYNC_INTERVAL):
            return
        if upload_json(apig_client, data_name, current):
            setattr(client_file, attr, current)
            last_upload[data_name] = now
        else:
            retry_at[data_name] = now + RETRY_INTERVAL

    while True:
        try:
            current_data = client_file.get_print_data()
            sync("print-data", current_data is not None, current_data, "print_data", resync=True)

            valid, current_recipe = client_file.get_print_recipe()
            sync("print-recipe", valid, current_recipe, "print_recipe", resync=True)

            valid, current_setting = client_file.get_device_setting()
            sync("device-setting", valid, current_setting, "device_setting", resync=False)

            time.sleep(1)
        except Exception as e:
            # 예외가 나도 쉬고 다음 주기로 — 안 그러면 같은 예외로 쉬지 않고 루프를 돈다
            print(f"Exception in file_sync_handler: {str(e)}\n{traceback.format_exc()}")
            time.sleep(1)

def upload_handler(apig_client: aws.ToAPIG, client_file: fm.FileManager):
    """장비 로그·출력 이력 업로드. 슬라이스·레시피 목록 갱신과 다른 스레드에서 돌아 서로 늦추지 않는다.
    올리는 데 성공했거나 읽을 수 없는 항목만 대기 목록에서 빼고, 업로드에 실패한 항목은 남겨
    RETRY_INTERVAL 뒤 다시 올린다."""
    while True:
        failed = False
        try:
            valid, current_logs = client_file.get_device_log_updatelist()
            if valid == True:
                done = []
                for current_log in current_logs:
                    valid, updated_log = client_file.get_device_log(current_log)
                    if valid != True:
                        print(f"device-log {current_log}: 파일을 읽을 수 없어 업로드 목록에서 뺌 ({updated_log})")
                        done.append(current_log)
                    elif upload_json(apig_client, "device-log", updated_log, name=str(current_log).split('.')[0]):
                        done.append(current_log)
                    else:
                        failed = True
                        break
                if done:
                    client_file.reset_device_log_updatelist(done=done)

            valid, current_historys = client_file.get_print_history_updatelist()
            if valid == True and not failed:
                done = []
                for current_history in current_historys:
                    valid, updated_history = client_file.get_print_history(current_history)
                    if valid != True:
                        print(f"print-history {current_history}: 파일을 읽을 수 없어 업로드 목록에서 뺌 ({updated_history})")
                        done.append(current_history)
                    elif upload_json(apig_client, "print-history", updated_history["storage"], name=updated_history["name"]):
                        done.append(current_history)
                        threading.Thread(target=captureimg_handler, args=(apig_client, client_file, updated_history["name"])).start()
                    else:
                        failed = True
                        break
                if done:
                    client_file.reset_print_history_updatelist(done=done)
        except Exception as e:
            print(f"Exception in upload_handler: {str(e)}\n{traceback.format_exc()}")

        # 실패했으면 조금 더 기다렸다가 다시 시도한다(네트워크가 끊긴 동안 매초 요청하지 않도록)
        time.sleep(RETRY_INTERVAL if failed else 1)
    
if __name__ == "__main__":
    if not fm.is_supported_device(DEVICE_TYPE):
        print(f"WARNING: 지원 목록에 없는 장비 타입({DEVICE_TYPE}) — 슬라이스·레시피 목록이 웹에 올라가지 않는다. lib/file_manager.py의 기종 목록을 확인할 것.")

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
        sync_thread = threading.Thread(target=file_sync_handler, args=(aws_client.api_gateway, aws_client.client_file))
        upload_thread = threading.Thread(target=upload_handler, args=(aws_client.api_gateway, aws_client.client_file))
        file_command_thread = threading.Thread(target=aws_client.file_command_worker)
        cam_thread = threading.Thread(target=cam_handler, args=(aws_client.cam_core, aws_client.client_status, aws_client.client_cam))
        
        status_thread.start()
        sync_thread.start()
        upload_thread.start()
        file_command_thread.start()
        cam_thread.start()
        
        status_thread.join()
        sync_thread.join()
        upload_thread.join()
        file_command_thread.join()
        cam_thread.join()

    finally:
        aws_client.iot_core.disconnect()
        aws_client.client_status.delete_json_file()
        aws_client.cam_core.disconnect()