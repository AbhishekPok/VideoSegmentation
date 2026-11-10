from fastapi import APIRouter, Path

from ...dependencies import CurrentUser
from ...schemas import VideoMeta
from ...services import youtube_service

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/videos/{video_id}", response_model=VideoMeta)
def video_meta(_user: CurrentUser, video_id: str = Path(pattern=r"^[A-Za-z0-9_-]{11}$")):
    """Exact length and chapter lines via the server-side Data API key.

    404 `not_configured` when the server has no key: the frontend then reads the
    length from the embedded YouTube player instead.
    """
    return youtube_service.get_video_meta(video_id)
