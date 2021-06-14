import subprocess
from typing import Optional, Dict


class ExternalProcessExecError(RuntimeError):
    """Error when an external process fails to run successfully"""
    def __init__(self, cmd: str, message: str):
        self.cmd = cmd
        self.message = message
        super().__init__(f"{message} when running: {cmd}")


def run(cmd: str, suppress_error=False, env: Optional[Dict[str, str]] = None) -> (str, str):
    """Runs an external command and returns back its stdout and stderr"""

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env=env)
    (res, err) = proc.communicate()
    res = res.decode(encoding="utf-8", errors="ignore")
    err = err.decode(encoding="utf-8", errors="ignore")

    if proc.returncode != 0 and not suppress_error:
        msg = f"Failed to execute external process: {cmd}\n{res}\nError: {err}"
        raise ExternalProcessExecError(msg, cmd)

    return res, err
