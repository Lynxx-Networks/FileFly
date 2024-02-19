import os
import sys
import shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from urllib.parse import unquote
from fastapi.testclient import TestClient
from main import app
from main import UserInDB, get_current_active_user, SessionLocal, get_password_hash, init_db
import pytest
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped


Base = declarative_base()

DATABASE_URL = "sqlite:////sql/filefly.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class UserInDB(Base):
    __tablename__ = "users"
    username: Mapped[str] = Column(String, primary_key=True)
    hashed_password: Mapped[str] = Column(String)
    disabled: Mapped[bool] = Column(Boolean, default=False)

@pytest.fixture(scope="session", autouse=True)
def setup_database_and_user():
    # Initialize the database
    Base.metadata.create_all(bind=engine)
    
    # Create an initial user
    with SessionLocal() as db:
        default_user = db.query(UserInDB).filter_by(username="test").first()
        if not default_user:
            hashed_password = get_password_hash("test")
            new_user = UserInDB(username="test", hashed_password=hashed_password)
            db.add(new_user)
            db.commit()
    
    yield  # This ensures the setup is done before tests run

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_user_authentication(client):
    response = client.post("/token", data={"username": "test", "password": "test"})
    assert response.status_code == 200, response.text
    assert "access_token" in response.json()


def test_upload_file(client):
    # Authenticate to obtain the token
    auth_response = client.post("/token", data={"username": "test", "password": "test"})
    assert auth_response.status_code == 200, auth_response.text
    token = auth_response.json()["access_token"]

    # Test data for file upload
    subdirectory = "test_subdirectory"
    destination_filename = "test_file_txt"  # Assuming you have corrected the filename handling
    file_content = b"Test file content"

    # Headers with Authorization token
    headers = {"Authorization": f"Bearer {token}"}

    # Make a POST request to upload the file with authentication
    response = client.post(
        "/upload",
        files={"file": (destination_filename, file_content)},
        data={"subdirectory": subdirectory, "destination_filename": destination_filename},
        headers=headers,
    )

    # Assertions to ensure the file upload was successful
    assert response.status_code == 200, response.text
    response_data = response.json()
    print(response.json())
    assert response_data["filename"] == destination_filename, "Uploaded filename mismatch"

    # Additional assertions can be made here, such as checking the file's existence in the filesystem, if applicable


import base64

def test_download_file(client):
    # Test data
    subdirectory = "test_subdirectory"
    destination_filename = "test_file_txt"
    file_content = b"Test file content"

    # Encode the credentials
    credentials = base64.b64encode(b"test:test").decode("utf-8")

    # Make a GET request to download the file
    response = client.get(
        f"/{subdirectory}/{destination_filename}",
        headers={"Authorization": f"Basic {credentials}"},
    )

    # Assert the response status code
    assert response.status_code == 200

    # Assert the response content
    assert response.content == file_content

def test_download_v2_file(client):
    # Authenticate to obtain the token
    auth_response = client.post("/token", data={"username": "test", "password": "test"})
    assert auth_response.status_code == 200, auth_response.text
    token = auth_response.json()["access_token"]

    # Headers with Authorization token
    headers = {"Authorization": f"Bearer {token}"}

    # The file to attempt to download
    file_path = "test_subdirectory/test_file_txt"

    # Make a GET request to download the file with authentication
    response = client.get(f"/files_v2/{file_path}", headers=headers)

    # Assertions to ensure the file download was successful
    assert response.status_code == 200, "Failed to download file"
    print(response.headers)
    assert "text/plain" in response.headers['content-type'], "Incorrect content type"

def test_register_user(client):
    # Authenticate to obtain the token for an existing user
    auth_response = client.post("/token", data={"username": "test", "password": "test"})
    assert auth_response.status_code == 200, auth_response.text
    token = auth_response.json()["access_token"]

    # Headers with Authorization token
    headers = {"Authorization": f"Bearer {token}"}

    # Data for the new user to register
    new_user_data = {
        "username": "test2",
        "password": "test2"
    }

    # Make a POST request to register a new user with authentication
    response = client.post("/register", json=new_user_data, headers=headers)

    # Assertions to ensure the new user registration was successful
    assert response.status_code == 200, response.text
    assert response.json() == {"message": "User successfully registered"}, "Unexpected response message"

    # Cleanup: Optionally delete the test user after the test to maintain a clean state
    # This would typically be done via a direct database operation or a dedicated API endpoint for cleanup

def test_security_upload_file_unauthenticated(client):
    # Test data for file upload
    subdirectory = "unauth_test_subdirectory"
    destination_filename = "unauth_test_file.txt"
    file_content = b"Unauthenticated file content"

    # Attempt to make a POST request without authentication
    response = client.post(
        "/upload",
        files={"file": (destination_filename, file_content)},
        data={"subdirectory": subdirectory, "destination_filename": destination_filename},
    )

    # Expecting a 401 Unauthorized response
    assert response.status_code == 401, "Access without authentication should be restricted"

def test_security_download_file_unauthenticated(client):
    # Attempt to make a GET request without authentication
    response = client.get("/files_v2/test_subdirectory/unauth_test_file.txt")

    # Expecting a 401 Unauthorized response
    assert response.status_code == 401, "Access without authentication should be restricted"

def test_security_register_user_unauthenticated(client):
    # Data for the new user registration attempt
    new_user_data = {
        "username": "unauth_test",
        "password": "unauth_test"
    }

    # Attempt to make a POST request without authentication
    response = client.post("/register", json=new_user_data)

    # Expecting a 401 Unauthorized response
    assert response.status_code == 401, "Access without authentication should be restricted"
