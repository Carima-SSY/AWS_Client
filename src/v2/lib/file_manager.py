import os, io, json , base64, time, glob, uuid
from PIL import Image
import zipfile
import shutil
import xmltodict
from . import img_process
from . import json_file
from collections import OrderedDict

SLICE_FORMAT = (".slice",".crmaslice",".cws",".cmz")

# 기종 계열(STATIC/config의 기종별 file 설정 기준).
# - XML 계열: 슬라이서가 슬라이스를 폴더로 내보내고, 레시피·장비 설정은 xml 파일
# - CFG 계열: .crmaslice/.cws/.cmz를 압축 파일 하나로 내보내고, 레시피는 resin.cfg
XML_DEVICE_TYPES = ("X1", "X1PRO", "DM400", "DM400PRO")
CFG_DEVICE_TYPES = (
    "DM4K", "DM4KH", "DM4KDS", "DM4KRS", "DM4KBD", "DM4KULTRA",
    "IML", "IML16K", "IML16KULTRA", "IMD", "IMDC", "ZENESIS", "BISON2000",
)
# 출력 대기열(add/change/delete-printing)이 있는 기종
PRINT_QUEUE_DEVICE_TYPES = ("DM400", "DM400PRO")

# 슬라이스 확장자별로 device_type에 따라 "폴더로 배치"할지("folder") "파일 그대로
# 처리"할지("file")가 갈림. 매핑에 없는 기종은 슬라이스 목록이 비므로, 새 기종은
# 위 계열 목록에 추가한다.
_FOLDER_SLICE_MODE = {".slice": "folder", ".crmaslice": "folder"}
_FILE_SLICE_MODE = {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"}
SLICE_FORMAT_MODE_BY_DEVICE = {
    **{t: _FOLDER_SLICE_MODE for t in XML_DEVICE_TYPES},
    **{t: _FILE_SLICE_MODE for t in CFG_DEVICE_TYPES},
}

def is_supported_device(device_type) -> bool:
    return device_type in SLICE_FORMAT_MODE_BY_DEVICE

# 웹에서 받은 슬라이스를 다 풀 때까지 두는 임시 이름. 확장자가 없어 슬라이스 목록에 잡히지 않는다.
PARTIAL_PREFIX = ".awsclient-partial-"

# 슬라이스 목록 캐시: 같은 슬라이스의 미리보기를 매초 다시 만들지 않는다. 폴더/파일의 수정 시각이
# 그대로면 이전 결과를 쓰고, 수정 시각을 놓치는 파일시스템에 대비해 이 시간이 지나면 다시 만든다.
SLICE_CACHE_MAX_AGE = 60  # seconds

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

        # 경로 → (서명, 캐시 시각, 결과). 결과가 None이면 유효하지 않은 슬라이스
        self._slice_cache = dict()

        self.clean_partial_slices()

    def clean_partial_slices(self):
        """지난 실행에서 압축을 풀다 멈춘 임시 슬라이스를 지운다."""
        try:
            for entry in os.listdir(self.data_folder):
                if entry.startswith(PARTIAL_PREFIX):
                    path = os.path.join(self.data_folder, entry)
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
        except Exception as e:
            print(f"clean_partial_slices error: {str(e)}")

    def get_slice_mode(self, ext: str):
        return SLICE_FORMAT_MODE_BY_DEVICE.get(self.device_type, {}).get(ext.lower())

    def is_recipefile(self, file: str):
        if ".xml" in file or ".cfg" in file:
            return True
        else:
            return False
    
    def is_settingfile(self, file: str):
        if self.device_type in XML_DEVICE_TYPES:
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
            _, extension = os.path.splitext(file)
            if extension == ".idx":
                return file
        return None
    
    def get_gcode_file(self, files: list):
        for file in files:
            _, extension = os.path.splitext(file)
            if extension == ".gcode":
                return file
        return None
    
    def encode_previewimg(self, file: str, width: int):
        with open(file, "rb") as f:
            return self.encode_previewimg_bytes(f.read(), width)

    def encode_previewimg_bytes(self, data: bytes, width: int):
        img = Image.open(io.BytesIO(data)).convert("RGBA")

        w_percent = width / float(img.size[0])
        new_height = int((float(img.size[1]) * float(w_percent)))
        img_resized = img.resize((width, new_height), Image.LANCZOS)

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

    def get_folder_size(self, path: str):
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                fp = os.path.join(dirpath, filename)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        return total

    def get_filetype_slice_data(self, path: str):
        # 파일형 슬라이스(.cws/.cmz 등): 압축을 풀지 않고 zip 내부 목록만 확인해서
        # preview/idx/gcode 존재 여부만 체크(내용 파싱은 하지 않음 - 폴더형과 동일 정책)
        try:
            preview_bytes = None
            has_idx_or_gcode = False

            with zipfile.ZipFile(path, "r") as zf:
                for entry in zf.namelist():
                    entry_lower = entry.lower()
                    if preview_bytes is None and "preview" in entry_lower:
                        preview_bytes = zf.read(entry)
                    elif entry_lower.endswith(".idx") or entry_lower.endswith(".gcode"):
                        has_idx_or_gcode = True

            if preview_bytes is None or not has_idx_or_gcode:
                return None

            return {
                "preview": self.encode_previewimg_bytes(preview_bytes, 120),
                "size": os.path.getsize(path)
            }
        except Exception as e:
            print(f"get_filetype_slice_data error: {str(e)}")
            return None

    def get_foldertype_slice_data(self, folder: str):
        slice_files = self.get_files(folder)
        preview = self.get_previewimg(slice_files)
        if len(preview) == 0 or (self.get_idx_file(slice_files) is None and self.get_gcode_file(slice_files) is None):
            # 유효하지 않은 슬라이스 - 목록에서만 제외하고 파일은 건드리지 않음
            return None

        return {
            "preview": self.encode_previewimg(preview[0], 120),
            "size": self.get_folder_size(folder)
        }

    def _get_cached_slice_data(self, path: str, build, seen: set):
        """path의 수정 시각·크기가 그대로이고 캐시가 오래되지 않았으면 이전 결과를 쓴다.
        미리보기 인코딩·폴더 용량 계산을 슬라이스가 바뀔 때만 하기 위함."""
        seen.add(path)
        st = os.stat(path)
        signature = (st.st_mtime_ns, st.st_size)
        now = time.time()

        cached = self._slice_cache.get(path)
        if cached is not None and cached[0] == signature and now - cached[1] < SLICE_CACHE_MAX_AGE:
            return cached[2]

        data = build(path)
        self._slice_cache[path] = (signature, now, data)
        return data

    def get_print_data(self):
        try:
            folders = self.get_subfolder(self.data_folder)
            files = self.get_files(self.data_folder)

            print_data = dict()
            seen = set()

            # 폴더형 슬라이스(device_type상 'folder' 모드인 확장자만 처리)
            for folder in folders:
                name = os.path.basename(folder)
                _, ext = os.path.splitext(name)
                if self.get_slice_mode(ext) != "folder":
                    continue

                data = self._get_cached_slice_data(folder, self.get_foldertype_slice_data, seen)
                if data is None:
                    continue

                print_data[name] = data

            # 파일형 슬라이스(device_type상 'file' 모드인 확장자만 처리, 압축 해제 없음)
            for file in files:
                name = os.path.basename(file)
                _, ext = os.path.splitext(name)
                if self.get_slice_mode(ext) != "file":
                    continue

                data = self._get_cached_slice_data(file, self.get_filetype_slice_data, seen)
                if data is None:
                    continue

                print_data[name] = data

            # 사라진 슬라이스의 캐시는 버린다
            for path in list(self._slice_cache):
                if path not in seen:
                    del self._slice_cache[path]

            return print_data
        except Exception as e:
            print(f"get_print_data error: {str(e)}")
            return None
        
    def get_print_recipe(self):
        try:
            if self.device_type in XML_DEVICE_TYPES:
                files = self.get_files(self.recipe_folder)
                recipe_dic = dict()
                for file in files:
                    if self.is_recipefile(file):
                        recipe_dic[os.path.basename(file)] = {
                            "content": self.convert_xml_to_json(file),
                            "size": os.path.getsize(file)
                        }
                return True, recipe_dic
            elif self.device_type in CFG_DEVICE_TYPES:
                recipe_dic = dict()
                recipe_dic["recipe-list"] = self.extract_resins(os.path.join(self.recipe_folder, "resin.cfg"))
                return True, recipe_dic
            else:
                return False, None
        except Exception as e:
            print(f"get_print_recipe error: {str(e)}")
            return False, None
        
    def get_device_setting(self):
        if self.device_type in XML_DEVICE_TYPES:
            files = self.get_files(self.setting_folder)
            setting_dic = dict()
            for file in files:
                if self.is_settingfile(file):
                    setting_dic = self.convert_xml_to_json(file)
            return True, setting_dic
        elif self.device_type in CFG_DEVICE_TYPES:
            return True, dict()
        else:
            return False, None
    
    def get_device_log_updatelist(self):
        try:
            device_log = json_file.read_json(os.path.join(self.log_folder, "device-log.json"))
            return True, device_log["updated-list"]
        except Exception as e:
            return False, str(e)
        
    def reset_device_log_updatelist(self, done: list | None = None):
        return self._remove_from_updatelist(os.path.join(self.log_folder, "device-log.json"), done)
        
    def get_device_log(self, file: str):
        try:
            device_log = json_file.read_json(os.path.join(self.log_folder, file))
            return True, device_log
        except Exception as e:
            return False, str(e)
        
    def get_print_history_updatelist(self):
        try:
            print_history = json_file.read_json(os.path.join(self.history_folder, "print-history.json"))
            return True, print_history["updated-list"]
        except Exception as e:
            return False, str(e)
        
    def reset_print_history_updatelist(self, done: list | None = None):
        return self._remove_from_updatelist(os.path.join(self.history_folder, "print-history.json"), done)

    def _remove_from_updatelist(self, path: str, done: list | None):
        """updated-list에서 업로드를 마친 항목(done)만 뺀다(done=None이면 전부 비움).

        업로드하는 동안 status 스레드가 새 항목을 추가할 수 있어서, 예전처럼 빈 목록으로
        덮어쓰면 그 항목이 업로드되지 않고 사라진다 — 같은 Lock 안에서 읽고-고쳐-쓴다.
        파일이 없거나 깨져 있으면 빈 목록으로 새로 만든다."""
        def remove(content):
            content["updated-list"] = [] if done is None else [n for n in content["updated-list"] if n not in done]
        try:
            try:
                json_file.update_json(path, remove)
            except (OSError, ValueError, KeyError, TypeError):
                json_file.write_json(path, {"updated-list": []})
            return True, "ResetSuccess"
        except Exception as e:
            return False, str(e)
    
    def get_print_data_blob(self, slice: str):
        try: 
            #print(f"get_print_data_blob: {slice}")
            blob = dict(); i=1
            while True:
                # print(f"{self.data_folder}/{slice}/SEC_{i:04d}.png")
                if os.path.exists(os.path.join(self.data_folder, slice, f"SEC_{i:04d}.png")):
                    blob[f"SEC_{i:04d}.png"] = img_process.analyze_dlp_slice_image(os.path.join(self.data_folder, slice, f"SEC_{i:04d}.png"))
                    i+=1
                else: 
                    #print("\n==========================================\nget_print_data_blob END\n==========================================\n")
                    break
            return True, blob
        except Exception as e:
            return False, str(e)
    
    def get_frame_count(self, folder: str):
        try:
            images = [img for img in os.listdir(os.path.join(self.cam_folder, folder)) if img.endswith((".webp"))]
            return True, len(images)
        except Exception as e:
            print(f"get_frame_count error: {e}")
            return False, None
    
    def get_timelapse_video(self, folder: str):
        try:
            img_process.create_timelapse(src_folder=os.path.join(self.cam_folder, folder), output_file=os.path.join(self.cam_folder, folder, f"{folder}.mp4"), fps=30)
            return True, os.path.join(self.cam_folder, folder, f"{folder}.mp4") 
        except Exception as e:
            print(f"get_timelapse_video error: {e}")
            return False, None
        
    def get_preview_zip(self, folder: str):
        try:
            img_process.create_preview_zip(src_folder=os.path.join(self.cam_folder, folder), output_file=os.path.join(self.cam_folder, folder, folder))
            return True, os.path.join(self.cam_folder, folder, f"{folder}.zip")
        except Exception as e:
            print(f"get_preview_zip error: {e}")
            return False, None
     
    def clean_timelapse_frame(self, folder: str):
        try:
            if os.path.exists(os.path.join(self.cam_folder, folder)):
                images = [img for img in os.listdir(os.path.join(self.cam_folder, folder)) if img.endswith((".jpg", ".png", ".jpeg", ".webp"))]
                for image in images:
                    file_path = os.path.join(self.cam_folder, folder, image)
                    os.remove(file_path)
            return True
        except Exception as e:
            print(f"clean_timelapse_frame error: {e}")
            return False
        
    def get_print_history(self, file: str):
        try:
            print(f"get_print_history: {file}")
            print_history = json_file.read_json(os.path.join(self.history_folder, file))

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
            print_history["storage"]["recipe"] = self.convert_xml_to_json(os.path.join(self.recipe_folder, print_history['database']['print']['recipe']))
            
            json_file.write_json(os.path.join(self.history_folder, file), print_history)
            
            return True, print_history
        except Exception as e:
            return False, str(e)
    
    def set_print_history(self, data: dict):
        json_file.write_json(f"print-history-{int(time.time())}.json", data)
        return True
    
    def add_print_data(self, name: str, encoded_content: str):
        # base64 디코딩
        decoded_bytes = base64.b64decode(encoded_content)

        # 전송용으로 덧붙은 ".zip"은 실제 슬라이스 이름/확장자가 아니므로 떼고 판정
        logical_name = name[:-len(".zip")] if name.lower().endswith(".zip") else name
        _, ext = os.path.splitext(logical_name)
        mode = self.get_slice_mode(ext)

        target_path = os.path.join(self.data_folder, logical_name)
        # 임시 이름으로 끝까지 만든 뒤 한 번에 제자리로 옮긴다. 만드는 도중의 슬라이스가
        # 목록·장비에 보이지 않고, 중간에 실패하면 임시본만 지워진다.
        temp_path = os.path.join(self.data_folder, f"{PARTIAL_PREFIX}{uuid.uuid4().hex}")

        try:
            if mode == "file":
                # 파일형 슬라이스: 압축 해제 없이 받은 바이트를 그대로 파일로 저장
                with open(temp_path, "wb") as f:
                    f.write(decoded_bytes)
                self._replace_path(temp_path, target_path)
                return

            # 폴더형 슬라이스(매핑에 없는 경우도 기존과 동일하게 폴더형으로 처리)
            with zipfile.ZipFile(io.BytesIO(decoded_bytes)) as zip_ref:
                zip_ref.extractall(temp_path)

            # 압축 안에 폴더가 하나뿐이면 그 폴더를 슬라이스로 쓴다(한 단계 위로 올리는 기존 동작과 같은 결과)
            source_path = temp_path
            items = os.listdir(temp_path)
            if len(items) == 1 and os.path.isdir(os.path.join(temp_path, items[0])):
                source_path = os.path.join(temp_path, items[0])

            self._replace_path(source_path, target_path)
        finally:
            if os.path.isdir(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)
            elif os.path.exists(temp_path):
                os.remove(temp_path)

    def _replace_path(self, source_path: str, target_path: str):
        """source를 target 자리로 옮긴다. 같은 이름이 이미 있으면 새 것으로 바꾼다."""
        if not os.path.exists(target_path):
            os.replace(source_path, target_path)
            return

        # 기존 것을 임시 이름으로 비켜 두고 새 것을 넣은 뒤 지운다(빈 시간이 거의 없음)
        old_path = os.path.join(self.data_folder, f"{PARTIAL_PREFIX}{uuid.uuid4().hex}")
        os.replace(target_path, old_path)
        try:
            os.replace(source_path, target_path)
        except Exception:
            os.replace(old_path, target_path)  # 실패하면 기존 것을 되돌린다
            raise
        if os.path.isdir(old_path):
            shutil.rmtree(old_path, ignore_errors=True)
        else:
            os.remove(old_path)

    def delete_print_data(self, name: str):
        data_path = os.path.join(self.data_folder, name)

        try:
            if os.path.isdir(data_path):
                shutil.rmtree(data_path)
            elif os.path.isfile(data_path):
                os.remove(data_path)
            return True
        except Exception as e:
            print(f"Exception error in delete_print_data: {str(e)}")
            return False
        
    def add_print_recipe(self, name: str, encoded_content: str):
        if self.device_type not in XML_DEVICE_TYPES:
            return False
        
        recipe_file_path = os.path.join(self.recipe_folder, name)

        # base64 디코딩
        decoded_content = base64.b64decode(encoded_content)

        #파일로 저장
        with open(recipe_file_path, 'wb') as f:
            f.write(decoded_content)    
            
    def delete_print_recipe(self, name: str):
        if self.device_type not in XML_DEVICE_TYPES:
            return False
        
        recipe_file_path = os.path.join(self.recipe_folder, name)
        
        try:
            os.remove(recipe_file_path)
            return True
        except Exception as e:
            print(f"Exception error in delete_print_recipe: {str(e)}")
            return False