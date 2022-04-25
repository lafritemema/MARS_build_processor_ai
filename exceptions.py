
class BaseError(Exception):
    def __init__(self, message:str):
        self._message = message 
        super().__init__(self._message)  

    @property
    def message(self):
        return self._message

class ConfigError(BaseError):
  def __init__(self, conf_object, message):
    super().__init__(message)
    self._conf_object = conf_object
  
  @property
  def conf_object(self):
    return self._conf_object