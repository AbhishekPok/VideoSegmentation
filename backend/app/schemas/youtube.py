from pydantic import BaseModel


class VideoMeta(BaseModel):
    video_id: str
    duration_sec: int
    duration: str
    chapters: str
    chapter_count: int


class PublicConfig(BaseModel):
    youtube_api: bool


class Health(BaseModel):
    status: str
    database: str
