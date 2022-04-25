from flask import Flask, request, jsonify
import fastjsonschema
import re
from typing import Dict
from .exceptions import QueryError, ServerConfigError
from .validation import Validator
from json import loads as jsonload
import os

'''
def build_validator(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            print(properties, subschema)
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(
            validator, properties, instance, schema,
        ):
            yield error

    return validators.extend(
        validator_class, {"properties" : set_defaults},
    )
'''

def http_error_handler(error:Exception):
  return str(error)

class EndpointAction(object):
  """Endpoint for http url handle

  Args:
      object (_type_): _description_
  """
  def __init__(self, action, code=200):
    self._action = action
    self._code = code

  def _get_response(self, data):
    return jsonify(status='SUCCESS', data=data), self._code

  def __call__(self, *args, **kargs):
    if args :
      data = self._action(*args)
    elif kargs:
      data = self._action(**kargs)
    else:
      data = self._action()
    return self._get_response(data)


class ErrorAction(EndpointAction):
  """ ErrorEndpoint for http url handle

  Args:
      EndpointAction (_type_): _description_
  """
  def __init__(self, action, code):
    super().__init__(action, code)
  
  def _get_response(self, data):
    return jsonify(status='FAIL', error=data), self._code


def query_error_handler(error:QueryError):
  """Function to handle a JsonSchemaException
  Args:
      error (fastjsonschema.JsonSchemaException): JsonSchemaException
  Returns:
      error (Dict): error description 
  """

  return error.to_json()


class HttpServer(object):
  
  app:Flask = None

  def __init__(self, name:str, validator:Validator):
    self._app = Flask(__name__)
    self._validator = validator

    self._app.register_error_handler(QueryError, ErrorAction(query_error_handler, 403))
    self._app.register_error_handler(400, ErrorAction(http_error_handler, 400))
    self._app.register_error_handler(403, ErrorAction(http_error_handler, 403))
    self._app.register_error_handler(404, ErrorAction(http_error_handler, 404))
    self._app.register_error_handler(405, ErrorAction(http_error_handler, 405))
    self._app.register_error_handler(500, ErrorAction(http_error_handler, 500))
    self._app.before_request(self.__validate)

  def __validate(self):
    if request.args:
      raise QueryError("No url parameters authorized", "URL.INVALID", "REQUEST.VALIDATION")
    
    path = request.path
    body = request.get_json()
    body = {} if not body else body
    body = self._validator.validate(path, body)

    request.body = body

  def run(self, host, port):
     self._app.run(host=host, port=port)

  def add_endpoint(self, endpoint, name, handler, methods, validation=True):
    if validation and not self._validator.has_key(endpoint):
      raise ServerConfigError(f'No validation schema for url {endpoint}, check your schema directory')
    
    self._app.add_url_rule(endpoint, name, EndpointAction(handler), methods=methods)

  def register_error_handler(self, exception, handler, code):
    self._app.register_error_handler(exception, ErrorAction(handler, code))
  

