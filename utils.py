from enum import EnumMeta
import yaml
from exceptions import BaseException, BaseExceptionType
from typing import Dict
import glob
import json

# define metaclass for enumeration access
class GetAttrEnum(EnumMeta):
  """
    Metaclass to get directly the value when call the attribute
  """
  def __getattribute__(cls, name: str) :
    value = super().__getattribute__(name)
    if isinstance(value, cls):
        value = value.value
    return value
  
class GetItemEnum(EnumMeta):
  """
    Metaclass to get directly the value when call the item
  """
  def __getitem__(self, name):
    return super().__getitem__(name).value

def get_config_from_file(yaml_file:str)-> Dict:
  """function to read and parse yaml config files

  Args:
      yaml_file (str): yaml config file

  Raises:
      BaseException: raise if config file not exist or yaml format is not conform

  Returns:
      Dict: the configuration under dict format
  """

  try:
    with open(yaml_file, 'r') as f:
        content = f.read()
        config = yaml.load(content, Loader=yaml.Loader)

    return config
  except FileNotFoundError as error:
    raise BaseException(['YAML_CONFIG'],
                        BaseExceptionType.CONFIG_MISSING,
                        f"no such configuration file {error.filename}")
  except yaml.parser.ParserError as error:
    raise BaseException(["YAML_CONFIG"],
                        BaseExceptionType.CONFIG_NOT_CONFORM,
                        f"the configuration file {yaml_file} not conform : yaml format not respected")

def get_validation_schemas(schemas_dir:str)->Dict[str, Dict]:
  """function to read and parse all json schemas contained in a directory
    the schema files must have a .schema.json extension

  Args:
      schemas_dir (str): path of directory

  Raises:
      BaseException: raise if json format is not conform or elements are missing

  Returns:
      Dict: the configuration under dict format
  """

  schema_dict = {}

  try:
    for file in glob.glob(f"{schemas_dir}/*.schema.json"):
      with open(file, 'r') as schema_file:
        content = schema_file.read()
        schema = json.loads(content)

        # get the paths to validate with schema
        # schema must contain a $paths key containing the paths to validate with the schema
        # if not raise a config error
        path_list = schema['$paths']
                
        # add the schema for each path
        for path in path_list:
          schema_dict[path] = schema
        
      return schema_dict
  except json.JSONDecodeError as error :
    raise BaseException(["VALIDATION_SCHEMA"],
                        BaseExceptionType.CONFIG_NOT_CONFORM,
                        f"Validation schema file {file} is not valid, json format not conform\n{error.args[0]}")
  except KeyError as error:
    raise BaseException(["VALIDATION_SCHEMA"],
                        BaseExceptionType.CONFIG_NOT_CONFORM,
                        f"Validation schema file {file} is not valid, key '$paths' is missing")
