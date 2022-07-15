
from enum import Enum
import logging
from processor.model.marsnode import Action
from .db.drivers import Neo4jDriver
from .db.queries import register as qreg
from .model.scoring import sort_by_position
from .model.situation import Situation
from .exceptions import ProcessException, ProcessExceptionType
from typing import List, Dict, Deque, Union
from .model.situation import StateObject, Situation
from collections import deque
from .model.marsnode import Action
from .model.optimization import begin_with_probing
import time

class SequenceTypeRegister(Enum):
  work_area = 'get_work_by_area'
  station_area = 'get_station_by_area'
  approach_area = 'get_approach_by_area'

class DataUnit():
  """
    object to data from neo4j database
    it contains function to application specific needs
  """
  def __init__(self, host_uri:str, auth:tuple):
    self._driver = Neo4jDriver(host_uri, auth[0], auth[1])
  
  def get_work_by_area(self, area_definition:Dict) -> List[Dict]:
    """fonction to get the work actions according to the area definition 

    Args:
        area_definition (Dict): dict defining the targeted area

    Returns:
        List: list of dict defining the work actions
    """
    query = qreg.build_work_by_area(area_definition)
    records = self._driver.run(query)
    return records
  
  def get_station_by_area(self, area_definition:Dict):
    """fonction to get the move station actions according to the area definition 

    Args:
        area_definition (Dict): dict defining the targeted area

    Returns:
        List: list of dict defining the move station actions
    """
    query = qreg.build_station_by_area(area_definition)
    records = self._driver.run(query)
    return records
  
  def get_approach_by_area(self, area_definition:Dict):
    """fonction to get the approach actions according to the area definition 

    Args:
        area_definition (Dict): dict defining the targeted area

    Returns:
        List: list of dict defining the approach actions
    """
    query = qreg.build_approach_by_area(area_definition)
    records = self._driver.run(query)
    return records
  
  def get_action_by_state(self, state_definition:Dict):
    """fonction to get the actions to move from a state (precondition) to an other (result)
      the precondition and the result are define in the state definition   

    Args:
        state_definition (Dict): dict defining precondition and result

    Returns:
        List: list of dict defining the action
    """
    query = qreg.build_action_by_state(state_definition)
    records = self._driver.run(query)
    return records

  def close(self):
    """close the dataunit object
    """
    self._driver.close()

class SequenceUnit():

  def __init__(self, data_unit:DataUnit):
    # data unit to get data
    self.__data_unit = data_unit
    
    # instantiate a sequence solver,
    # I pass a dataunit as parameter to it get the missing data
    self._solver = SequenceSolver(data_unit)
    self._logger = logging.getLogger('sequencer.processor')
    
  def build(self,
        sequence_type:SequenceTypeRegister,
        query_definition:Dict,
        states_definition:Dict,
        ) -> List[Dict]:
    """function to build a sequence of action according the user query definition
    and a initial situation (states definition)

    Args:
        sequence_type (SequenceTypeRegister): sequence type to build
        query_definition (Dict): user query
        states_definition (Dict): initial state

    Returns:
        List[Dict]: sequence of action definition
    """
    tb = time.time()
    self._logger.info('get goals from database')
    # get DataUnit function according sequence_type
    query_function = getattr(self.__data_unit, sequence_type.value)

    # get data from database
    records = query_function(query_definition)

    self._logger.info('build the sequence')
    # transform json data to actions
    self._logger.info('transform data to actions')
    actions = [Action.from_dict(action) for action in records]
    
    # sort action
    self._logger.info('sort actions')
    actions = sort_by_position(actions)


    # use the solver to resolve problem and produce sequence
    self._logger.info('solve the actions definition')
    sequence  = self._solver.resolve(actions, states_definition)

    # optimize the sequence
    # begin with all probing subsequence
    self._logger.info('optimize the sequence')
    sequence = begin_with_probing(sequence)

    tsequence = time.time()
    # transform to dict for json transfert
    json_sequence = [action.to_dict() for action in sequence]

    ttb = round(tsequence - tb, 2)
    self._logger.info(f'sequence builded - time to build sequence : {ttb} seconds')

    return json_sequence


