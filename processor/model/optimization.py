

from typing import List
from .marsnode import Action
import re

ACTION_TYPE_CODE = {
    'LOAD.EFFECTOR':'E',
    'MOVE.STATION.TOOL' : 'T',
    'MOVE.STATION.WORK' : 'S',
    'MOVE.TCP.APPROACH' : 'A',
    'MOVE.TCP.CLEARANCE' : 'C',
    'MOVE.TCP.WORK' : 'W',
    'UNLOAD.EFFECTOR' : 'E',
    'WORK.PROBE' : 'P',
    'MOVE.STATION.HOME' : 'H'}

# probing schema (regex)
PROBE_SCHEMA = '(TE){0,1}SAPC'
REPETITIVE_LU_TOOL_SCHEMA = 'TEETEE'

def __delete_recursive_lu_tool(sequence:List[Action]):
  str_code_sequence = ''.join([ACTION_TYPE_CODE[action.type] for action in sequence])
  rep_lu_tool_it = re.finditer(REPETITIVE_LU_TOOL_SCHEMA, str_code_sequence)

  for match in rep_lu_tool_it:
    # get the begin index
    begin = match.start()
    end = match.end()

    del sequence[begin:end]


def __move_sequence_by_schema(schema:str, sequence:List[Action], to_index:int):
  # empty list to store elements found using schema
  found_sequence = []
  # empty list tot store other elements
  other_sequence = []

  # transform list of action to a string containing one code lettre for each action
  # according their type
  str_code_sequence = ''.join([ACTION_TYPE_CODE[action.type] for action in sequence])

  # find schema in str -> return an iterator
  found_sequence_it = re.finditer(schema, str_code_sequence)

  #initilize var to 0
  end = 0
  begin = 0

  # for each match element found 
  for match in found_sequence_it:
    # get the begin index
    begin = match.start()
    # put the sublist end last match -> begin new match in other
    other_sequence.extend(sequence[end:begin])

    # get the end index
    end = match.end()
    # put the sublist begin new match -> end new match in found
    found_sequence.extend(sequence[begin:end])
  
  other_sequence.extend(sequence[end:])

  # 
  __delete_recursive_lu_tool(other_sequence)
  
  # return a sequence with found element inerted at the wanted index
  return other_sequence[:to_index]+found_sequence+other_sequence[to_index:]


def begin_with_probing(sequence:List[Action]):
  return __move_sequence_by_schema(PROBE_SCHEMA, sequence, to_index=0)
