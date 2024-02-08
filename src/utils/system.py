from subprocess import check_output

class SystemUtils:

    def wifi_up():
        return check_output(['hostname', '-I']) is not None