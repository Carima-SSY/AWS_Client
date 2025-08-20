from lib import status_manager as sm
from lib import file_manager as fm
from lib import aws 
import json, time

class AWSClient: 
    def __init__(self, device_type, device_number, data_folder, recipe_folder, iotcore_endpoint, iotcore_clientid, iotcore_topic, iotcore_cacert, iotcore_certfile, iotcore_privatekey, apig_endpoint):
        self.iot_core = aws.ToIoTCore(endpoint=iotcore_endpoint, client_id=iotcore_clientid, topic=iotcore_topic, ca_cert=iotcore_cacert, cert_file=iotcore_certfile, private_key=iotcore_privatekey)
        self.iot_core.set_onmessage(self.iotcore_onmessage_handler)
        
        self.api_gateway = aws.ToAPIG(endpoint=apig_endpoint)

        self.client_status = sm.StatusManager(device_type=device_type, device_number=device_number)
        self.client_file = fm.FileManager(device_type=device_type, device_number=device_number, data_folder=data_folder, recipe_folder=recipe_folder)
        
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

    def iotcore_onmessage_handler(self, client, userdata, msg):
        topic = msg.topic
        message = dict(json.loads(msg.payload.decode()))
        print (f"Message from {topic} is {message}")
        
        request = message.get("request")
        
        if request is None: 
            return 
        
        if request == "file-transfer":
            message.get("data")
            url = self.api_gateway.get_presigned_url(method="get_object",key=data.get("content"))
            res = self.api_gateway.get_file_from_s3(url=url)
            self.request_file_transfer(ftype=res.get("type"), fname=res.get("name"), fcontent=res.get("content"))
            
        elif request == "print-start":
            data = message.get("data")
            self.request_print_start(data=data.get("data"), recipe=data.get("recipe"))
            
        elif request == "print-abort":
            self.request_print_abort()


DEVICE_TYPE = "DM400"
DEVICE_NUMBER = "123456789"

DATA_FOLDER = "/Users/carima/Documents/TestDir/Datas"
RECIPE_FOLDER = "/Users/carima/Documents/TestDir/Recipes"

IOT_ENDPOINT = "a3nz0danj2sqa0-ats.iot.ap-northeast-2.amazonaws.com"        
CLIENT_ID = "C-Hub_TestClient_v2"
TOPIC = "Status/test"
CA_CERT = "/Users/carima/Documents/AWS/IoTCore/V2_Test_Things/carima-hub_v2_AmazonRootCA1.pem"
CERT_FILE = "/Users/carima/Documents/AWS/IoTCore/V2_Test_Things/carima-hub_v2_certificate.pem.crt"
PRIVATE_KEY = "/Users/carima/Documents/AWS/IoTCore/V2_Test_Things/carima-hub_v2_private.pem.key"

APIG_ENDPOINT = ""


if __name__ == "__main__":
    aws_client = None
    try: 
        aws_client = AWSClient(
            device_type=DEVICE_TYPE,
            device_number=DEVICE_NUMBER,
            data_folder=DATA_FOLDER,
            recipe_folder=RECIPE_FOLDER,
            iotcore_endpoint=IOT_ENDPOINT,
            iotcore_topic=TOPIC,
            iotcore_clientid=CLIENT_ID,  
            iotcore_cacert=CA_CERT,
            iotcore_certfile=CERT_FILE,
            iotcore_privatekey=PRIVATE_KEY,
            apig_endpoint=APIG_ENDPOINT
        )
        aws_client.iot_core.connect()
        while True:
            aws_client.iot_core.publish({
                    "target": ["browser"],
                    "action": "all-status",
                    "data": {
                        "device": aws_client.client_status.get_device_status(),
                        "sensor": aws_client.client_status.get_sensor_status(),
                        "print": aws_client.client_status.get_print_status()
                    }
                }
            )
            
            if aws_client.client_status.get_device_alarm()["subject"] != "-":
                aws_client.iot_core.publish({
                        "target": ["browser"],
                        "action": "device-alarm",
                        "data": aws_client.client_status.get_device_alarm() 
                    }
                )
                
                aws_client.client_status.set_device_alarm({
                        "subject": "-",
                        "content": "-",
                        "created_date": "0000:00:00:00:00:00"
                    }
                )
            
            time.sleep(10)
    finally:
        aws_client.client_status.delete_json_file()
