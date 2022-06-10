from enum import Enum, EnumMeta
from typing import Dict, List
from .marsnode import Action

# init area order constants
AIRCRAFT_RAIL_ORDER = ("y+1292", "y+763", "y+254", "y-254", "y-763", "y-1292")
RAIL_SIDE_ORDER = ("right", "left")
RAIL_AREA_ORDER = ("flange", "web")
CROSSBEAM_SIDE_ORDER = ("front", "rear")


class EnumScoreInterface(Enum):
  """
    Interface to hanlde automatic value generation for Enum attributes
    the value generated is the insertion order 
  """
  @classmethod
  def __new__(cls):
    value = len(cls.__members__) + 1
    obj = object.__new__(cls)  # this is the only change from above
    return obj


class EnumChainingInterface(EnumMeta):
  """
    Interface to handle Enum chaining call
  """
  def __getitem__(self, name):
    return super().__getitem__(name).value


class ScoreCalculator:
  """
     Object to calculate the score
  """
  def __init__(self, name, ordered_keys, coeff):
    """ instanciation function

    Args:
        name (str): calculator name
        ordered_keys (List[str] | Tuple[str]): list of key to integrate in the calculator.
        ordered by value 
        coeff (int): coefficient to applicate for score calculation
    """
    keys = []
    for k in ordered_keys:
      if '+' in k:
          keys.append(k.replace('+', 'p'))
      elif '-' in k:
          keys.append(k.replace('-', 'm'))
      else:
          keys.append(k)
    self._enum = Enum(name, keys, module=EnumScoreInterface)
    self._coeff = coeff

  def __getitem__(self, name):
    if '+' in name:
      key = name.replace('+', 'p')
    elif '-' in name:
      key = name.replace('-', 'm')
    else:
      key = name
    value = self._enum.__getitem__(key).value
    return self._coeff * value


class AreaScore(Enum, metaclass=EnumChainingInterface):
  aircraft_rail = ScoreCalculator('aircraft', AIRCRAFT_RAIL_ORDER, coeff=100)
  rail_side = ScoreCalculator('rail_side', RAIL_SIDE_ORDER, coeff=1)
  rail_area = ScoreCalculator('rail_area', RAIL_AREA_ORDER, coeff=1000)
  crossbeam_side = ScoreCalculator('crossbeam_side', CROSSBEAM_SIDE_ORDER, coeff=10)


class AreaComponent(object):
  def __init__(self, value:str, score:int=0):
    self._value = value
    self._score = score

  @property
  def score(self):
    return self._score
  
  @property
  def value(self):
    return self._value


class Area(object):
  """
   Object describing the area for scoring calculation
  """
  def __init__(self, aircraft_rail:AreaComponent,
               rail_area:AreaComponent,
               crossbeam_side:AreaComponent=None,
               rail_side:AreaComponent=None):
    self._aircraft_rail = aircraft_rail
    self._rail_area = rail_area
    self._rail_side = rail_side
    self._crossbeam_side = crossbeam_side

  @property
  def score(self):
    """Return the score calculate for the area (sum of score of each components)
    Returns:
        int: area score
    """
    crossbeam_side_score =  self._crossbeam_side.score if self._crossbeam_side else 0
    rail_side_score = self._rail_side.score if self._rail_side else 0

    return self._aircraft_rail.score \
          + self._rail_area.score \
          + rail_side_score \
          + crossbeam_side_score

  @property
  def rail_area(self):
    return self._rail_area

  @property
  def aircraft_rail(self):
    return self._aircraft_rail

  @property
  def rail_side(self):
    return self._rail_side
  
  @property
  def crossbeam_side(self):
    return self._crossbeam_side

  @staticmethod
  def parse(area_list:List[Dict]):
    """function to parse a list of area components Dict and instanciate an Area Object instance

    Args:
        area_list (List[Dict]): list of Dict describing the area components

    Returns:
        Area: the Area object described by the list of dict
    """

    area = {}

    for a in area_list:
      key = f"{a['reference']}_{a['type']}"
      name = a['uid']
      value = AreaScore[key][name]
      area[key] = AreaComponent(name, value)

    instance = Area(area.get('aircraft_rail'),
                    area.get('rail_area'),
                    area.get('crossbeam_side'),
                    area.get('rail_side'))

    return instance


class Coordinates:
  """
    Object describing coordinates for scoring calculation
  """
  COORDINATES_REF_MODIF = {"x": -15100, "y": 0, "z":555}
  COORDINATES_COEFF = {"x": 10**-3, "y": 0, "z":0}

  def __init__(self, x:int, y:int, z:int):
    self._x_score = x
    self._y_score = y
    self._z_score = z
  
  @property
  def score(self):
    return self._x_score \
          + self._y_score \
          + self._z_score

  @staticmethod
  def parse(coordinates:Dict, reverse=False):
    c = coordinates.copy()
    Coordinates.__realign_ref(c)
    Coordinates.__apply_coeff(c)
    if reverse:
      Coordinates.__reverse_score(c)
    return Coordinates(c['x'], c['y'], c['z'])

  @staticmethod
  def __realign_ref(coordinates:Dict):
    coordinates["x"] = coordinates["x"] + Coordinates.COORDINATES_REF_MODIF["x"]
    coordinates["y"] = coordinates["y"] + Coordinates.COORDINATES_REF_MODIF["y"]
    coordinates["z"] = coordinates["z"] + Coordinates.COORDINATES_REF_MODIF["z"]
  
  @staticmethod 
  def __apply_coeff(coordinates:Dict):
    coordinates["x"] = int(coordinates["x"]) * Coordinates.COORDINATES_COEFF["x"]
    coordinates["y"] = int(coordinates["y"]) * Coordinates.COORDINATES_COEFF["y"]
    coordinates["z"] = int(coordinates["z"]) * Coordinates.COORDINATES_COEFF["z"]
  
  @staticmethod
  def __reverse_score(coordinates):
    coordinates["x"] = 1-coordinates["x"]
  

class Position:

  def __init__(self, area:Area, coordinates:Coordinates):
    self._area = area
    self._coordinates = coordinates
  
  @property
  def score(self):
    coodinates_score = self._coordinates.score if self._coordinates else 0
    return self._area.score \
          + coodinates_score

  @staticmethod
  def parse(position:Dict):
    
    area = Area.parse(position['areas'])
    coordinates = position.get('coordinates')
    
    if coordinates:
      if area.crossbeam_side.value == "rear" and\
        area.rail_area.value == 'flange':
        reverse = True
      else: 
        reverse = False
      
      coordinates = Coordinates.parse(position['coordinates'],
                                      reverse=reverse)

    return Position(area, coordinates)


def __get_position_score(action_pos_tuple):
  score = action_pos_tuple[1].score
  return score

def sort_by_position(action_list:List[Action]):
  
  action_pos_score = []

  for action in action_list:
    position = action.get_metadata('position')
    if not position :
      raise Exception('no position at disposal for action')
    position = Position.parse(position)

    action_pos_score.append((action, position))
  
  action_pos_score.sort(key=__get_position_score)
  
  sorted_action = [acpos[0] for acpos in action_pos_score]

  return sorted_action
