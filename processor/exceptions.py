from exceptions import BaseException, ExceptionType
from typing import List

class ProcessExceptionType(ExceptionType):
  SOLVER_ERROR = "PROCESS_SOLVER_ERROR"


class ProcessException(BaseException):
  def __init__(self, origin_stack:List[str], type:ProcessExceptionType, description:str):
    super().__init__(origin_stack,
                     type,
                     description)