from importlib.resources import path
from lib2to3.pgen2.pgen import DFAState
from msilib import sequence
from exceptions import ConfigError
from typing import Dict, Tuple
from flask import request, abort

from server.http_server import HttpServer
from server.validation import Validator
from server.exceptions import ServerConfigError

# from config import Config, KeyNotFoundError as KeyConfigError
import json
import yaml
import sys
from enum import Enum
import glob
import re

# from db.neo4j import Neo4jDriver, StateObjectEnum, build_match_query

import os
from dotenv import load_dotenv

from processor.components import DataUnit, SequenceUnit, SequenceTypeRegister

load_dotenv()
data_unit:DataUnit = None
sequence_unit:SequenceUnit = None
DEFAULT_SITUATION_DEFINITION = None
DEFAULT_GOALS_DEFINITION =None


def build_sequence():
  
  # get request body
  request_body = request.get_json()

  #get definitions from request body
  situation_definition = build_situation_definition(request_body)
  definition_type, goals_definition = build_goals_definition(request_body)
  
  # read target from path /sequence/$target
  target = re.search('\w+$', request.path).group()

  #initialize squence_type
  sequence_type = f'{target}_{definition_type}'

  # build sequence
  json_sequence = sequence_unit.build(SequenceTypeRegister[sequence_type],
                      goals_definition,
                      situation_definition)
  
  # return sequence under json form
  return json_sequence

def build_situation_definition(request_body:Dict):

  temp_situation = DEFAULT_SITUATION_DEFINITION.copy()

  # if situation info in request
  # read situation info from request and update standard
  if request_body and request_body.get('initialSituation'):

    request_situation = request_body.get('initialSituation')

    work_situation:Dict = request_body['initialSituation'].get('workSituation')
    robot_situation:Dict = request_situation['initialSituation'].get('robotSituation')

    if work_situation:
      for state, value in work_situation.items():
        temp_situation['work_situation'][state]['state']=value
        temp_situation['work_situation'][state]['relation']='eq'
    
    if robot_situation:
      for state, value in robot_situation.items():
        temp_situation['robot_situation'][state]['state']=value
        temp_situation['robot_situation'][state]['relation']='eq'

  return temp_situation

def build_goals_definition(request_body:Dict) -> Tuple[str, Dict]:
  temp_goals = DEFAULT_GOALS_DEFINITION.copy()

  if request_body and request_body.get('goalsDefinition'):   

    definition_type = request_body['goalsDefinition']['definitionType']
    temp_goals = DEFAULT_GOALS_DEFINITION[definition_type]

    definition:Dict = request_body['goalsDefinition'].get('definition')
    if definition:
      for def_key, value in definition.items():
        temp_goals[def_key] = value

    return definition_type, temp_goals

  else:
    default_type = DEFAULT_GOALS_DEFINITION['defaultType']
    return default_type, DEFAULT_GOALS_DEFINITION[default_type]


# get env var for configuration
NEO_URI = os.getenv('DB_URI')
NEO_USER  = os.getenv('DB_USERNAME')
NEO_PASSWD = os.getenv('DB_PASSWORD')
SERVER_HOST = os.getenv('SERVER_HOST')
SERVER_PORT = os.getenv('SERVER_PORT')
SCHEMA_DIR = os.getenv('SCHEMA_DIR')
CONFIG_DIR = os.getenv('CONFIG_DIR')
# CONSTANT_REGISTER = os.getenv('CONSTANT_REGISTER')

# check env var not none, add default value if necessary
SERVER_PORT = SERVER_PORT if SERVER_PORT else 8001
SERVER_HOST = SERVER_HOST if SERVER_HOST else 'localhost'
NEO_URI = NEO_URI if NEO_URI else 'bolt://localhost:7687'
SCHEMA_DIR = SCHEMA_DIR if SCHEMA_DIR else './schemas/'
CONFIG_DIR = CONFIG_DIR if CONFIG_DIR else './config/'

# CONSTANT_REGISTER = CONSTANT_REGISTER if CONSTANT_REGISTER else './constant.yaml'

