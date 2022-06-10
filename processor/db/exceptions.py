from exceptions import BaseException, ExceptionType
from typing import List

class DBExceptionType(ExceptionType):
  NOT_REACHABLE = 'DB_NOT_REACHABLE'
  MISSING_ELEMENT = 'DB_MISSING_ELEMENT'
  CONFIG_ERROR = 'DB_CONFIG_ERROR'
  UNKNOW_TYPE = 'DB_TYPE_UNKNOW'


class DBDriverException(BaseException):
  def __init__(self, origin_stack:List[str], type:DBExceptionType, description:str):
    super().__init__(origin_stack,
                     type,
                     description)