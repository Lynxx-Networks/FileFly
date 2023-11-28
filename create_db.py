from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./test.db"
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
