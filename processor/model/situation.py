from typing import List, Dict, Tuple
from collections import OrderedDict
from .exceptions import ModelException, ModelExceptionType


class StateObject:
    """class describing a state
    """
    def __init__(self, uid: str,
                 relation:str,
                 state:str,
                 description:str=None,
                 priority:int=0):
        """init function
        the value of the stateobject is the combinaison of the relation and the state
        Args:
            uid (str): state id
            relation (str): relation function. 'eq' or 'neq'
            state (str): value of the state
            description (str, optional): description of the stateobject. Defaults to None.
            priority (int, optional): the stateobject priority. Defaults to 0.
        """
        self._uid=uid
        self._description=description
        self._priority=priority
        self._relation=getattr(StateObject, relation) #relation function
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
    def from_dict(so_definition:Dict) -> 'StateObject':
      """function to parse a stateobject definition

      Args:
          so_definition (Dict): stateobject definition

      Raises:
          ModelException: raise if an error occured during the parsing

      Returns:
          StateObject: the stateobject defined
      """

      try:
        definition=so_definition['definition']
        relation=so_definition['relation']
        priority=so_definition.get('priority')
        state=so_definition['state']
        
        return StateObject(definition['uid'],
                           relation,
                           state,
                           definition['description'],
                           priority)

      except KeyError as error:
        # raise if a parameter is missing
        raise ModelException(['STATEOBJECT', 'PARSING'],
                              ModelExceptionType.PARSING_ERROR,
                            f"one asset parameters is missing in the asset description, check your database.\nmissing parameter :{error.args[0]}\nasset uid: {definition['uid']}" )
      except Exception as error:
        # raise if an other errro occured
        raise ModelException(['STATEOBJECT', 'PARSING'],
                              ModelExceptionType.PARSING_ERROR,
                              f"no managed error occured during parsing\n{error}" )
    
    def __eq__(self, other_state: 'StateObject') -> bool:
      """function to check equivalence of two stateobject
      the value of the stateobject is the combinaison of the relation and the state

      Args:
          other_state (StateObject): the second stateobject

      Returns:
          bool: true if stateobjects are equivalent
      """
      return self._relation(self._state, other_state.state)
    
    @staticmethod
    def eq(fstate:str, sstate:str) -> bool:
      """equal relation function
      check if two state are equal

      Args:
          fstate (str): first state
          sstate (str): second state

      Returns:
          bool: true if states are equal else false
      """
      return fstate == sstate

    @staticmethod
    def neq(fstate:str, sstate:str):
      """non equal relation function
      check if two state are not equal

      Args:
          fstate (str): first state
          sstate (str): second state

      Returns:
          bool: true if states are not equal else false
      """  
      return fstate != sstate
    
    def __repr__(self) -> str:
        return f"{self._uid} -> {self._relation} -> {self._state}"

class Situation: 
  """class describing a situation (list of state)
  """
  def __init__(self , state_list:List[StateObject]=[]):
      # sort the stateobject by priority
      state_list.sort(key=lambda so: so.priority)
      # init a ordered dict to store stateobject
      self.__state_objects:Dict[str, StateObject] = OrderedDict(zip([so.uid for so in state_list], state_list))
  

  def __eq__(self, other_situation: 'Situation') -> bool:
    """function to check if two situation are equivalent

    Args:
        other_situation (Situation): the second situation

    Returns:
        bool: true if situations are equivalent else false
    """
    # loop on each stateobject in the situation
    for key, state in self.__state_objects.items():
      # get the corresponding stateobject in the second situation
      other_state = other_situation.get(key)
      # return false if one inequivalence is detected
      if other_state and not state == other_state:
          return False
    # else return true
    return True


  def get(self, key:str) -> StateObject:
    # get situation stateobject using its key 
    return self.__state_objects.get(key)

  def compare(self, situation:'Situation') -> Tuple[StateObject]:
    """ Compare the situation with an other situation and return the first difference

    Args:
        situation (Situation): situation to compare with

    Returns:
        StateObject|None: the first different stateobject or none if no difference
    """
    #loop on each stateobject of the situation
    for key, self_state in self.__state_objects.items():
      # get the corresponding state in the other situation 
      other_state = situation.get(key)
      # return the first inequivalent stateobject or None if no inequivalence
      if not self_state == other_state:
          return self_state, other_state
  

  def update(self, state_object:StateObject):
    """function to update a stateobject in a situation

    Args:
        state_object (StateObject): the stateobject to update
    """
    self.__state_objects[state_object.uid] = state_object

  def copy(self):
    # make a deep copy of a situation
    state_objects = list(self.__state_objects.values())
    return Situation(state_objects)

  @staticmethod
  def from_list(state_list:List[Dict]) -> 'Situation':
    """function to parse a situation definition

    Args:
        state_list (List[Dict]): situation definition (list of stateobject definition)

    Raises:
        ModelException: raise if an error occured during the parsing

    Returns:
        Situation: the Situation instance
    """
    try:
      #parse each stateobject definition
      states = [StateObject.from_dict(so) for so in state_list]
      return Situation(states)
    except ModelException as error:
      # raise if error on parsing
      error.add_in_stack(['SITUATION'])
      raise error

  def __repr__(self) -> str:
      str_list= [f"{key}->{state_obj.relation}->{state_obj.state}" for key,state_obj in self.__state_objects.items()]
      return ','.join(str_list)