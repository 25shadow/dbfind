from fastapi import APIRouter

from app.api.routes import agent, collections, exports, files, query, settings, sheets, upload_sessions

api_router = APIRouter()
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(collections.router, prefix="/collections", tags=["collections"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(upload_sessions.router, prefix="/upload-sessions", tags=["upload-sessions"])
api_router.include_router(sheets.router, tags=["sheets"])
api_router.include_router(query.router, prefix="/query", tags=["query"])
api_router.include_router(exports.router, prefix="/export", tags=["exports"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
