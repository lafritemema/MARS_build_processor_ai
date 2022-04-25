import re
from collections import UserList
from typing import List, Dict
from enum import Enum

class LogicOperator(Enum):
    AND=' and '
    OR=' or '

    
class BaseList(UserList):
    def __init__(self, init_list:List=None):
        initlist = init_list if init_list else []
        super().__init__(initlist)
    
    def add(self, definition:str):
        _def = re.sub(r"((\n\ *)|(\ {2,})|(\t\ *))", " ", definition)
        self.append(_def)
    
    def build(self):
        if len(self) > 0:
            return ','.join(self)
    

class LogicList(BaseList):
    def __init__(self, operator:LogicOperator=LogicOperator.AND, init_list:List=None):
        self._operator = operator
        super().__init__(init_list)
    
    @property
    def operator(self):
        return self._operator
    
    @operator.setter
    def operator(self, operator:LogicOperator):
        self._operator = operator
    
    def add(self, definition:str):
        if type(definition) == str:
            super().add(definition)
        else:
            self.append(definition)
    
    def build(self):
        clauses = [f"({p.build()})" if type(p) == LogicList else p for p in self]
        return self._operator.value.join(clauses)


class AliasList(BaseList):
    
    def __init__(self, init_list:List=None):
        super().__init__(init_list)
    
    def add(self, definition:str, alias:str):
        _def = re.sub(r"((\n\ *)|(\ {2,})|(\t\ *))", " ", definition)
        self.append((_def, alias))
    
    def build(self):
        if len(self) > 0:
            _def = [f"{p[0]} as {p[1]}" if p[1] else p[0] for p in self]
            clause = ','.join(_def)
            return clause
    
    
class Clause(object):
    def __init__(self, prefix:str, list_type:BaseList=BaseList):
        self._prefix = prefix
        self._definitions = list_type()
    
    def add(self, definition:str):
        self._definitions.add(definition)
    
    def build(self):
        clause = self._definitions.build()
        if clause:
            return f"{self._prefix} {clause}"


class LogicClause(Clause):
    def __init__(self, prefix:str,
                 init_list:LogicList=None):
        super().__init__(prefix, LogicList)
    
    @property
    def operator(self):
        return self._definitions.operator.value

    @operator.setter
    def operator(self, operator:LogicOperator):
        self._definitions.operator = operator
    
    def build(self):
        clause = self._definitions.build()
        if clause:
            return f"{self._prefix} {clause}"

        
class AliasClause(Clause):
    def __init__(self, prefix:str):
        super().__init__(prefix, AliasList)
    
    def add(self, definition:str, alias:str=None):
        _def = re.sub(r"((\n\ *)|(\ {2,})|(\t\ *))", " ", definition)
        self._definitions.add(_def, alias)
    
    def build(self):
        clause = self._definitions.build()
        if clause:
            return f"{self._prefix} {clause}"
    
    
class DBQuery:
    def __init__(self):
        self._input = Clause('with')
        self._match = Clause('match')
        self._where = LogicClause('where')
        self._with = AliasClause('with')
        self._return = Clause('return')
    
    @property
    def input_clause(self):
        return self._input
    
    @property
    def match_clause(self):
        return self._match
    
    @property
    def where_clause(self):
        return self._where
    
    @where_clause.setter
    def where_clause(self, where:LogicClause):
        self._where = where
    
    @property
    def with_clause(self):
        return self._with

    @property
    def return_clause(self):
        return self._return
    
    def build(self):
        query = [self._input.build(),
                   self._match.build(),
                   self._where.build(),
                   self._with.build(),
                   self._return.build()]
        
        query = [r for r in query if r]
        return " ".join(query)

class DBPipeline:
    def __init__(self):
        self._queries:List[DBQuery] = []
        self._with = AliasClause('with')
        self._return = Clause('return')
    
    @property
    def with_clause(self):
        return self._with
    
    @property
    def return_clause(self):
        return self._return
    
    def add(self, query:DBQuery):
        self._queries.append(query)
    
    def build(self):
        query = [f'call {{{req.build()}}}' for req in self._queries]
        query = [" ".join(query),
                   self._with.build(),
                   self._return.build()]
        query = [r for r in query if r]
        return " ".join(query)
    