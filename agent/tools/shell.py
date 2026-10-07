"""Legacy host shell removed. Use the isolated run_python tool."""


class ShellTools:
    def __init__(self, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        return {"error": "Host shell disabled; run_python requires an explicit Docker image ID"}
