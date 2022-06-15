from glob import glob
from typing import Dict, Tuple
from exceptions import BaseExceptionType, BaseException
from server.http import HttpServer, EFunction
from server.amqp import AMQPServer, CPipeline, CFunction
from server.exceptions import ServerException
from server.validation import Validator
from utils import get_config_from_file, get_validation_schemas
import re
import os
import sys
import logging

from dotenv import load_dotenv
from processor.components import DataUnit, SequenceUnit, SequenceTypeRegister

load_dotenv()

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOGGER = logging.getLogger("cmd_generator")
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)

# init global var
DATA_UNIT:DataUnit = None
SEQUENCE_UNIT:SequenceUnit = None

DEFAULT_SITUATION_DEFINITION = None
DEFAULT_GOALS_DEFINITION = None

# get neo4j credentials => env var
NEO_USER  = os.getenv('DB_USERNAME')
NEO_PASSWD = os.getenv('DB_PASSWORD')
# get server configuration file path
__SERVER_CONFIG_FILE = os.getenv('SERVER_CONFIG')
__SERVER_CONFIG_FILE = __SERVER_CONFIG_FILE if __SERVER_CONFIG_FILE else './config/server.yaml'

# get validation schema directory
__VALIDATION_SCHEMA_DIR = os.getenv('VALIDATION_SCHEMA_DIR')
__VALIDATION_SCHEMA_DIR = __VALIDATION_SCHEMA_DIR if __VALIDATION_SCHEMA_DIR else './schemas'

# mars config file
__MARS_CONFIG_FILE = os.getenv('MARS_CONFIG')
__MARS_CONFIG_FILE = __MARS_CONFIG_FILE if __MARS_CONFIG_FILE else './config/mars.yaml'

# amqp topics
__AMQP_TOPICS = "request.build_processor", "report.build_processor"

def build_sequence(body:Dict,
                   headers:Dict,
                   path:str,
                   query_args:Dict):
  
  global SEQUENCE_UNIT

  #get definitions from request body
  situation_definition = build_situation_definition(body)
  definition_type, goals_definition = build_goals_definition(body)
  
  # read target from url /sequence/$target
  target = re.search('\w+$', path).group()

  #define sequence_type
  sequence_type = f'{target}_{definition_type}'

  # build sequence
  json_sequence = SEQUENCE_UNIT.build(SequenceTypeRegister[sequence_type],
                                      goals_definition,
                                      situation_definition)
  body = {
    "sequence": json_sequence
  }

  # return sequence under json form
  return body, headers

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

def get_http_para_from_config(http_config:Dict) -> Tuple[str, int]:
  try:
    host = http_config['host']
    port = http_config['port']
    return host, port
  except KeyError as error:
    raise BaseException(["SERVER", "HTTP"],
                        BaseExceptionType.CONFIG_NOT_CONFORM,
                        f"http server config is not conform, {error.args[0]} parameter is missing")

def build_amqp_server(amqp_config:Dict):
  try:
    host = amqp_config['host']
    port = amqp_config['port']
    exchange = amqp_config['exchange']
    ex_name = exchange['name']
    ex_type = exchange['type']

    server = AMQPServer(name="command_generator",
                            host=host,
                            port=port,
                            exchange_name=ex_name,
                            exchange_type=ex_type)
                            
    return server

  except KeyError as error:
    missing_key = error.args[0]
    raise BaseException(['CONFIG', 'SERVER', 'AMQP'],
                        BaseExceptionType.CONFIG_NOT_CONFORM,
                        f"the amqp configuration parameter {missing_key} is missing")

  except ServerException as error:
    error.add_in_stack(['INIT','SERVER'])
    raise error

def build_validator(schemas_dict:Dict)-> Validator:
  # instanciate validator to validate request 
  validator = Validator()
  # add all schemas in the validation object
  for path, schema in schemas_dict.items():
    validator.add_schema(path, schema)
  
  return validator
    

