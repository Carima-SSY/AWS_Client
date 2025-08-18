from lib import status_manager as sm
from lib import file_manager as fm
from lib import aws 


def iotcore_onmessage_handler():
    pass
def init_client():
    iot_core = aws.ToIoTCore()

    api_gateway = aws.ToAPIG()

    devstat = sm.StatusManager()
    devfile = fm.FileManager()

if __name__ == "__main__":
    pass
