# import file_manager as fm
# import time
# import json

# start_time = time.time()

# subfolders = fm.get_subfolder("/Users/carima/Documents/TestDir/Datas")

# preview_dict = dict()

# for subfolder in subfolders:
#     previews = fm.get_previewimg(fm.get_files(subfolder))
#     if len(previews) > 0:
#         preview_dict[previews[0]] = fm.encode_previewimg(previews[0],180)
            
# with open("data.json", "w", encoding="utf-8") as f:
#     json.dump(preview_dict, f, ensure_ascii=False, indent=4)
    
# end_time = time.time()
# elapsed_time = (end_time - start_time)*1000

# print(f"실행 시간: {elapsed_time: .4f}밀리 초")



# import status_manager as sm
# import time
# stat_manage = sm.StatusManager()

# time.sleep(5)

# stat_manage.delete_json_file()



from lib import file_manager as fm
from lib import status_manager as sm

test1 = fm.FileManager("DM4K", "1", "", "")
test2 = fm.FileManager("DM400", "1", "", "")

print(test1.get_print_recipe("/Users/carima/Documents/Programming/GitConn/AWS_Client")[1])