def main():

  global DATA_UNIT, SEQUENCE_UNIT, DEFAULT_SITUATION_DEFINITION, DEFAULT_GOALS_DEFINITION

  HTTP_SERVER:HttpServer = None
  AMQP_SERVER:AMQPServer = None

  try:
    # check the neo4j authentification parameters
    assert NEO_USER and NEO_PASSWD,\
           (("DB", "CREDENTIALS"),
            "neo4j credentials parameters are missing, check NEO_USER and NEO_PASSWD environment variables")
    assert os.path.isdir(__VALIDATION_SCHEMA_DIR),\
                         (("VALIDATION_SCHEMA"),
                          f"Validat+ion schema directory {__VALIDATION_SCHEMA_DIR} not found")
    

    # get validations schemas stored in __VALIDATION_SCHEMA_DIR
    schemas_dict = get_validation_schemas(__VALIDATION_SCHEMA_DIR)
    # build the validator object
    request_validator = build_validator(schemas_dict)

    # TODO implement json schema for all configuration files
    # get mars configuration
    MARS_CONFIG =  get_config_from_file(__MARS_CONFIG_FILE)
    
    # get default situation and goals from mars configuration
    DEFAULT_SITUATION_DEFINITION = MARS_CONFIG['default_parameters']['situations']
    DEFAULT_GOALS_DEFINITION = MARS_CONFIG['default_parameters']['goals']

    # get database configuration from mars configuration
    DATABASE_CONFIG = MARS_CONFIG['database']

    # initialize the DataUnit in charge of the db communications 
    DATA_UNIT = DataUnit(host_uri=DATABASE_CONFIG['uri'],
                         auth=(NEO_USER, NEO_PASSWD))

    # initialize the SEQUENCE_UNIT in charge of the processing
    # DATA_UNIT in parameter for db communication
    SEQUENCE_UNIT = SequenceUnit(data_unit=DATA_UNIT)

    # load the servers config
    SERVER_CONFIG = get_config_from_file(__SERVER_CONFIG_FILE)
    http_config = SERVER_CONFIG.get('http')
    amqp_config = SERVER_CONFIG.get('amqp')

    # TODO implement multithreading if two activated server
    # if http server activate in configuration
    if http_config and http_config.get('activate'):
      LOGGER.info("build http server")
      HTTP_HOST, HTTP_PORT = get_http_para_from_config(http_config)
      HTTP_SERVER = HttpServer(name='build_processor',
                               validator=request_validator)
      
      LOGGER.info("configure http server")
      HTTP_SERVER.add_endpoint('/sequence/approach',
                      'approach',
                      EFunction(build_sequence),
                      methods=['GET'])
      HTTP_SERVER.add_endpoint('/sequence/station',
                      'station',
                      EFunction(build_sequence),
                      methods=['GET'])
      HTTP_SERVER.add_endpoint('/sequence/work',
                      'work',
                      EFunction(build_sequence),
                      methods=['GET'])

    #if amqp server activate in the configuration
    if amqp_config and amqp_config.get('activate'):
      LOGGER.info("build amqp server")
      AMQP_SERVER = build_amqp_server(amqp_config)

      LOGGER.info('configure amqp server')
      AMQP_SERVER.add_queue(label="request_report",
                            topics=__AMQP_TOPICS)

      # prepare a consumer pipeline
      # no topic parameter for publish => report_topic contained in the message header
      req_pipeline = CPipeline([CFunction(build_sequence),
                                CFunction(AMQP_SERVER.publish)])
      
      AMQP_SERVER.add_consumer('request.build_processor', req_pipeline)
    
    # if no server activated, raise an error
    if not HTTP_SERVER and not AMQP_SERVER:
      raise BaseException(['CONFIG', 'SERVER'],
                          BaseExceptionType.CONFIG_NOT_CONFORM,
                          "no server activated, check the configuration")

    if AMQP_SERVER:
      # run amqp server on the current tread
      LOGGER.info('run amqp server and wait for messages')
      AMQP_SERVER.run()
    
    if HTTP_SERVER:
      # run http server on the current tread
      LOGGER.info('run http server and wait for messages')
      HTTP_SERVER.run(HTTP_HOST, HTTP_PORT)

  except BaseException as error:
    error.add_in_stack(['INIT'])
    raise error
  except AssertionError as error:
    origin, message = error.args[0]
    raise BaseException(['CONFIG'].extend(origin),
                        BaseExceptionType.CONFIG_MISSING,
                        message) 
  except KeyError as error:
    missing_key = error.args[0]
    raise BaseException(['CONFIG'],
                        BaseExceptionType.CONFIG_NOT_CONFORM,
                        f"configuration is not conform, parameter {missing_key} is missing")

if __name__ == '__main__':
  exit_code = 0
  try:
    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
    LOGGER.info("run build_processor service")
    main()
  except BaseException as error:
    LOGGER.fatal(error.describe())
    exit_code=1
  except KeyboardInterrupt as error:
    LOGGER.info("manual interruption")
  except Exception as error:
    LOGGER.fatal(error)
  finally:
    if DATA_UNIT:
      DATA_UNIT.close()
    sys.exit(exit_code)

