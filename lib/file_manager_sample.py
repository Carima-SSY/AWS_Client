import os
import io
import shutil
import base64
import zipfile
from typing import List, Dict, Tuple, Optional
from PIL import Image

SLICE_FORMAT = (".slice", ".crmaslice", ".cws", ".cmz")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

class FileManager:
    def __init__(self, device_type: str, device_number: int, data_folder: str, recipe_folder: str):
        self.device_type = device_type
        self.device_number = device_number
        self.data_folder = data_folder
        self.recipe_folder = recipe_folder

        self.print_data: Dict[str, Dict] = {}
        self.print_recipe: Dict[str, Dict] = {}

    # ───────────────────────────── util: path & scan ─────────────────────────────
    def is_slicefolder(self, folder: str) -> Tuple[bool, Optional[str]]:
        base = os.path.basename(folder).lower()
        for sf in SLICE_FORMAT:
            if base.endswith(sf):  
                return True, sf
        return False, None

    def is_recipefile(self, file: str) -> bool:
        ext = os.path.splitext(file)[1].lower()
        # DM/X 계열: xml, cfg, (필요하면 csv도 허용)
        return ext in {".xml", ".cfg", ".csv"}

    def get_subfolder(self, folder: str) -> List[str]:
        try:
            return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isdir(os.path.join(folder, f))]
        except FileNotFoundError:
            return []

    def get_files(self, folder: str) -> List[str]:
        try:
            return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        except FileNotFoundError:
            return []

    def get_files_recursive(self, folder: str) -> List[str]:
        out: List[str] = []
        for root, _, files in os.walk(folder):
            for f in files:
                out.append(os.path.join(root, f))
        return out

    def _dir_size(self, folder: str) -> int:
        total = 0
        for root, _, files in os.walk(folder):
            for f in files:
                path = os.path.join(root, f)
                try:
                    total += os.path.getsize(path)
                except OSError:
                    pass
        return total

    # ─────────────────────────── preview pick & encode ───────────────────────────
    def find_preview(self, files: List[str]) -> Optional[str]:
        """
        preview 대소문자 무시, 파일명 어디에 있어도 허용, 이미지 확장자만.
        우선순위: 'preview' == 0, 'preview*' 시작 == 1, 포함 == 2
        없으면 첫 이미지로 폴백.
        """
        candidates: List[Tuple[int, str]] = []
        for f in files:
            name = os.path.basename(f)
            stem, ext = os.path.splitext(name)
            if ext.lower() not in IMAGE_EXTS:
                continue
            base = stem.casefold()
            if "preview" in base:
                if base == "preview":
                    score = 0
                elif base.startswith("preview"):
                    score = 1
                else:
                    score = 2
                candidates.append((score, f))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        # 폴백: 첫 번째 이미지
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXTS:
                return f
        return None

    def encode_previewimg(self, file: str, width: int) -> str:
        img = Image.open(file).convert("RGBA")
        w_percent = width / float(img.size[0])
        new_height = int(float(img.size[1]) * w_percent)
        img_resized = img.resize((width, new_height), Image.LANCZOS)

        temp_path = "output.webp"
        img_resized.save(temp_path, format="WEBP", quality=80)
        try:
            with open(temp_path, "rb") as image_file:
                encoded_bytes = base64.b64encode(image_file.read())
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return encoded_bytes.decode("utf-8")

    # ───────────────────────── recipe encode / parse ─────────────────────────────
    def encode_recipe(self, file: str) -> str:
        with open(file, "rb") as rec_file:
            encoded_bytes = base64.b64encode(rec_file.read())
        return encoded_bytes.decode("utf-8")

    def extract_resins(self, file: str) -> List[str]:
        """
        resin.cfg 내부에서 'ResinList=' 라인을 찾아
        "A=...,B=...,C=..." 형태에서 좌측 키(A,B,C)만 리스트로 반환.
        파일이 없거나 형식이 달라도 빈 리스트 반환.
        """
        resin_list: List[str] = []
        try:
            with open(file, "r", encoding="utf-8", errors="backslashreplace") as cfg_file:
                for line in cfg_file:
                    if "ResinList" in line:
                        content = line.partition("=")[2]
                        parts = [s.strip('"\t\r\n ') for s in content.split(',') if s.strip()]
                        for p in parts:
                            resin_list.append(p.split('=')[0])
                        break
        except FileNotFoundError:
            pass
        return resin_list

    # ─────────────────────────────── public APIs ─────────────────────────────────
    def get_print_data(self) -> Dict[str, Dict]:
        """
        data_folder 하위의 *.slice 등 폴더를 찾아
        - preview: base64(webp, width 120) (없으면 빈 문자열)
        - size: 폴더 전체 사이즈
        를 dict로 반환.
        """
        folders = self.get_subfolder(self.data_folder)
        slices = [f for f in folders if self.is_slicefolder(f)[0]]

        print_data: Dict[str, Dict] = {}
        for slc in slices:
            name = os.path.basename(slc)
            files = self.get_files_recursive(slc)
            preview_path = self.find_preview(files)

            encoded = ""
            if preview_path:
                try:
                    encoded = self.encode_previewimg(preview_path, 120)
                except Exception:
                    encoded = ""  # 이미지 깨짐 등 예외 시 폴백

            print_data[name] = {
                "preview": encoded,
                "size": self._dir_size(slc),
            }
        return print_data

    def get_print_recipe(self) -> Tuple[bool, Optional[Dict]]:
        """
        DM400/X1: recipe 폴더 내 xml/cfg/csv 파일을 base64로 싣는다.
        IM 시리즈/DM4K: resin.cfg에서 리스트만 반환.
        """
        if self.device_type in ("X1", "DM400"):
            files = self.get_files(self.recipe_folder)
            recipe_dic: Dict[str, Dict] = {}
            for file in files:
                if self.is_recipefile(file):
                    recipe_dic[os.path.basename(file)] = {
                        "content": self.encode_recipe(file),
                        "size": os.path.getsize(file),
                    }
            return True, recipe_dic

        elif self.device_type in ("DM4K", "IML", "IMDC", "IMD"):
            cfg_path = os.path.join(self.recipe_folder, "resin.cfg")
            recipe_dic = {"recipe-list": self.extract_resins(cfg_path)}
            return True, recipe_dic

        else:
            return False, None

    def add_print_data(self, name: str, encoded_content: str) -> bool:
        """
        업로드 받은 zip(base64)을 data_folder/name(확장자 .zip 제거) 아래로 풀고
        내부에 단일 폴더만 있을 경우 평탄화.
        """
        target_dir = os.path.join(self.data_folder, name).removesuffix(".zip")
        os.makedirs(target_dir, exist_ok=True)

        decoded_bytes = base64.b64decode(encoded_content)
        with zipfile.ZipFile(io.BytesIO(decoded_bytes)) as zip_ref:
            zip_ref.extractall(target_dir)

        # 단일 내부폴더 평탄화
        try:
            items = os.listdir(target_dir)
            if len(items) == 1:
                inner = os.path.join(target_dir, items[0])
                if os.path.isdir(inner):
                    for item in os.listdir(inner):
                        shutil.move(os.path.join(inner, item), target_dir)
                    os.rmdir(inner)
        except OSError:
            pass

        return True

    def add_print_recipe(self, name: str, encoded_content: str) -> bool:
        """
        DM400/X1에서만 레시피 파일 저장. (그 외 모델은 False)
        """
        if self.device_type not in ("X1", "DM400"):
            return False

        os.makedirs(self.recipe_folder, exist_ok=True)
        recipe_file_path = os.path.join(self.recipe_folder, name)

        decoded_content = base64.b64decode(encoded_content)
        with open(recipe_file_path, "wb") as f:
            f.write(decoded_content)
        return True