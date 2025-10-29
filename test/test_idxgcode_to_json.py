import json
import re
import os

GCODE_FILENAME = "run.gcode"
IDX_FILENAME = "test.idx"
OUTPUT_FILENAME = "output.json"

def parse_gcode_file(file_content):
    data = {"gcode_file": {}}
    for line in file_content.split('\n'):
        line = line.strip()
        if line.startswith(';'):
            # ;key:value 또는 ;key=value 패턴 찾기
            match_colon = re.match(r';(\w+):(.+)', line)
            match_equal = re.match(r';(\w+)=(.+)', line)
            
            match = match_colon if match_colon else match_equal
            
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                
                # 숫자로 변환 가능한 경우 변환
                if value.replace('.', '', 1).isdigit() and key != 'fileName': # fileName은 숫자처럼 보여도 문자열 유지
                    data["gcode_file"][key] = float(value) if '.' in value else int(value)
                else:
                    data["gcode_file"][key] = value
                
    return data


def parse_idx_file(file_content):
    data = {"idx_file": {
        "Version": {},
        "BuildData": {},
        "Build and Slicing Parameters": {},
        "Machine Configuration": {},
        "Preview": {},
        "PixelData": {},
        "TotalPixelWhiteCount": {} # 새로운 섹션 추가
    }}
    current_section = None
    
    for line in file_content.split('\n'):
        line = line.strip()
        if not line:
            continue

        section_match = re.match(r'\[(.*?)\]', line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue
        
        if current_section in data["idx_file"] and '=' in line:
            try:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if key: 
                    if current_section == "PixelData" and key.startswith("SEC_"):
                        data["idx_file"][current_section][key] = int(value)
                    
                    elif current_section in data["idx_file"]:
                        if value.replace('.', '', 1).isdigit():
                            data["idx_file"][current_section][key] = float(value) if '.' in value else int(value)
                        else:
                            data["idx_file"][current_section][key] = value
                
            except ValueError:
                pass 

    return data

def write_to_json(gcode_data, idx_data, output_filename):

    final_data = {
        "gcode_data": gcode_data["gcode_file"],
        "idx_data": idx_data["idx_file"]
    }

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    
    print(f"✅ 데이터가 성공적으로 '{output_filename}'에 저장되었습니다.")
    return output_filename



def main():
    
    # GCODE 파일 읽기
    try:
        with open(GCODE_FILENAME, 'r', encoding='utf-8') as f:
            gcode_content = f.read()
        gcode_data = parse_gcode_file(gcode_content)
        print(f"📌 '{GCODE_FILENAME}' 파일 읽기 및 파싱 완료.")
    except FileNotFoundError:
        print(f"❌ 오류: '{GCODE_FILENAME}' 파일을 찾을 수 없습니다. 경로를 확인해 주세요.")
        return

    # IDX 파일 읽기
    try:
        # IDX 파일은 인코딩이 다를 수 있으므로, 에러 발생 시 다른 인코딩 시도 가능
        with open(IDX_FILENAME, 'r', encoding='utf-8') as f:
            idx_content = f.read()
        idx_data = parse_idx_file(idx_content)
        print(f"📌 '{IDX_FILENAME}' 파일 읽기 및 파싱 완료.")
    except FileNotFoundError:
        print(f"❌ 오류: '{IDX_FILENAME}' 파일을 찾을 수 없습니다. 경로를 확인해 주세요.")
        return
    except UnicodeDecodeError:
        print(f"⚠️ 경고: '{IDX_FILENAME}' 파일이 UTF-8 인코딩이 아닐 수 있습니다. 다른 인코딩을 시도해 보세요.")
        # 예를 들어, 'latin-1' 또는 'euc-kr' 등을 시도해 볼 수 있습니다.
        try:
            with open(IDX_FILENAME, 'r', encoding='latin-1') as f:
                idx_content = f.read()
            idx_data = parse_idx_file(idx_content)
            print(f"📌 '{IDX_FILENAME}' 파일 (latin-1 인코딩) 읽기 및 파싱 완료.")
        except:
            print(f"❌ 오류: '{IDX_FILENAME}' 파일을 읽을 수 없습니다.")
            return

    # JSON 파일로 저장
    write_to_json(gcode_data, idx_data, OUTPUT_FILENAME)

if __name__ == "__main__":
    main()