from ast import arg
from glob import glob
from typing import Dict, Tuple
from exceptions import BaseExceptionType, BaseException
from server.http import HttpServer, EFunction
from server.amqp import AMQPServer, CPipeline, CFunction
from server.exceptions import ServerException
from server.validation import Validator
from utils import GetAttrEnum, GetItemEnum, get_config_from_file, get_validation_schemas
import re
import os
import sys
import logging
import argparse
from enum import Enum
from dotenv import load_dotenv
from processor.components import DataUnit, SequenceUnit, SequenceTypeRegister
from functools import partial

load_dotenv()

__VALIDATION_SCHEMA_DIR = './schemas'
__SERVER_CONFIG_FILE = './config/server.yaml'
__MARS_CONFIG_FILE = './config/mars.yaml'

# init global var
DATA_UNIT:DataUnit = None
SEQUENCE_UNIT:SequenceUnit = None

DEFAULT_SITUATION_DEFINITION = None
DEFAULT_GOALS_DEFINITION = None

# get neo4j credentials => env var
DB_USER  = os.getenv('DB_USERNAME')
DB_PASSWD = os.getenv('DB_PASSWORD')

# amqp topics
__AMQP_TOPICS = "request.build_processor", "report.build_processor"

class ConfigLoader(argparse.Action):
  def __call__(self, parser, namespace, values, option_strings=None) -> Dict:
    try:
      if '--environment-config' in option_strings:
        return get_config_from_file(values)
      elif '--validation-schemas' in option_strings:
        assert os.path.isdir(values)
        # get validations schemas stored in __VALIDATION_SCHEMA_DIR
        return get_validation_schemas(values)
    except BaseException as error:
      error.add_in_stack(['CONFIG'])
      raise error
    except AssertionError as error:
      raise BaseException(["CONFIG", "VALIDATION_SCHEMA"],
                        BaseExceptionType.CONFIG_MISSING,
                        f"validation schema directory {values} not found") 


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
    "buildProcess": json_sequence
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
    

def main(activated_server:str,
         server_config:str,
         environment_config:str,
         validation_schemas:str,
         db_auth):

  global DATA_UNIT, SEQUENCE_UNIT, DEFAULT_SITUATION_DEFINITION, DEFAULT_GOALS_DEFINITION

  HTTP_SERVER:HttpServer = None
  AMQP_SERVER:AMQPServer = None

  try:
        
    # build the validator object
    request_validator = build_validator(validation_schemas)

    # TODO implement json schema for all configuration files
    
    # get default situation and goals from mars configuration
    DEFAULT_SITUATION_DEFINITION = environment_config['default_parameters']['situations']
    DEFAULT_GOALS_DEFINITION = environment_config['default_parameters']['goals']

    # get database configuration from mars configuration
    DATABASE_CONFIG = environment_config['database']

    # initialize the DataUnit in charge of the db communications 
    DATA_UNIT = DataUnit(host_uri=DATABASE_CONFIG['uri'],
                         auth=db_auth)

    # initialize the SEQUENCE_UNIT in charge of the processing
    # DATA_UNIT in parameter for db communication
    SEQUENCE_UNIT = SequenceUnit(data_unit=DATA_UNIT)

    http_config = server_config.get('http')
    amqp_config = server_config.get('amqp')

    if activated_server == 'amqp' and amqp_config:
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

    # TODO implement multithreading if two activated server
    # if http server activate in configuration
    elif activated_server == 'http' and http_config :
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
  except KeyError as error:
    missing_key = error.args[0]
    raise BaseException(['CONFIG'],
                        BaseExceptionType.CONFIG_NOT_CONFORM,
                        f"configuration is not conform, parameter {missing_key} is missing")

if __name__ == '__main__':
  exit_code = 0
  try:
    
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOGGER = logging.getLogger("cmd_generator")

    parser = argparse.ArgumentParser()
    parser.add_argument('-v', "--verbose", action='store_true')
    parser.add_argument('-s', '--server',
                        type=str,
                        choices=['amqp', 'http'],
                        default='amqp',
                        help='type of server used for communications')
    
    parser.add_argument('--server-config',
                        type=str,
                        nargs=1,
                        action=ConfigLoader,
                        help='path of server configuration yaml file')

    parser.add_argument('--environment-config',
                        type=str,
                        nargs=1,
                        action=ConfigLoader,
                        help='path of environment configuration yaml file')
    
    parser.add_argument('--validation-schemas',
                        type=str,
                        nargs=1,
                        action=ConfigLoader,
                        help='path of the directory contains schemas for requests validations')

    args = parser.parse_args()
    args.validation_schemas = get_validation_schemas(__VALIDATION_SCHEMA_DIR)\
                              if not args.validation_schemas else args.validation_schemas
    args.server_config = get_config_from_file(__SERVER_CONFIG_FILE)\
                         if not args.server_config else args.server_config
    args.environment_config = get_config_from_file(__MARS_CONFIG_FILE)\
                              if not args.environment_config else args.environment_config
    
    DB_USER  = os.getenv('DB_USERNAME')
    DB_PASSWD = os.getenv('DB_PASSWORD')

    assert DB_USER and DB_PASSWD, "missing database authentification parameters DB_USERNAME and/or DB_PASSWORD"

    
    if args.verbose:
      logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
    else:
      logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)

    LOGGER.info("run build_processor service")
    main(activated_server=args.server,
         server_config=args.server_config,
         environment_config=args.environment_config,
         validation_schemas=args.validation_schemas,
         db_auth=(DB_USER, DB_PASSWD))
  
  except BaseException as error:
    LOGGER.fatal(error.describe())
    exit_code=1
  except AssertionError as error:
    message = error.args[0]
    LOGGER.fatal(message)
  except KeyboardInterrupt as error:
    LOGGER.info("manual interruption")
  # except Exception as error:
  #   LOGGER.fatal(error)
  '''finally:
    if DATA_UNIT:
      DATA_UNIT.close()
    sys.exit(exit_code)'''


