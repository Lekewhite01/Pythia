from pydantic import BaseModel, field_validator
from typing import List, Union
from fastapi import Depends
from sqlalchemy import create_engine, inspect

class DatabaseConfig(BaseModel):
    username: str
    password: str
    host: str
    port: int
    database: str

    @field_validator('port')
    def port_must_be_int(cls, v):
        if not isinstance(v, int):
            raise ValueError('Port must be an integer')
        return v
    
def get_bi_db(db_config: DatabaseConfig = Depends()):
    engine = create_engine(f'postgresql://{db_config.username}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.database}')
    # Session = sessionmaker(bind=engine)
    db = inspect(engine)
    return db

# Define your desired output structure
class NlOutput(BaseModel):
    sql_query: str
    natural_language: str
    chart_type: str

class QuestionsOutput(BaseModel):
    actual_question: str
    summary_question: str

class TableOutput(BaseModel):
    table_names: list

# class BiOutput(BaseModel):
#     Role: str
#     SQLQueries: list

class SQLQuery(BaseModel):
    metric: str
    query: str

class BiOutput(BaseModel):
    Roles: Union[str, List[str]]
    SQLQueries: List[SQLQuery]

class Nltosql(BaseModel):
    SQLQuery: str
    NaturalLanguage: str
    ChartType: str
    VisualizationData: str

class ChartVisual(BaseModel):
    ChartCode: str