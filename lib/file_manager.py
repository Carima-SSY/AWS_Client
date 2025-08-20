import os 
from PIL import Image
import base64
import zipfile
import io
import shutil

SLICE_FORMAT = (".slice",".crmaslice",".cws",".cmz")
class FileManager: 
    def __init__(self, device_type, device_number, data_folder, recipe_folder):
        self.device_type = device_type
        self.device_number = device_number
        self.data_folder = data_folder
        self.recipe_folder = recipe_folder
        
        self.print_data = dict()
        self.print_recipe = dict()
    
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
        
    def get_subfolder(self, folder: str):
        return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isdir(os.path.join(folder, f))]

    def get_files(self, folder: str):
        return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

    def get_previewimg(self, files: list):
        preview_list = list()
        
        for file in files:
            if "preview" in file:
                preview_list.append(file)
                
        return preview_list

    def encode_previewimg(self, file: str, width: int):
        img = Image.open(file)
        
        w_percent = width / float(img.size[0])
        new_height = int((float(img.size[1]) * float(w_percent)))
        img_resized = img.resize((width, new_height), Image.LANCZOS)

        img_resized.save("output.webp", format="WEBP", quality=80)
        with open("output.webp", "rb") as image_file:
            encoded_bytes = base64.b64encode(image_file.read())
            
        encoded_str = encoded_bytes.decode('utf-8')
        
        os.remove("output.webp")
        
        return encoded_str

    def encode_recipe(self, file: str):
        with open(file, "rb") as rec_file:
            encoded_bytes = base64.b64encode(rec_file.read())
            
        encoded_str = encoded_bytes.decode('utf-8')
        
        return encoded_str

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
        folders = self.get_subfolder(self.data_folder)
        
        slices = list()
        for folder in folders: 
            valid, form = self.is_slicefolder(folder)
            if valid == True:
                slices.append(folder)
        
        print_data = dict() 
        for slice in slices:
            split_str = str(slice).split('/')
            name = split_str[len(split_str)-1]
            files = self.get_files(slice)
            preview = self.get_previewimg(files)
            encoded = self.encode_previewimg(preview, 120)
            
            print_data[name] = {
                "preview": encoded,
                "size": os.path.getsize(slice)
            }  
        return print_data
        
    def get_print_recipe(self, folder: str):
        if self.device_type == "X1" or self.device_type == "DM400":
            files = self.get_files(folder)
            recipe_dic = dict()
            for file in files:
                if self.is_recipefile(file):
                    recipe_dic[file.split('/')[len(file.split('/'))-1]] = {
                        "content": self.encode_recipe(file),
                        "size": os.path.getsize(file)
                    }
            return True, recipe_dic    
        elif self.device_type == "DM4K" or self.device_type == "IML" or self.device_type == "IMDC" or self.device_type == "IMD":
            recipe_dic = dict()
            recipe_dic["recipe-list"] = self.extract_resins(folder+"/resin.cfg")
            return True, recipe_dic
        else:
            False, None
            
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
            
    def add_print_recipe(self, name: str, encoded_content: str):
        if self.device_type != "X1" or self.device_type != "DM400":
            return False
        
        recipe_file_path = self.recipe_folder+"/"+name

        # base64 디코딩
        decoded_content = base64.b64decode(encoded_content)

        #파일로 저장
        with open(recipe_file_path, 'wb') as f:
            f.write(decoded_content)