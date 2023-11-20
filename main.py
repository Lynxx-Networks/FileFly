from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os
from pathlib import Path

app = FastAPI()

FOLDER_PATH = "/data"  # Set this to your folder path

@app.get("/files/{file_path:path}")
async def read_file(file_path: str):
    full_path = Path(FOLDER_PATH) / file_path
    if full_path.is_file():
        return FileResponse(str(full_path))
    raise HTTPException(status_code=404, detail="File not found")
