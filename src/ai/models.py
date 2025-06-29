from typing import Dict, List, Union, Literal, Optional

from pydantic import Field, BaseModel, validator


class SeasonMapping(BaseModel):
    """季度映射对象"""

    local_group_name: str = Field(..., description="本地组名称，例如目录名")
    maps_to_tmdb_seasons: List[int] = Field(..., description="对应的TMDB季度列表")

    @validator("maps_to_tmdb_seasons")
    def validate_tmdb_seasons(cls, v):
        """验证TMDB季度列表"""
        if not isinstance(v, list):
            raise ValueError("maps_to_tmdb_seasons必须是列表类型")

        if not v:
            raise ValueError("maps_to_tmdb_seasons不能为空")

        for season in v:
            if not isinstance(season, int) or season < 0:
                raise ValueError(f"季度号必须是非负整数: {season}")

        return v


class EpisodeMapping(BaseModel):
    """单个剧集映射"""

    file_path: str = Field(..., description="本地文件的相对路径")
    tmdb_season: int = Field(..., ge=0, description="TMDB季号")
    tmdb_episode: int = Field(..., ge=1, description="TMDB集号")
    episode_type: Literal["regular", "special", "movie"] = Field(
        default="regular", description="剧集类型"
    )
    confidence: Literal["High", "Medium", "Low"] = Field(
        default="Medium", description="置信度等级"
    )


class AIAnalysisResult(BaseModel):
    """AI分析结果"""

    confidence: Literal["High", "Medium", "Low"] = Field(
        ..., description="总体置信度等级"
    )
    reason: str = Field(..., description="分析理由说明")
    season_mapping: List[SeasonMapping] = Field(
        default_factory=list, description="季度映射列表"
    )
    file_mapping: List[EpisodeMapping] = Field(
        default_factory=list, description="剧集映射列表"
    )
    extra_notes: Optional[str] = Field(default=None, description="额外特殊情况说明")

    @validator("file_mapping")
    def validate_mapping_not_empty(cls, v, values):
        """验证映射列表不为空（当置信度足够高时）"""
        confidence = values.get("confidence", "Low")
        if confidence in ["High", "Medium"] and not v:
            raise ValueError("高置信度结果必须包含映射信息")
        return v

    class Config:
        # 允许额外字段，但会发出警告
        extra = "forbid"
        # JSON序列化时使用字段别名
        allow_population_by_field_name = True
