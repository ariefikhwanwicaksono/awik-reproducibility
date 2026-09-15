"""Neo4j connection and batched query helper."""

import pandas as pd
from neo4j import GraphDatabase


class Neo4jConnection:
    def __init__(self, uri, user, pwd):
        self.__driver = None
        try:
            self.__driver = GraphDatabase.driver(uri, auth=(user, pwd))
            print("=> Neo4j: connected.")
        except Exception as e:
            print(f"=> Neo4j: connection failed -- {e}")

    def close(self):
        if self.__driver:
            self.__driver.close()

    def query_to_dataframe(self, query, parameters=None):
        with self.__driver.session() as session:
            result = session.run(query, parameters or {})
            return pd.DataFrame([r.values() for r in result], columns=result.keys())


def run_batched_query(conn, query, user_list, batch_size, label=""):
    """Run a Neo4j query in batches to stay under the per-transaction memory limit."""
    results = []
    n = (len(user_list) + batch_size - 1) // batch_size
    for i in range(n):
        batch = user_list[i * batch_size: (i + 1) * batch_size]
        try:
            df_b = conn.query_to_dataframe(query, {"batch": batch})
            if not df_b.empty:
                results.append(df_b)
        except Exception as e:
            print(f"  WARNING batch {i+1}/{n} [{label}]: {str(e)[:60]}")
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()
