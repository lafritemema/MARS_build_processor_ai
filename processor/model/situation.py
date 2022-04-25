from typing import List, Dict, Tuple
from collections import OrderedDict
from .exceptions import ModelDataError


class StateObject:
    
    def __init__(self, uid: str, relation:str, state:str, description:str=None, priority:int=0):
        self._uid=uid
        self._description=description
        self._priority=priority
        self._relation=getattr(StateObject, relation)
        self._state = state
        
    @property
    def priority(self)->int:
        return self._priority
    
    @property
    def relation(self):
        return self._relation

    @property
    def uid(self)->str:
        return self._uid
    
    @property
    def state(self)->str:
        return self._state

    @staticmethod
    def from_dict(so_dict:Dict) -> 'StateObject':
        try:
            definition=so_dict['definition']
            relation=so_dict['relation']
            priority=so_dict.get('priority')
            state=so_dict['state']
            
            return StateObject(definition['uid'], relation, state, definition['description'], priority)
        except KeyError as e:
            raise ModelDataError(StateObject.__name__, e.args[0])
        except Exception as e:
            print('Error not handled raise during StateObject parsing')
            raise e
    
    def __eq__(self, other_state: 'StateObject') -> bool:
        return self._relation(self._state, other_state.state)#\
                # and other_state.relation(self._state, other_state.state)
    
    @staticmethod
    def eq(fstate:str, sstate:str):
        return fstate == sstate

    @staticmethod
    def neq(fstate:str, sstate:str):
        return fstate != sstate
    
    def __repr__(self) -> str:
        return f"{self._uid} -> {self._relation} -> {self._state}"

class Situation: 
    
    def __init__(self , state_list:List[StateObject]=[]):
        state_list.sort(key=lambda so: so.priority)
        self.__state_objects:Dict[str, StateObject] = OrderedDict(zip([so.uid for so in state_list], state_list))
    

    def __eq__(self, other_situation: 'Situation') -> bool:
        for key, state in self.__state_objects.items():
            other_state = other_situation.get(key)
            if other_state and not state == other_state:
                return False
        return True


    def get(self, key:str) -> StateObject:
        return self.__state_objects.get(key)

    def compare(self, situation:'Situation') -> Tuple[StateObject]:
        """ Compare the situation with an other situation and return the first difference

        Args:
            situation (Situation): situation to compare with

        Returns:
            StateObject|None: the first different stateobject or none if no difference
        """

        for key, self_state in self.__state_objects.items():
            other_state = situation.get(key)
            if not self_state == other_state:
                return self_state, other_state
    

    def update(self, state_object:StateObject):
        self.__state_objects[state_object.uid] = state_object

    def copy(self):
        state_objects = list(self.__state_objects.values())
        return Situation(state_objects)

    @staticmethod
    def from_list(state_list:List[Dict]) -> 'Situation':
        try:
            states = [StateObject.from_dict(so) for so in state_list]
            return Situation(states)
        except ModelDataError as error:
            error.update_stack(Situation.__name__)
            raise error

    def __repr__(self) -> str:
        str_list= [f"{key}->{state_obj.relation}->{state_obj.state}" for key,state_obj in self.__state_objects.items()]
        return ','.join(str_list)