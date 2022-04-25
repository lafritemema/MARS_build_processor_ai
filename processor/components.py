
from enum import Enum

from processor.model.marsnode import Action
from .db.drivers import Neo4jDriver
from .db.queries import register as qreg
from .model.scoring import sort_by_position
from .model.situation import Situation
from exceptions import BaseError
from typing import List, Dict, Deque
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

  def __init__(self, host_uri:str, auth:tuple):
    self._driver = Neo4jDriver(host_uri, auth[0], auth[1])
  
  def get_work_by_area(self, area_definition:Dict):
    query = qreg.build_work_by_area(area_definition)
    records = self._driver.run(query)
    return records
  
  def get_station_by_area(self, area_definition:Dict):
    query = qreg.build_station_by_area(area_definition)
    records = self._driver.run(query)
    return records
  
  def get_approach_by_area(self, area_definition:Dict):
    query = qreg.build_approach_by_area(area_definition)
    records = self._driver.run(query)
    return records
  
  def get_action_by_state(self, state_definition:Dict):
    query = qreg.build_action_by_state(state_definition)
    records = self._driver.run(query)
    return records

class SequenceUnit():

  def __init__(self, data_unit:DataUnit):
    self.__data_unit = data_unit
    self._solver = SequenceSolver(data_unit)
    
  def build(self,
        sequence_type:SequenceTypeRegister,
        query_definition:Dict,
        states_definition:Dict,
        ):

    print('sequence construction ...')
    tb = time.time()
    print('get data')
    # get DataUnit function according sequence_type
    query_function = getattr(self.__data_unit, sequence_type.value)

    # get data from database
    records = query_function(query_definition)
    tdata = time.time()

    print('build sequence')
    # transform json data to actions
    actions = [Action.from_dict(action) for action in records]

    # sort action
    actions = sort_by_position(actions)

    # get sequence from solver
    sequence  = self._solver.resolve(actions, states_definition)

    # optimize the sequence
    # begin with all probing subsequence
    sequence = begin_with_probing(sequence)

    tsequence = time.time()
    # transform to dict for json transfert
    json_sequence = [action.to_json() for action in sequence]

    print('end of process')
    print('time to get data : ', tdata - tb)
    print('time to build sequence : ', tsequence - tb)

    return json_sequence


class ModelSolverError(BaseError):
    def __init__(self, message):
        super().__init__(message)


class SequenceSolver:
    
    def __init__(self, data_unit:DataUnit):
        self._data_unit = data_unit
        # self._state_objects:Dict[str, StateObject] = OrderedDict()
        self._situation:Situation = None
        self._goals:Deque[Action] = None
        self._init_situation = None
        self._history_state_def = None

    def resolve(self, goals: List[Action],
            init_situation_definition:Dict):

        self._goals = deque(goals[::-1])

        robot_situation_definition = init_situation_definition['robot_situation']
        work_situation_definition = init_situation_definition['work_situation']
        carrier_states = [sd for sd in robot_situation_definition.values()]
        work_states = [sd for sd in work_situation_definition.values()]

        self._situation = Situation.from_list(carrier_states+work_states)
        self._init_situation = Situation.from_list(carrier_states)

        plan_list = []

        action = self.__next_goal()

        while action:
            if not action.effect == self._situation:
                if self.__poss(action):
                    self.__do(action)
                    plan_list.append(action)
                    action = self.__next_goal()
                else:
                    action = self.__expand(action)
        
        return plan_list
    
    def __next_goal(self):
        try:
            return self._goals.pop()
        except IndexError as e:
            if not self._situation == self._init_situation :
                result_state, precondition_state = self._init_situation.compare(self._situation)
                state_definition = SequenceSolver.__build_state_definition(precondition_state, result_state)

                t_action = self.__get_action_from_db(state_definition)
                return t_action

    @staticmethod
    def __build_state_definition(precondition:StateObject, result:StateObject):
        state_def={
            'uid':result.uid,
            'result': result.state,
            'precondition': precondition.state
        }
        return state_def

    def __expand(self, action:Action):
        result_state, precondition_state = action.preconditions.compare(self._situation)
        state_definition = SequenceSolver.__build_state_definition(precondition_state, result_state)

        # condition to avoid infinite resolution
        if state_definition == self._history_state_def:
            raise ModelSolverError("abort infinite resolution")
        else:
            self._history_state_def = state_definition

        t_action = self.__get_action_from_db(state_definition)
        
        if not t_action:
            
            del state_definition['precondition']
            t_action =self.__get_action_from_db(state_definition)
            
            if not t_action :
                raise ModelSolverError(f"no action found for state : {state_definition}")

        self._goals.append(action)
        return t_action

    def __poss(self, action:Action):
        return action.preconditions == self._situation
    
    def __do(self, action:Action):
        for result in action.results:
            self._situation.update(result)
    
    def __get_action_from_db(self, states_definition:Dict):
        records = self._data_unit.get_action_by_state(states_definition)

        if len(records) > 0:
            return Action.from_dict(records[0])

