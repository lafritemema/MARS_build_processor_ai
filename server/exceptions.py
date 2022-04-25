from exceptions import BaseError, ConfigError

class ServerConfigError(ConfigError):
  def __init__(self, message) -> None:
      super().__init__('SERVER.HTTP', message)



class QueryError(BaseError):
  def __init__(self, message: str, type:str, origin:str):
    self._type = type
    self._origin = origin
    super().__init__(message)
  
  def to_json(self):
    return {
      "type": self._type,
      "origin": self._origin,
      "message": self._message
    }