class SequenceSolver:
    
    def __init__(self, data_unit:DataUnit):
        # dataunit to get data from database
        self._data_unit = data_unit
        # variable to store internal situation (list of states)
        self._situation:Situation = None
        # variable to store goals
        self._goals:Deque[Action] = None
        # variable to store initial situation
        self._init_situation = None
        # variable to store internal state definition
        self._history_state_def = None
        self._logger = logging.getLogger('sequencer.solver')

    def resolve(self, goals: List[Action],
            init_situation_definition:Dict) -> List[Action]:
      """fonction to resolve the problem : 
      from the initial situation, define all the actions to do
      to perform all the actions listed in the goals list 

      Args:
          goals (List[Action]): list of goals, action to perform
          init_situation_definition (Dict): initial situation

      Returns:
          List[Action]: list of action to perform all the goals 
      """
      # reverse the list of goals (the first action must be at the end) 
      # and cast list of goals to a queue
      self._goals = deque(goals[::-1])

      # get the robot and work situations
      robot_situation_definition = init_situation_definition['robot_situation']
      work_situation_definition = init_situation_definition['work_situation']
      
      # get the states definition (values)
      carrier_states = [sd for sd in robot_situation_definition.values()]
      work_states = [sd for sd in work_situation_definition.values()]
      
      # parse the list of states to get Situation objects
      self._situation = Situation.from_list(carrier_states+work_states)
      self._init_situation = Situation.from_list(carrier_states)

      # list to store actions
      plan_list = []

      # get the next goal
      action = self.__next_goal()

      # while the goals queue return an action
      while action:
        # if the action effect is not a the actual situation
        if not action.effect == self._situation:
          # if it's possible to perform the action (all preconditions are verified)
          if self.__poss(action):
            # do the action (update the actual situation) and append it to the plan list
            self.__do(action)
            plan_list.append(action)
            # get the next action in the goals queue
            action = self.__next_goal()
          else:
            # expand the action => explore the action and found other actions
            # to perform to verify all the conditions
            action = self.__expand(action)
      
      # return the plan list when all the goals are performed
      return plan_list
    
    def __next_goal(self)-> Action:
      """function to get the next action from the goals queue

      Returns:
          Action: next action of the goals queue
      """

      try:
          # return the next action of the goals queue
          return self._goals.pop()
      except IndexError as e:
        # raise if no more action in the goals queue
        # check if the system is in the initial situation
        if not self._situation == self._init_situation :
          # if not compare the situation and return the first different state (StateObject)
          # get the result (the value to reach) and the precondition (actual value)
          result_state, precondition_state = self._init_situation.compare(self._situation)
          
          # build a state definition object from precondition and result
          state_definition = SequenceSolver.__build_state_definition(precondition_state, result_state)
          
          # get the action to perform to reach the result from the precondition
          t_action = self.__get_action_from_db(state_definition)
          return t_action

    @staticmethod
    def __build_state_definition(precondition:StateObject, result:StateObject) -> Dict:
      """function to build a structured dict from a result and a precondition

      Args:
          precondition (StateObject): precondition state
          result (StateObject): result state

      Returns:
          Dict: structured definition
      """
      state_def={
          'uid':result.uid,
          'result': result.state,
          'precondition': precondition.state
      }
      return state_def

    def __expand(self, action:Action) -> Action:
      """function to expand an action.
      used when the precondition to perform the action are not verified.
      the function compare the actions preconditions with the actual situation
      and return the first action to perform to move to verified the action preconditions

      Args:
          action (Action): action to expand

      Raises:
          ProcessException: raise if no action exist to obtain the preconditions

      Returns:
          Action: the action to perform to obtain the precondition
      """
      self._logger.debug(f'expand the action {action}')
      # compare the action preconditions with actual situation, return the first different state
      result_state, precondition_state = action.preconditions.compare(self._situation)
      # build a state definition 
      state_definition = SequenceSolver.__build_state_definition(precondition_state, result_state)

      # condition to avoid infinite resolution
      # compare the actual statedef to the previous on (if exist)
      # and raise an error if equal
      if state_definition == self._history_state_def:
        raise ProcessException(['PROCESS', 'SOLVER', 'RESOLUTION'],
                                ProcessExceptionType.SOLVER_ERROR,
                                "unable to solve the problem: infinite resolution")
      else:
        # update the state_def history
        self._history_state_def = state_definition

      # request to db to get the action
      t_action = self.__get_action_from_db(state_definition)

      # if no action found in db, expand search 
      if not t_action: 
        print('action not found with initial situation, extend the search')
        self._logger.debug(f'expand the action {action}')
        # delete precondition parameter (keep only the result)
        del state_definition['precondition']
        # and do a new request
        t_action = self.__get_action_from_db(state_definition)

        # if no result, no action for state evolution in the database, raise an erro
        if not t_action :
            st_uid = state_definition.get('uid')
            st_res = state_definition.get('result')
            raise ProcessException(['PROCESS', 'SOLVER', 'RESOLUTION'],
                                    ProcessExceptionType.SOLVER_ERROR,
                                    f"unable to solve the problem: no action to update the state {st_uid} to {st_res}, check your database")
      # reinsert the actual action in the goals queue
      # and return the result of expand
      
      self._goals.append(action)
      return t_action

    def __poss(self, action:Action) -> bool:
      """function to check if the action can be performed
      compare the action precondition to actual situation

      Args:
          action (Action): action to check

      Returns:
          bool: true if all precondition are verified else false
      """
      poss = action.preconditions == self._situation
      self._logger.debug(f'possibility to perform action {action} -> {poss}')
      return poss

    
    def __do(self, action:Action):
      """function to perform an action => update the actual situation

      Args:
          action (Action): action to perform
      """
      self._logger.debug(f"perform the action {action}")

      for result in action.results:
          self._situation.update(result)
    
    def __get_action_from_db(self, states_definition:Dict) -> Union[Action, None]:
      """function to get an action from the database.
      return the action which have, for a state, the precondition and result
      defined in the state definition

      Args:
          states_definition (Dict): object describing the state to change

      Returns:
          Action|None: the action to perform to change the state or None if no action found
      """
      self._logger.debug(f"search in DB the action in db solving situation {states_definition}")
      records = self._data_unit.get_action_by_state(states_definition)
      
      if len(records) > 0:
        action = Action.from_dict(records[0])
        self._logger.debug(f"action found : {action}")
        return Action.from_dict(records[0])
      else:
        return None
