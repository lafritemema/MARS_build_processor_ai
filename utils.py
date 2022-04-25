from enum import Enum
from typing import List

class MsgDecorator(Enum):
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class BaseError(Exception):
  
  def __init__(self, origin:str, message:str, error_type:str):
    self._origin = origin
    self._message = message
    self._error_type = error_type

  def __repr__(self):
    error_type = self._error_type.upper()
    return f"{MsgDecorator[error_type].value}[{error_type}][{self._origin.upper()}] : {self._message}{MsgDecorator.ENDC.value}"

  def __str__(self):
    error_type = self._error_type.upper()
    return f"{MsgDecorator[error_type].value}[{error_type}][{self._origin.upper()}] : {self._message}{MsgDecorator.ENDC.value}"