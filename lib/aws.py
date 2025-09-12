import paho.mqtt.client as mqtt
import ssl
import time
import json
import os
import base64
import requests

class ToIoTCore:
    def __init__(self, endpoint, client_id, topic, ca_cert, cert_file, private_key):
        """
        AWS IoT Core MQTT 클라이언트 초기화
        :param endpoint: AWS IoT Core Endpoint
        :param client_id: AWS Client ID (Custom)
        :param topic: MQTT Topic
        :param ca_cert: CA Certificate Directory Address 
        :param cert_file: Cert File Directory Address
        :param private_key: Private Key Directory Address
        """
        
        print("Create AWS Client...")
        
        self.endpoint = endpoint
        self.client_id = client_id
        self.topic = topic
        self.ca_cert = ca_cert
        self.cert_file = cert_file
        self.private_key = private_key
        
        self.mqttclient = mqtt.Client(client_id=self.client_id)
        
        print("Create MQTT Client Successfully!!")
        
        # TLS 설정
        self.mqttclient.tls_set(ca_certs=self.ca_cert,
                            certfile=self.cert_file,
                            keyfile=self.private_key,
                            tls_version=ssl.PROTOCOL_TLSv1_2)
        
        print("Set TLS (CA Cert / Cert File / Private Key / TLS Version) Successfully!!")
    
        self.mqttclient.on_connect = self.on_connect
        
    def on_connect(self, client, userdata, flags, rc):
        # Call when connected to AWS IoT Core
        if rc == 0:
            print("Connection to ", self.endpoint,"/", self.topic, ": Success")
            self.mqttclient.subscribe(self.topic)
        else:
            print("Connection to ", self.endpoint,"/", self.topic, f": Failure (RC: {rc})")
        
    def set_onmessage(self, on_message):
        self.mqttclient.on_message = on_message
        
    def connect(self):
        # Connect AWS IoT Core
        print("Try to Connection to", self.endpoint, "/", self.topic, "...")
        self.mqttclient.connect(self.endpoint, 8883, 60)
        self.mqttclient.loop_start()
    
        time.sleep(5)
        
        print("Connection End - Endpoint: ", self.endpoint, "/ topic", self.topic)
    
    def publish(self, message):
        # Send MQTT message
        payload = json.dumps(message)
        self.mqttclient.publish(self.topic, payload)
        print("Sent Message to ", self.endpoint, "/", self.topic, f": {payload}")
    
    def disconnect(self):
        # Disconnect to AWS IoT Core
        self.mqttclient.loop_stop()
        self.mqttclient.disconnect()
        print("Disconnection to ", self.endpoint,"/", self.topic, ": Success")
        
class ToAPIG:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def get_presigned_url(self, devtype, devnum, method, data):
        response = requests.get(f"{self.endpoint}/api/file/{devtype}/{devnum}/{method}/{data}")
        print(response.json())
        if response.status_code == 200: return response.json()
        else: return None
        
    def get_file_from_s3(self, get_url):
        response = requests.get(url=get_url)
        if response.status_code == 200: return response.json()
        else: return None
        
    def put_file_to_s3(self, put_url, data):
        response = requests.put(url=put_url, json=data)
        if response.status_code == 200: return True
        else: return False


