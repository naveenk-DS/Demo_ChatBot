from sqlglot import exp, parse
from .config import env

def validate_generated_sql(sql: str) -> None:
    statements = parse(sql, read="trino")
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Only one SQL statement is permitted.")
    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise ValueError("Only SELECT queries are permitted.")
    expected_table = env("ATHENA_TABLE")
    tables = {table.name for table in tree.find_all(exp.Table)}
    if tables != {expected_table}:
        raise ValueError("Query references an unapproved table.")
