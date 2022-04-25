from exceptions import BaseError

class DatabaseError(BaseError):
    def __init__(self, message:str):
        super().__init__(message)