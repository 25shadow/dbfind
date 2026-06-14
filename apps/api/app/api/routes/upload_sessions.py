from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from starlette.status import HTTP_204_NO_CONTENT

from app.schemas.upload_sessions import UploadSessionCreateRequest, UploadSessionResponse
from app.services.upload_session_service import UploadSessionService

router = APIRouter()


@router.post("", response_model=UploadSessionResponse)
async def create_upload_session(payload: UploadSessionCreateRequest) -> UploadSessionResponse:
    return await run_in_threadpool(
        UploadSessionService().create_session,
        file_name=payload.file_name,
        file_size=payload.file_size,
        chunk_size=payload.chunk_size,
        collection_id=payload.collection_id,
    )


@router.get("", response_model=list[UploadSessionResponse])
async def list_upload_sessions() -> list[UploadSessionResponse]:
    return await run_in_threadpool(UploadSessionService().list_sessions)


@router.get("/{session_id}", response_model=UploadSessionResponse)
async def get_upload_session(session_id: str) -> UploadSessionResponse:
    return await run_in_threadpool(UploadSessionService().get_session, session_id)


@router.put("/{session_id}/chunks/{chunk_index}", response_model=UploadSessionResponse)
async def upload_session_chunk(
    session_id: str,
    chunk_index: int,
    chunk: UploadFile = File(...),
) -> UploadSessionResponse:
    data = await chunk.read()
    return await run_in_threadpool(UploadSessionService().upload_chunk, session_id, chunk_index, data)


@router.post("/{session_id}/complete", response_model=UploadSessionResponse)
async def complete_upload_session(session_id: str, background_tasks: BackgroundTasks) -> UploadSessionResponse:
    session = await run_in_threadpool(UploadSessionService().complete_session, session_id, False)
    if session.status == "importing":
        background_tasks.add_task(UploadSessionService().import_session_file, session_id)
    return session


@router.delete("/{session_id}", status_code=HTTP_204_NO_CONTENT)
async def cancel_upload_session(session_id: str) -> None:
    await run_in_threadpool(UploadSessionService().cancel_session, session_id)
