from sqlalchemy import create_engine, inspect
from pydantic import BaseModel
from fastapi import HTTPException

class ConnectionParams(BaseModel):
    database_type: str
    username: str
    password: str
    host: str
    port: int
    database_name: str

class SnowflakeConnectionParams(BaseModel):
    database_type: str
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str

def create_connection_string(connection_params: ConnectionParams) -> str:
    if connection_params.database_type.lower() == 'postgresql':
        return f'postgresql+psycopg2://{connection_params.username}:{connection_params.password}@{connection_params.host}:{connection_params.port}/{connection_params.database_name}'
    elif connection_params.database_type.lower() == 'mysql':
        return f'mysql+mysqlconnector://{connection_params.username}:{connection_params.password}@{connection_params.host}:{connection_params.port}/{connection_params.database_name}'
    elif connection_params.database_type.lower() == 'sqlite':
        return f'sqlite:///{connection_params.database_name}'
    else:
        raise HTTPException(status_code=400, detail=f'Unsupported database type: {connection_params.database_type}')

def create_snowflake_connection_string(snowflake_conn: SnowflakeConnectionParams) -> str:
    if snowflake_conn.database_type.lower() == 'snowflake':
        return f'snowflake://{snowflake_conn.user}:{snowflake_conn.password}@{snowflake_conn.account}/{snowflake_conn.database}/{snowflake_conn.schema}?warehouse={snowflake_conn.warehouse}&role={snowflake_conn.role}'
    else:
        raise HTTPException(status_code=400, detail=f'Unsupported database type: {snowflake_conn.database_type}')
