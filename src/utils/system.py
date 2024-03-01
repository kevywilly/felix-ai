from subprocess import check_output
import os
class SystemUtils:

    def wifi_up():
        return check_output(['hostname', '-I']) is not None
    
    def makedir(path: str):
        try:
            os.makedirs(path)
        except:
            pass