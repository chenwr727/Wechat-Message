from sqlmodel import SQLModel, create_engine

from sql.models import *

engine = create_engine("sqlite:///database.db")
SQLModel.metadata.create_all(engine)