try:
  # check the neo4j authentification parameters
  if not NEO_USER and not NEO_PASSWD:
    raise ConfigError("DATABASE.AUTH", "Neo4J authentification parameters are missing")
  
  # check the if the validation schema exist
  if not os.path.isdir(SCHEMA_DIR):
    raise ConfigError("VALIDATION.SCHEMA", f"Validation schema folder not found")

  # initialize validator to validate request
  request_validator = Validator()

  # import schemas present in schema directory in validator
  # list the .schema.json file in directory
  for file in glob.glob(f"{SCHEMA_DIR}/*.schema.json"):
    with open(file, 'r') as schema_file:
      content = schema_file.read()
      schema = json.loads(content)

      # get the paths to validate with schema
      # schema must contain a $paths key containing the paths to validate with the schema
      # if not raise a config error
      path_list = schema.get('$paths')
      if not path_list:
        raise ConfigError("VALIDATION_SCHEMA", f"Validation schema file {file} is not valid, key '$paths' is missing")
      
      # add the schema for each path
      for path in path_list:
        request_validator.add_schema(path, schema)

  # get the default initial situation in config folder 
  with open(CONFIG_DIR+'situation.default.yaml', 'r') as sdf:
    content = sdf.read()
    DEFAULT_SITUATION_DEFINITION = yaml.load(content, Loader=yaml.Loader)
  # get the default goals definition in config folder
  with open(CONFIG_DIR+'goals.default.yaml', 'r') as gdf:
    content = gdf.read()
    DEFAULT_GOALS_DEFINITION = yaml.load(content, Loader=yaml.Loader)

  # initialize the DataUnit for db communications
  data_unit = DataUnit(NEO_URI, (NEO_USER, NEO_PASSWD))
  # initialize the sequence_unit for sequence building
  sequence_unit = SequenceUnit(data_unit)

  '''
  with open(CONSTANT_REGISTER, 'r') as constant_file:
    content = constant_file.read()
    constant_register = yamlload(content, Loader=Loader)
  '''

  '''
  #init neo4j driver
  neo4j_driver = Neo4jDriver(NEO_URI, NEO_USER, NEO_PASSWD)
  neo4j_queries = constant_register['neo4j']['query_reg']
  

  for name, query in neo4j_queries.items():
    neo4j_driver.add_query_in_reg(name, query)

  Solver.DB_DRIVER = neo4j_driver

  solver = Solver()

  init_state_list = constant_register['init_situation'].values()
  init_situation = Situation.from_list(init_state_list)
  '''

  # read the server configuration from configuration files
  # server_config = Config(config_file_path)
  # SERVER_PORT = server_config['server.port']
  # SERVER_HOST = server_config['server.host']

  # init http server with validator
  server = HttpServer("build_processor_http", request_validator)
  
  # server.add_endpoint('/sequence/approach', 'approach', build_sequence, methods=['GET'])
  # server.add_endpoint('/sequence/station', 'station', build_sequence, methods=['GET'])
  # server.add_endpoint('/sequence/work', 'work', build_sequence, methods=['GET'])
  
  # add the url the server have to listen with
  server.add_endpoint('/sequence/approach',
                      'approach',
                      build_sequence,
                      methods=['GET'])
  server.add_endpoint('/sequence/station',
                      'station',
                      build_sequence,
                      methods=['GET'])
  server.add_endpoint('/sequence/work',
                      'work',
                      build_sequence,
                      methods=['GET'])

  server.run(SERVER_HOST, SERVER_PORT)

except ServerConfigError as error:
  print(error.message)
  sys.exit(1)
except ConfigError as error:
  print("environment variablex DB_USERNAME or DB_PASSWORD is missing")
  sys.exit(1)
except yaml.error.MarkedYAMLError as error:
  # raise if error on yaml config file
  print('error on yaml config file')
  sys.exit(1)
except FileNotFoundError as error:
  print ('missing config file : {error}')
  sys.exit(1)

  
# except FileNotFoundError as error:
  #print(f"constant register file {CONSTANT_REGISTER} not found")
  # sys.exit(1)
#except AttributeError as error:
#  print(f"parameter is missing, control the CONSTANT_REGISTER file :{CONSTANT_REGISTER}\n{error}")
'''
except KeyConfigError as error:
  print("One or several keys are missing in configuration file.")
  print(error.args[0])
  sys.exit(1)
'''
