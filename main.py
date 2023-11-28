from fastapi.responses import FileResponse
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBasicCredentials, HTTPBasic
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
# from starlette.responses import FileResponse
from passlib.context import CryptContext
from pathlib import Path
from typing import List
import os
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import secrets

USERNAME = os.getenv("DEFAULT_USERNAME", "admin")
PASSWORD = os.getenv("DEFAULT_PASSWORD", "P@ssW0rd!")

DATABASE_URL = "sqlite:///./sql/filefly.db"
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)


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


# List available Files
def list_files_in_directory(path: str) -> List[str]:
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")
    try:
        return [file for file in os.listdir(path) if os.path.isfile(os.path.join(path, file))]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str or None = None


class User(BaseModel):
    username: str
    disabled: bool or None = None


class UserInDB(User):
    hashed_password: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()
security = HTTPBasic()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db: Session, username: str):
    user = db.query(User).filter(User.username == username).first()
    if user:
        print(f"Found user: {user.username}")
    else:
        print("User not found.")
    return user


def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta or None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate "
                                                                                          "credentials",
                                         headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credential_exception

        token_data = TokenData(username=username)
    except JWTError:
        raise credential_exception

    user = get_user(db, username=token_data.username)

    if user is None:
        raise credential_exception

    return user


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive User")
    return current_user


@app.on_event("startup")
async def startup_event():
    init_db()  # Initialize the database

    # Create session for database operations
    db = SessionLocal()

    # Check if the default user exists
    default_user = get_user(db, USERNAME)
    if not default_user:
        # Create and add the new default user
        hashed_password = get_password_hash(PASSWORD)
        new_user = User(username=USERNAME, hashed_password=hashed_password, disabled=False)
        db.add(new_user)
        db.commit()

    db.close()


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect Username or Password",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/files/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@app.get("/files_v2/{file_path:path}")
async def download_v2_file(file_path: str, current_user: User = Depends(get_current_active_user)):
    # current_user now contains the authenticated user's information

    full_path = Path(FOLDER_PATH) / file_path
    if full_path.is_file():
        return FileResponse(str(full_path))
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/files_v2/list_all")
async def list_all_files(current_user: User = Depends(get_current_active_user)):
    # Ensure that current_user is authenticated
    file_list = list_files_in_directory(FOLDER_PATH)
    return file_list


@app.post("/register")
async def register_user(user_data: UserRegistration, current_user: User = Depends(get_current_active_user),
                        db: Session = Depends(get_db)):
    # Check if the user already exists
    existing_user = get_user(db, user_data.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Hash the user's password
    hashed_password = get_password_hash(user_data.password)

    # Create new user object
    new_user = User(username=user_data.username, hashed_password=hashed_password, disabled=False)

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

    # Replace this with your actual authentication logic
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Username or Password",
            headers={"WWW-Authenticate": "Basic"},
        )

    full_path = Path(FOLDER_PATH) / file_path
    if full_path.is_file():
        return FileResponse(str(full_path))
    raise HTTPException(status_code=404, detail="File not found")