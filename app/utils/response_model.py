"""
Pydantic schemas and lightweight database-session helpers.

The schemas defined here are used as `response_model` arguments when invoking
the OpenAI client through `instructor`, which forces the LLM to return JSON
that conforms to the declared structure. This removes a whole class of
"the model returned the wrong shape" errors from the pipeline.
"""

from pydantic import BaseModel, field_validator
from typing import List, Union
from fastapi import Depends
from sqlalchemy import create_engine, inspect


class DatabaseConfig(BaseModel):
    """
    Connection parameters for a user-supplied BI database.

    These fields are populated from query/body parameters by FastAPI's
    dependency injection system, so each request can target a different
    database without restarting the service.
    """
    username: str
    password: str
    host: str
    port: int
    database: str

    @field_validator('port')
    def port_must_be_int(cls, v):
        """Validate that ``port`` is an integer (Pydantic already coerces,
        but this guards against intentionally bad inputs)."""
        if not isinstance(v, int):
            raise ValueError('Port must be an integer')
        return v


def get_bi_db(db_config: DatabaseConfig = Depends()):
    """
    Build a SQLAlchemy inspector for the BI database described by
    ``db_config``. Used as a FastAPI dependency in endpoints that need to
    introspect arbitrary user databases.
    """
    engine = create_engine(
        f'postgresql://{db_config.username}:{db_config.password}'
        f'@{db_config.host}:{db_config.port}/{db_config.database}'
    )
    db = inspect(engine)
    return db


# ---------------------------------------------------------------------------
# LLM response schemas
# ---------------------------------------------------------------------------

class NlOutput(BaseModel):
    """Legacy NL-to-SQL response shape (kept for backwards compatibility)."""
    sql_query: str
    natural_language: str
    chart_type: str


class QuestionsOutput(BaseModel):
    """A single suggested question paired with a short summary/title."""
    actual_question: str
    summary_question: str


class TableOutput(BaseModel):
    """List of table names the LLM judged relevant to the user's prompt."""
    table_names: list


class SQLQuery(BaseModel):
    """A single KPI metric and the SQL query that computes it."""
    metric: str
    query: str


class BiOutput(BaseModel):
    """
    Structured BI-dashboard response: one or more roles together with all
    KPI queries generated for them.
    """
    Roles: Union[str, List[str]]
    SQLQueries: List[SQLQuery]


class Nltosql(BaseModel):
    """
    Primary NL-to-SQL response payload returned by `/convert-nl-to-sql`.

    Attributes:
        SQLQuery:          Executable SQL that answers the user's question.
        NaturalLanguage:   Plain-English answer (no query-mechanics jargon).
        ChartType:         Suggested chart for visualisation
                           (bar/pie/line/scatter/area/table).
        VisualizationData: JSON payload with the datapoints for the chart.
    """
    SQLQuery: str
    NaturalLanguage: str
    ChartType: str
    VisualizationData: str


class ChartVisual(BaseModel):
    """Container for generated chart-rendering code (reserved for future use)."""
    ChartCode: str
