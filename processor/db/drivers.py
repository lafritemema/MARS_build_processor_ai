from neo4j import GraphDatabase, BoltDriver
from neo4j.exceptions import ServiceUnavailable
from .exceptions import DBDriverException, DBExceptionType

class Neo4jDriver(object):

    def __init__(self, bolt_uri: str, user:str, passwd:str) -> 'Neo4jDriver':
        self.__driver:BoltDriver = GraphDatabase.driver(bolt_uri, auth=(user, passwd),connection_timeout=10.0)

    def run(self, query:str, **query_args):
        try:
            with self.__driver.session() as session:
                result = session.run(query,
                                    **query_args)
                records = result.data()
                session.close()
            return records
        except ServiceUnavailable as error:
            error.args[0]
            raise DBDriverException(['DB', 'DRIVER', 'NEO4J','QUERY'],
                                    DBExceptionType.NOT_REACHABLE,
                                    f"neo4j service is not available.\n{error.args[0]}")
    def close(self):
        self.__driver.close()