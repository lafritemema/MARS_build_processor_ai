from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from .exceptions import DatabaseError


class Neo4jError():
    def __init__(self, message):
        super().__init__('NEO4J ERROR', message)


class Neo4jConnectionError(Neo4jError):
    def __init__(self, message):
        super().__init__(message)


class Neo4jDriver(object):

    def __init__(self, bolt_uri: str, user:str, passwd:str) -> 'Neo4jDriver':
        self.__driver = GraphDatabase.driver(bolt_uri, auth=(user, passwd),connection_timeout=10.0)

    def run(self, query:str, **query_args):
        try:
            with self.__driver.session() as session:
                result = session.run(query,
                                    **query_args)
                records = result.data()
                session.close()
            return records
        except ServiceUnavailable as error:
            raise DatabaseError("Neo4J database not reachable")