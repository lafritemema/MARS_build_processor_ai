from exceptions import BaseException, ExceptionType
from enum import Enum
from typing import List

class ModelExceptionType(ExceptionType):
    PARSING_ERROR = "MODEL_PARSING_ERROR"


class ModelException(BaseException):
  def __init__(self, origin_stack:List[str], type:ModelExceptionType, description:str):
    super().__init__(origin_stack,
                     type,
                     description)
    