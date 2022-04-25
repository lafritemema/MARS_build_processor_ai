
from .exceptions import ModelDataError
from typing import List, Dict
from .situation import Situation, StateObject

class Asset:
    def __init__(self, uid:str, description:str, type:str, interface:str):
        self._uid = uid
        self._description = description
        self._interface = interface
    
    def to_json(self):
        return {
            'uid': self._uid,
            'description': self._description,
            'interface':self._interface
        }

    @staticmethod
    def from_dict(asset_dict:Dict) -> 'Asset':
        try:
            _type:List = asset_dict['type'].copy()
            _type.remove('Asset')
            _type.remove('Resource')
            definition = asset_dict['definition']
            
            return Asset(definition['uid'],
                         definition['description'],
                         _type[0],
                         definition['interface'])
        except KeyError as error:
            raise ModelDataError(Asset.__name__, error.args[0])

        except Exception as e:
            print('Error not handled raise during StateObject parsing')
            raise e

class Action:
    def __init__(self, uid:str,
                 description:str,
                 type:str,
                 assets:List[Asset],
                 preconditions:Situation,
                 results:List[StateObject],
                 metadata:Dict):

        self._uid = uid
        self._description=description
        self._type = type
        self._assets = assets
        self._preconditions=preconditions
        self._results = results
        self._metadata = metadata

    @property
    def description(self):
        return self._description
    
    @property
    def preconditions(self):
        return self._preconditions
    
    @property
    def results(self):
        return self._results
    
    @property
    def type(self):
        return self._type

    def get_metadata(self, key):
        return self._metadata.get(key)

    @property
    def effect(self) -> Situation:
        effect = self._preconditions.copy()
        for result in self._results:
            effect.update(result)
        return effect
        
    @staticmethod
    def from_dict(action_dict:Dict) -> 'Action':
        definition = action_dict['definition']
        preconditions = action_dict['preconditions']
        results = action_dict['results']
        assets = action_dict['assets']
            
        uid = definition['uid']
        description = definition['description']
        type = definition['type']
        
        meta_keys = [key for key in action_dict.keys() \
                    if not key in ['definition', 'preconditions', 'results', 'assets']]
        
        metadata = {}
        for key in meta_keys:
            metadata[key] = action_dict[key]

        try:
            assets = [Asset.from_dict(asset) for asset in assets]
            preconditions = Situation.from_list(preconditions)
            results = [StateObject.from_dict(result) for result in results]
            return Action(uid,
                    description,
                    type,
                    assets,
                    preconditions,
                    results,
                    metadata)

        except ModelDataError as error:
            error.update_stack(Action.__name__)
            raise error
    
    def to_json(self):
        return {
            'uid': self._uid,
            'description': self._description,
            'type': self._type,
            'assets':[asset.to_json() for asset in self._assets]
        }

    def __repr__(self) -> str:
        return self._description
        '''return "description:{description}\ntype:{type}\npreconditions:{preconditions}"\
                .format(description=self._description,
                        type=self._type,
                        preconditions=self.preconditions.__repr__())'''