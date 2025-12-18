import os, io, json , base64, time
from PIL import Image
import zipfile
import shutil
import xmltodict
from . import img_process
from collections import OrderedDict

SLICE_FORMAT = (".slice",".crmaslice",".cws",".cmz")
class FileManager: 
    def __init__(self, device_type, device_number, data_folder, recipe_folder, setting_folder, log_folder, history_folder, cam_folder):
        self.device_type = device_type
        self.device_number = device_number
        self.data_folder = data_folder
        self.recipe_folder = recipe_folder
        self.setting_folder = setting_folder
        self.log_folder = log_folder
        self.history_folder = history_folder
        self.cam_folder = cam_folder
        
        self.print_data = dict()
        self.print_recipe = dict()
        self.device_setting = dict()
        
    def is_slicefolder(self, folder: str):
        for sf in SLICE_FORMAT:
            if sf in folder: 
                return True, sf
        return False, None

    def is_recipefile(self, file: str):
        if ".xml" in file or ".cfg" in file:
            return True
        else:
            return False
    
    def is_settingfile(self, file: str):
        if self.device_type == "X1" or self.device_type == "DM400":
            if "SaveFile.xml" in file:
                return True
            else: 
                return False
        else: 
            return False
        
    def get_subfolder(self, folder: str):
        return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isdir(os.path.join(folder, f))]

    def get_files(self, folder: str):
        return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

    def get_previewimg(self, files: list):
        preview_list = list()
        
        for file in files:
            if "preview" in str(file).lower():
                preview_list.append(file)
                
        return preview_list
    
    def get_idx_file(self, files: list):
        for file in files:
            if ".idx" in str(file).lower():
                return file
        return None
    
    def get_gcode_file(self, files: list):
        for file in files:
            if ".gcode" in str(file).lower():
                return file
        return None
    
    def encode_previewimg(self, file: str, width: int):
        img = Image.open(file).convert("RGBA")
        
        w_percent = width / float(img.size[0])
        new_height = int((float(img.size[1]) * float(w_percent)))
        img_resized = img.resize((width, new_height), Image.LANCZOS)

        # img_resized.save("output.webp", format="WEBP", quality=80)
        # try:
        #     with open("output.webp", "rb") as image_file:
        #         encoded_bytes = base64.b64encode(image_file.read())
        # finally:
        #     try:
        #         os.remove("output.webp")
        #     except OSError:
        #         pass
        
        byte_io = io.BytesIO() #  create in-memory file object
        img_resized.save(byte_io, format="WEBP", quality=80) # save img to file object
        byte_io.seek(0) # change location to start to read file
        encoded_bytes = base64.b64encode(byte_io.read()) # base 64 encoding
        
        return encoded_bytes.decode("utf-8")

    def encode_recipe(self, file: str):
        with open(file, "rb") as rec_file:
            encoded_bytes = base64.b64encode(rec_file.read())
            
        encoded_str = encoded_bytes.decode('utf-8')
        
        return encoded_str
    
    def convert_xml_to_json(self, file: str):
        with open(file, 'r', encoding='utf-8') as xml_file:
            xml_data = xml_file.read()        
        return xmltodict.parse(xml_data)
    
    def save_json_to_xml(self, folder: str, file: str, data: dict, root_name=None):
        
        if root_name: final_dict = {root_name: data}
        else: final_dict = data

        xml_data = xmltodict.unparse(final_dict, full_document=True, pretty=True)    
        xml_data = xml_data.replace('<?xml version="1.0" encoding="utf-8"?>', '<?xml version="1.0" standalone="yes"?>')
        
        with open(f"{folder}/{file}", 'w', encoding='utf-8') as xml_file:
            xml_file.write(xml_data)
          
    def extract_resins(self, file: str):
        with open(file, "r", encoding="utf-8", errors="backslashreplace") as cfg_file:
            for line in cfg_file:
                if "ResinList" in line:
                    content_list = [s.strip('"\t\r\n ') for s in line.partition("=")[2].split(',')]
                    break
        
        resin_list = list()
        
        for content in content_list:
            resin_list.append(content.split('=')[0])
            
        return resin_list

    def get_print_data(self):
        try:
            folders = self.get_subfolder(self.data_folder)
            
            slices = list()
            for folder in folders: 
                valid, form = self.is_slicefolder(folder)
                if valid == True:
                    slices.append(folder)
            
            print_data = dict() 
            for slice in slices:
                name = os.path.basename(slice)
                files = self.get_files(slice)
                preview = self.get_previewimg(files)
                encoded = self.encode_previewimg(preview[0], 120)
                
                print_data[name] = {
                    "preview": encoded,
                    "size": os.path.getsize(slice)
                }  
            return print_data
        except Exception as e:
            print(f"get_print_data error: {str(e)}")
            return None
        
    def get_print_recipe(self):
        try: 
            if self.device_type == "X1" or self.device_type == "DM400":
                files = self.get_files(self.recipe_folder)
                recipe_dic = dict()
                for file in files:
                    if self.is_recipefile(file):
                        recipe_dic[os.path.basename(file)] = {
                            "content": self.convert_xml_to_json(file),
                            "size": os.path.getsize(file)
                        }
                return True, recipe_dic    
            elif self.device_type == "DM4K" or self.device_type == "IML" or self.device_type == "IMDC" or self.device_type == "IMD":
                recipe_dic = dict()
                recipe_dic["recipe-list"] = self.extract_resins(self.recipe_folder+"/resin.cfg")
                return True, recipe_dic
            else:
                return False, None
        except Exception as e:
            print(f"get_print_recipe error: {str(e)}")
            return False, None
        
    def get_device_setting(self):
        if self.device_type == "X1" or self.device_type == "DM400":
            files = self.get_files(self.setting_folder)
            setting_dic = dict()
            for file in files:
                if self.is_settingfile(file):
                    setting_dic = self.convert_xml_to_json(file)
            return True, setting_dic    
        elif self.device_type == "DM4K" or self.device_type == "IML" or self.device_type == "IMDC" or self.device_type == "IMD":
            return True, dict()
        else:
            return False, None
    
    def get_device_log_updatelist(self):
        try:
            with open(f"{self.log_folder}/device-log.json", 'r', encoding='utf-8') as f:
                device_log = json.load(f)
            return True, device_log["updated-list"]
        except Exception as e:
            return False, str(e)
        
    def reset_device_log_updatelist(self):
        try:
            with open(f"{self.log_folder}/device-log.json", 'w', encoding='utf-8') as f:
                json.dump({"updated-list": []}, f, ensure_ascii=False, indent=4)
            return True, "ResetSuccess"
        except Exception as e:
            return False, str(e)
        
    def get_device_log(self, file: str):
        try:
            with open(f"{self.log_folder}/{file}", 'r', encoding='utf-8') as f:
                device_log = json.load(f)
            return True, device_log
        except Exception as e:
            return False, str(e)
        
    def get_print_history_updatelist(self):
        try:
            with open(f"{self.history_folder}/print-history.json", 'r', encoding='utf-8') as f:
                print_history = json.load(f)
            return True, print_history["updated-list"]
        except Exception as e:
            return False, str(e)
        
    def reset_print_history_updatelist(self):
        try:
            with open(f"{self.history_folder}/print-history.json", 'w', encoding='utf-8') as f:
                json.dump({"updated-list": []}, f, ensure_ascii=False, indent=4)
            return True, "ResetSuccess"
        except Exception as e:
            return False, str(e)
    
    def get_print_data_blob(self, slice: str):
        try: 
            #print(f"get_print_data_blob: {slice}")
            blob = dict(); i=1
            while True:
                # print(f"{self.data_folder}/{slice}/SEC_{i:04d}.png")
                if os.path.exists(f"{self.data_folder}/{slice}/SEC_{i:04d}.png"):
                    blob[f"SEC_{i:04d}.png"] = img_process.analyze_dlp_slice_image(f"{self.data_folder}/{slice}/SEC_{i:04d}.png")
                    i+=1
                else: 
                    #print("\n==========================================\nget_print_data_blob END\n==========================================\n")
                    break
            return True, blob
        except Exception as e:
            return False, str(e)
    
    def get_frame_count(self, folder: str):
        try:
            images = [img for img in os.listdir(f"{self.cam_folder}/{folder}") if img.endswith((".webp"))]
            return True, len(images)
        except Exception as e:
            print(f"get_frame_count error: {e}")
            return False, None
    
    def get_timelapse_video(self, folder: str):
        try:
            img_process.create_timelapse(src_folder=f"{self.cam_folder}/{folder}", output_file=f"{self.cam_folder}/{folder}/{folder}.mp4", fps=30)
            return True, f"{self.cam_folder}/{folder}/{folder}.mp4"
        except Exception as e:
            print(f"get_timelapse_video error: {e}")
            return False, None
        
    def get_preview_zip(self, folder: str):
        try:
            img_process.create_preview_zip(src_folder=f"{self.cam_folder}/{folder}", output_file=f"{self.cam_folder}/{folder}/{folder}")
            return True, f"{self.cam_folder}/{folder}/{folder}.zip"
        except Exception as e:
            print(f"get_preview_zip error: {e}")
            return False, None
     
    def clean_timelapse_frame(self, folder: str):
        try:
            if os.path.exists(f"{self.cam_folder}/{folder}"):
                images = [img for img in os.listdir(f"{self.cam_folder}/{folder}") if img.endswith((".jpg", ".png", ".jpeg", ".webp"))]
                for image in images:
                    file_path = os.path.join(f"{self.cam_folder}/{folder}", image)
                    os.remove(file_path)
            return True
        except Exception as e:
            print(f"clean_timelapse_frame error: {e}")
            return False
        
    def get_print_history(self, file: str):
        try:
            print(f"get_print_history: {file}")
            with open(f"{self.history_folder}/{file}", 'r', encoding='utf-8') as f:
                print_history = json.load(f)

            # files = self.get_files(f"{self.data_folder}/{print_history["database"]["print"]["data"]}")
            # print(f"FILES TYPE:{type(files)}")
            # ================================================================================
            # Modified Code: Add idx and gcode file content in print-history.json
            # Finished: False
            
            # print_history["storage"]["data"]["idx"] = self.get_idx_file(files) # Add function that convert idx content to json 
            # print_history["storage"]["data"]["gcode"] = self.get_gcode_file(files) # Add function that convert gcode content to json 
            # print(f"IDX: {print_history["storage"]["data"]["idx"]} / GCODE: {print_history["storage"]["data"]["gcode"]}")
            
            print_history["storage"]["data"]["slices"] = self.get_print_data_blob(print_history["database"]["print"]["data"])[1] 
            # ================================================================================
            print_history["storage"]["recipe"] = self.convert_xml_to_json(f"{self.recipe_folder}/{print_history['database']['print']['recipe']}")
            
            with open(f"{self.history_folder}/{file}", 'w', encoding='utf-8') as f:
                json.dump(print_history, f, ensure_ascii=False, indent=4)
            
            return True, print_history
        except Exception as e:
            return False, str(e)
    
    def set_print_history(self, data: dict):
        with open(f"print-history-{int(time.time())}.json", 'w', encoding='utf-8') as content:
            json.dump(data, content, ensure_ascii=False, indent=4)
        return True
    
    def add_print_data(self, name: str, encoded_content: str):
        data_file_path = self.data_folder+"/"+name
        
        # base64 디코딩
        decoded_bytes = base64.b64decode(encoded_content)
        
        data_file_path = data_file_path.removesuffix(".zip")
        
        with zipfile.ZipFile(io.BytesIO(decoded_bytes)) as zip_ref:
            zip_ref.extractall(data_file_path)  # 압축 해제할 폴더 지정
            
        items = os.listdir(data_file_path)
        if len(items) == 1 and os.path.isdir(os.path.join(data_file_path, items[0])):
            inner_folder = os.path.join(data_file_path, items[0])
            
            for item in os.listdir(inner_folder):
                shutil.move(os.path.join(inner_folder, item), data_file_path)
            os.rmdir(inner_folder)
            
    def delete_print_data(self, name: str):
        data_folder_path = self.data_folder+"/"+name
        try:
            shutil.rmtree(data_folder_path)
            return True
        except Exception as e:
            print(f"Exception error in delete_print_data: {str(e)}")
            return False
        
    def add_print_recipe(self, name: str, encoded_content: str):
        if self.device_type != "X1" or self.device_type != "DM400":
            return False
        
        recipe_file_path = self.recipe_folder+"/"+name

        # base64 디코딩
        decoded_content = base64.b64decode(encoded_content)

        #파일로 저장
        with open(recipe_file_path, 'wb') as f:
            f.write(decoded_content)    
            
    def delete_print_recipe(self, name: str):
        if self.device_type != "X1" or self.device_type != "DM400":
            return False
        
        recipe_file_path = self.recipe_folder+"/"+name
        
        try:
            os.remove(recipe_file_path)
            return True
        except Exception as e:
            print(f"Exception error in delete_print_recipe: {str(e)}")
            return False