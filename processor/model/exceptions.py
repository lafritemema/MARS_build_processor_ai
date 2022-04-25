from exceptions import BaseError

class ModelDataError(BaseError):
    def __init__(self, element:str, missing_key:str):
        self._parsing_stack = [element]
        super().__init__(f"Missing data {missing_key} for {element} creation.")
   
    @property
    def parsing_stack(self):
        return self._parsing_stack

    def update_stack(self, new_element:str):
        self._parsing_stack.append(new_element)
    