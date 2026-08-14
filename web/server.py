"""uvicorn 入口：python -m web.server 或 uvicorn web.app:app"""
import uvicorn

from config import Config

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(__import__("os").getenv("WEB_PORT", "8000"))
    print(f"Insight Web 平台: http://{host}:{port}  (db={Config.WEB_DB_PATH})")
    uvicorn.run("web.app:app", host=host, port=port, log_level="info")
