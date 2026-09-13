import uvicorn

from app.api.main import create_app

if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=8787, access_log=False)
