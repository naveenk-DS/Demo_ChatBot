import re
from .config import env, int_env
from .schemas import SearchFilters

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def ident(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid configured SQL identifier: {value}")
    return value

def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

def build_sql(f: SearchFilters) -> str:
    db, table = ident(env("ATHENA_DATABASE")), ident(env("ATHENA_TABLE"))
    cols = {
        "property_id": ident(env("COL_PROPERTY_ID", "property_id")),
        "location": ident(env("COL_LOCATION", "location")),
        "city": ident(env("COL_CITY", "city")),
        "bhk": ident(env("COL_BHK", "bhk")),
        "price": ident(env("COL_PRICE", "price")),
        "property_type": ident(env("COL_PROPERTY_TYPE", "property_type")),
        "image_url": ident(env("COL_IMAGE_URL", "image_url")),
        "property_status": ident(env("COL_STATUS", "property_status")),
    }
    selected = ", ".join(dict.fromkeys(cols.values()))
    where = []
    if f.location: where.append(f"lower(CAST({cols['location']} AS VARCHAR)) = lower({sql_string(f.location)})")
    if f.city: where.append(f"lower(CAST({cols['city']} AS VARCHAR)) = lower({sql_string(f.city)})")
    if f.bhk is not None: where.append(f"CAST({cols['bhk']} AS INTEGER) = {f.bhk}")
    if f.min_price is not None: where.append(f"CAST({cols['price']} AS DOUBLE) >= {f.min_price}")
    if f.max_price is not None: where.append(f"CAST({cols['price']} AS DOUBLE) <= {f.max_price}")
    if f.property_type: where.append(f"lower(CAST({cols['property_type']} AS VARCHAR)) = lower({sql_string(f.property_type)})")
    if not where: raise ValueError("At least one search filter is required before querying Athena.")
    limit = max(1, min(int_env("MAX_RESULTS", 10), 50))
    return f"SELECT {selected} FROM {db}.{table} WHERE {' AND '.join(where)} LIMIT {limit}"
