
from typing import  Dict
from unittest import result

from click import progressbar
from .components import DBPipeline, DBQuery, LogicClause, LogicList, LogicOperator

def __build_preconditions():
    precondition = DBQuery()
    precondition.input_clause.add('action')
    precondition.match_clause.add('(action)<-[precondition:PRECONDITION]-(precond_state:Resource:StateObject)')
    precondition.with_clause.add('''collect({state:precondition.state,
                                     relation:precondition.relation,
                                     priority:precondition.priority,
                                     definition:properties(precond_state)})''',
                                     'preconditions')
    precondition.return_clause.add('preconditions')
    return precondition

def __build_results():
    results = DBQuery()
    results.input_clause.add('action')
    results.match_clause.add('(action)-[result:RESULT]->(result_state:Resource:StateObject)')
    results.with_clause.add('''collect({definition:properties(result_state),
                               state:result.state,
                               relation:result.relation})''', 'results')
    results.return_clause.add('results')
    return results

def __build_assets():
    assets = DBQuery()
    assets.input_clause.add('action')
    assets.match_clause.add('(action)-[:PERFORM_BY]->(asset:Resource:Asset)')
    assets.with_clause.add('''collect({definition: properties(asset),
                              type: labels(asset)})''', 'assets')
    assets.return_clause.add('assets')
    return assets

def __build_action_position():
    areas = DBQuery()
    areas.input_clause.add('action')
    areas.match_clause.add('(action)-[:TO_REACH]->(area:Process:Area)')
    areas.with_clause.add('''{areas: collect({reference: area.reference,
                              type: area.type,
                              uid: area.uid})}''', 'position')
    areas.return_clause.add('position')
    
    return areas

def __build_area_where(node:str, relation:str, area_definition:Dict):
    where_and = LogicClause('where')
    area_str = "exists(({node})-[:{relation}]->{area})"
    for v in area_definition.values():
        if not v == 'all':
            if type(v) == list:
                where_or = LogicList(LogicOperator.OR)
                for el in v:
                    where_or.append(area_str.format(node=node,
                                                 relation=relation,
                                                 area="(:Process:Area{{uid:'{area_uid}'}})".format(area_uid=el)))
                where_and.add(where_or)
            else:
                where_and.add(area_str.format(node=node,
                                              relation=relation,
                                              area="(:Process:Area{{uid:'{area_uid}'}})".format(area_uid=v)))
    return where_and


def __build_appst_by_area(action_type:str, area_definition:Dict):
    pipeline = DBPipeline()
    
    action = DBQuery()
    action.match_clause.add(f'(action:Resource:Action{{type:"{action_type}"}})')
    action.return_clause.add('action')
    
    where_clause = __build_area_where('action', 'TO_REACH', area_definition)
    action.where_clause = where_clause
    
    pipeline.add(action)
    pipeline.add(__build_preconditions())
    pipeline.add(__build_results())
    pipeline.add(__build_assets())
    pipeline.add(__build_action_position())
    
    pipeline.with_clause.add('properties(action)', 'definition')
    pipeline.with_clause.add('preconditions')
    pipeline.with_clause.add('results')
    pipeline.with_clause.add('assets')
    pipeline.with_clause.add('position')
    
    pipeline.return_clause.add('definition')
    pipeline.return_clause.add('preconditions')
    pipeline.return_clause.add('results')
    pipeline.return_clause.add('assets')
    pipeline.return_clause.add('position')
    
    return pipeline

def __build_state_object_where(state_object_definition:Dict):
    where_and = LogicClause('where')

    uid = state_object_definition['uid']
    result = state_object_definition['result']
    precondition = state_object_definition.get('precondition')

    where_and.add(f'state_object.uid = "{uid}"')
    where_and.add(f'result.state = "{result}"')

    if precondition:
        pre_or = LogicList(LogicOperator.OR)
        eq_pre_and = LogicList(LogicOperator.AND)
        neq_pre_and = LogicList(LogicOperator.AND)

        eq_pre_and.add(f'precondition.relation = "eq"')
        eq_pre_and.add(f'precondition.state = "{precondition}"')
        neq_pre_and.add(f'precondition.relation = "neq"')
        neq_pre_and.add(f'precondition.state = "{result}"')

        pre_or.add(eq_pre_and)
        pre_or.add(neq_pre_and)

        where_and.add(pre_or)
    
    return where_and

def build_action_by_state(state_object_definition:Dict):
    pipeline = DBPipeline()
    action = DBQuery()

    action.match_clause.add("(state_object:StateObject)-[precondition:PRECONDITION]->(action:Action)-[result:RESULT]->(state_object)")
    where_clause = __build_state_object_where(state_object_definition)
    action.where_clause = where_clause
    action.return_clause.add('action')

    pipeline.add(action)
    
    pipeline.add(__build_preconditions())
    pipeline.add(__build_results())
    pipeline.add(__build_assets())
    
    pipeline.with_clause.add('properties(action)', 'definition')
    pipeline.with_clause.add('preconditions')
    pipeline.with_clause.add('results')
    pipeline.with_clause.add('assets')
    
    pipeline.return_clause.add('definition')
    pipeline.return_clause.add('preconditions')
    pipeline.return_clause.add('results')
    pipeline.return_clause.add('assets')

    return pipeline.build()


def build_approach_by_area(area_definition:Dict):
    return __build_appst_by_area('MOVE.TCP.APPROACH', area_definition).build()

def build_station_by_area(area_definition:Dict):
    return __build_appst_by_area('MOVE.STATION.WORK', area_definition).build()

def build_work_by_area(area_definition:Dict):
    pipeline = DBPipeline()
    assembly = DBQuery()
    
    assembly.match_clause.add(('(assembly:Product:Assembly)-[:LOCALIZED_IN]->(area:Process:Area)'))
    where_clause = __build_area_where('assembly', 'LOCALIZED_IN', area_definition)
    assembly.where_clause = where_clause
    assembly.with_clause.add('assembly.uid', 'uid')
    assembly.with_clause.add('''{coordinates: {x:assembly.origin.x,
                                               y:assembly.origin.y,
                                               z:assembly.origin.z},
                                 areas:collect(
                                            {reference: area.reference,
                                             type: area.type,
                                             uid: area.uid}
                                         )}''',
                                'position')
    assembly.with_clause.add('''collect({reference: area.reference,
                              type: area.type,
                              uid: area.uid})''', 'areas')
    
    assembly.return_clause.add('uid')
    assembly.return_clause.add('position')
    assembly.return_clause.add('areas')
    
    action = DBQuery()
    action.input_clause.add('uid')
    action.match_clause.add('''(action:Resource:Action{type:"MOVE.TCP.WORK"})
                            -[result:RESULT]->(so:Resource:StateObject{uid:"tcp_work"})''')
    action.where_clause.add('result.state in uid')
    action.return_clause.add('action')
    
    pipeline.add(assembly)
    pipeline.add(action)
    
    pipeline.add(__build_preconditions())
    pipeline.add(__build_results())
    pipeline.add(__build_assets())
    
    pipeline.with_clause.add('properties(action)', 'definition')
    pipeline.with_clause.add('preconditions')
    pipeline.with_clause.add('results')
    pipeline.with_clause.add('assets')
    pipeline.with_clause.add('position')
    
    pipeline.return_clause.add('definition')
    pipeline.return_clause.add('preconditions')
    pipeline.return_clause.add('results')
    pipeline.return_clause.add('assets')
    pipeline.return_clause.add('position')
    
    return pipeline.build()