from urllib.parse import unquote

from fastapi.responses import FileResponse
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File, Form, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBasicCredentials, HTTPBasic
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
# from starlette.responses import FileResponse
from passlib.context import CryptContext
from pathlib import Path
from typing import List, Optional
import os
import shutil
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import secrets
from sqlalchemy.orm import Mapped
import logging

logging.basicConfig(filename='/filefly/logs.log', encoding='utf-8', level=logging.INFO)

USERNAME = os.getenv("USERNAME", "admin")
PASSWORD = os.getenv("PASSWORD", "P@ssW0rd!")

DATABASE_URL = "sqlite:////sql/filefly.db"
Base = declarative_base()

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class UserRegistration(BaseModel):
    username: str
    password: str


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

FOLDER_PATH = "/data"  # Set this to your folder path


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str or None = None


class UserSchema(BaseModel):  # Pydantic model for API validation
    username: str
    disabled: bool = False


class UserInDB(Base):  # Extending SQLAlchemy Base
    __tablename__ = "users"
    username: Mapped[str] = Column(String, primary_key=True, index=True)
    hashed_password: Mapped[str] = Column(String)
    disabled: Mapped[bool] = Column(Boolean, default=False)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()
security = HTTPBasic()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db: Session, username: str):
    try:
        user = db.query(UserInDB).filter(UserInDB.username == username).first()

        return user
    except Exception as e:
        return None


def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


# Function to create access token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Function to get current user
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)): # Replace ... with your actual dependency
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credential_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credential_exception

    user = get_user(db, username=token_data.username) # Ensure you have a function `get_user`

    if user is None:
        raise credential_exception

    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive User")
    return current_user


@app.on_event("startup")
async def startup_event():
    init_db()

    db = SessionLocal()

    try:
        default_user = db.query(UserInDB).filter(UserInDB.username == USERNAME).first()
        if default_user:
            logging.debug("Default user already exists.")
        else:
            logging.debug("Creating new user...")
            logging.debug(USERNAME)
            hashed_password = get_password_hash(PASSWORD)
            new_user = UserInDB(username=USERNAME, hashed_password=hashed_password, disabled=False)
            db.add(new_user)
            db.commit()
            logging.debug("New user created.")
    except Exception as e:
        logging.error(f"Error during database query: {e}")
        raise  # Re-raise the exception to make it visible
    finally:
        db.close()
        logging.debug("Startup event completed....")


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect Username or Password",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


# @app.get("/files/me", response_model=UserInDB)
# async def read_users_me(current_user: UserInDB = Depends(get_current_active_user)):
#     return current_user


@app.get("/files_v2/{file_path:path}")
async def download_v2_file(file_path: str, current_user: UserInDB = Depends(get_current_active_user)):
    # Ensure that current_user is authenticated

    # Normalize and validate the file path
    normalized_path = os.path.normpath(file_path)
    full_path = Path(FOLDER_PATH) / normalized_path

    # Check if the path is within the intended directory
    if not os.path.commonpath([FOLDER_PATH, str(full_path)]) == FOLDER_PATH:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Serve the file if it exists
    if full_path.is_file():
        return FileResponse(str(full_path))
    else:
        raise HTTPException(status_code=404, detail="File not found")


@app.post("/register")
async def register_user(user_data: UserRegistration, current_user: UserInDB = Depends(get_current_active_user),
                        db: Session = Depends(get_db)):
    # Check if the user already exists
    existing_user = get_user(db, user_data.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Hash the user's password
    hashed_password = get_password_hash(user_data.password)

    # Create new user object
    new_user = UserInDB(username=user_data.username, hashed_password=hashed_password, disabled=False)

    # Add new user to the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User successfully registered"}


@app.get("/{file_path:path}")
async def download_file(file_path: str, credentials: HTTPBasicCredentials = Depends(security),
                        db: Session = Depends(get_db)):
    username = credentials.username
    password = credentials.password

    # Authentication logic...
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Username or Password",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Normalize and validate the file path
    normalized_path = os.path.normpath(file_path)
    full_path = Path(FOLDER_PATH) / normalized_path

    # Check if the path is within the intended directory
    if not os.path.commonpath([FOLDER_PATH, str(full_path)]) == FOLDER_PATH:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Serve the file if it exists
    if full_path.is_file():
        return FileResponse(str(full_path))
    else:
        raise HTTPException(status_code=404, detail="File not found")


def sanitize_path_component(path_component: str) -> str:
    # Remove any unsafe characters or patterns from each part of the path
    # This example is simplistic; consider using a library like `python-magic` for more robust handling
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    return ''.join(c for c in path_component if c in safe_chars)


def safe_join(base, *paths):
    """Safely join paths to the base directory."""
    final_path = base
    for path in paths:
        final_path = os.path.normpath(os.path.join(final_path, path))
        if not final_path.startswith(base):
            raise HTTPException(status_code=400, detail="Invalid path")
    return final_path


@app.post("/upload")
async def upload_file(subdirectory: str = Form(...), destination_filename: str = Form(...),
                      file: UploadFile = File(...),
                      current_user: UserInDB = Depends(get_current_active_user),
                      db: Session = Depends(get_db)):
    # Decode URL-encoded strings
    subdirectory = unquote(subdirectory)
    destination_filename = unquote(destination_filename)

    # Normalize and sanitize the subdirectory path
    sanitized_subdirectory_parts = [sanitize_path_component(part) for part in subdirectory.split(os.sep)]
    sanitized_subdirectory = os.path.join(*sanitized_subdirectory_parts)

    # Sanitize the destination filename
    sanitized_filename = sanitize_path_component(destination_filename)

    # Safely define the full file path
    full_directory = safe_join(FOLDER_PATH, sanitized_subdirectory)
    file_location = os.path.join(full_directory, sanitized_filename)

    # Create subdirectory if it doesn't exist
    os.makedirs(full_directory, exist_ok=True)

    # Check if the file already exists
    if os.path.exists(file_location):
        raise HTTPException(status_code=400, detail="File already exists at the destination")

    # Write the uploaded file to the specified location
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": sanitized_filename}
