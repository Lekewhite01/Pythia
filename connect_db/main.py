from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, inspect
from pydantic import BaseModel
from typing import List

# Create a FastAPI app instance
app = FastAPI()

class ConnectionParams(BaseModel):
    """
    Pydantic model representing connection parameters for a generic database.

    Attributes:
        database_type (str): Type of the database (e.g., 'postgresql', 'mysql', 'sqlite').
        username (str): Database username.
        password (str): Database password.
        host (str): Database host.
        port (int): Database port.
        database_name (str): Database name.
    """
    database_type: str
    username: str
    password: str
    host: str
    port: int
    database_name: str

class SnowflakeConnectionParams(BaseModel):
    """
    Pydantic model representing connection parameters for a Snowflake database.

    Attributes:
        database_type (str): Type of the database ('snowflake').
        account (str): Snowflake account name.
        user (str): Snowflake database user.
        password (str): Snowflake database password.
        warehouse (str): Snowflake warehouse name.
        database (str): Snowflake database name.
        schema (str): Snowflake schema name.
        role (str): Snowflake role name.
    """
    database_type: str
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str

def create_engine_with_connection_params(connection_params: ConnectionParams):
    """
    Create and return an SQLAlchemy engine based on the provided connection parameters.

    Args:
        connection_params (ConnectionParams): An instance of ConnectionParams containing database connection details.

    Returns:
        sqlalchemy.engine.base.Engine: SQLAlchemy engine for the specified database.

    Raises:
        HTTPException: If an unsupported database type is provided in connection_params.
    """
    connection_url = None

    # Determine the connection URL based on the provided database type
    if connection_params.database_type.lower() == 'postgresql':
        connection_url = f'postgresql+psycopg2://{connection_params.username}:{connection_params.password}@{connection_params.host}:{connection_params.port}/{connection_params.database_name}'
    elif connection_params.database_type.lower() == 'mysql':
        connection_url = f'mysql+mysqlconnector://{connection_params.username}:{connection_params.password}@{connection_params.host}:{connection_params.port}/{connection_params.database_name}'
    elif connection_params.database_type.lower() == 'sqlite':
        connection_url = f'sqlite:///{connection_params.database_name}'
    else:
        # Raise an exception for unsupported database types
        raise HTTPException(status_code=400, detail=f'Unsupported database type: {connection_params.database_type}')

    # Create and return the SQLAlchemy engine
    return create_engine(connection_url)

def create_snowflake_engine(snowflake_conn: SnowflakeConnectionParams):
    """
    Create and return an SQLAlchemy engine for Snowflake database based on the provided connection parameters.

    Args:
        snowflake_conn (SnowflakeConnectionParams): An instance of SnowflakeConnectionParams containing Snowflake connection details.

    Returns:
        sqlalchemy.engine.base.Engine: SQLAlchemy engine for the Snowflake database.

    Note:
        The function assumes that the `database_type` attribute of snowflake_conn is 'snowflake'.
    """
    connection_url = None

    # Check if the provided database type is 'snowflake'
    if snowflake_conn.database_type.lower() == 'snowflake':
        # Construct the Snowflake connection URL
        connection_url = f'snowflake://{snowflake_conn.user}:{snowflake_conn.password}@{snowflake_conn.account}/{snowflake_conn.database}/{snowflake_conn.schema}?warehouse={snowflake_conn.warehouse}&role={snowflake_conn.role}'

    # Create and return the SQLAlchemy engine
    return create_engine(connection_url)

def get_tables(engine):
    """
    Get a list of table names from the specified SQLAlchemy engine.

    Args:
        engine (sqlalchemy.engine.base.Engine): SQLAlchemy engine representing the database connection.

    Returns:
        list: A list of table names in the connected database.
    """
    # Create an inspector for the provided engine
    inspector = inspect(engine)

    # Get a list of table names using the inspector
    tables = inspector.get_table_names()

    # Return the list of tables
    return tables

@app.post("/connect")
async def connect_to_database(connection_params: ConnectionParams):
    """
    Endpoint to connect to a database using the provided connection parameters and retrieve a list of tables.

    Args:
        connection_params (ConnectionParams): An instance of ConnectionParams containing database connection details.

    Returns:
        dict: A dictionary containing the list of tables in the connected database.

    Raises:
        HTTPException: If there is an error connecting to the database.
    """
    try:
        # Attempt to create an SQLAlchemy engine with the provided connection parameters
        engine = create_engine_with_connection_params(connection_params)

        # Get a list of tables using the created engine
        tables = get_tables(engine)

        # Return the list of tables in the response
        return {"tables": tables}

    except Exception as e:
        # If an error occurs during the connection, raise an HTTPException with a 500 status code
        raise HTTPException(status_code=500, detail=f'Error connecting to the database: {str(e)}')
    
@app.post("/snowflake")
async def connect_to_snowflake(snowflake_conn: SnowflakeConnectionParams):
    """
    Endpoint to connect to a Snowflake database using the provided connection parameters and retrieve a list of tables.

    Args:
        snowflake_conn (SnowflakeConnectionParams): An instance of SnowflakeConnectionParams containing Snowflake connection details.

    Returns:
        dict: A dictionary containing the list of tables in the connected Snowflake database.

    Raises:
        HTTPException: If there is an error connecting to the Snowflake database.
    """
    try:
        # Attempt to create an SQLAlchemy engine for Snowflake with the provided connection parameters
        engine = create_snowflake_engine(snowflake_conn)

        # Get a list of tables using the created engine
        tables = get_tables(engine)

        # Return the list of tables in the response
        return {"tables": tables}

    except Exception as e:
        # If an error occurs during the connection, raise an HTTPException with a 500 status code
        raise HTTPException(status_code=500, detail=f'Error connecting to the Snowflake database: {str(e)}')