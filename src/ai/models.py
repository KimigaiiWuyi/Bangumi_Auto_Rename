from typing import List, Literal, Optional

from pydantic import Field, BaseModel, field_validator


class SeasonMapping(BaseModel):
    """季度映射对象"""

    local_group_name: str = Field(..., description="本地组名称，例如目录名")
    maps_to_tmdb_seasons: List[int] = Field(
        ..., description="对应的TMDB季度列表，无需包括第0季"
    )

    @field_validator("maps_to_tmdb_seasons")
    @classmethod
    def validate_tmdb_seasons(cls, v):
        """验证TMDB季度列表"""
        if not isinstance(v, list):
            raise ValueError("maps_to_tmdb_seasons必须是列表类型")

        # 有时子路径中完全无匹配项或仅有第零季的特典，不验证。
        # if not v:
        #     raise ValueError("maps_to_tmdb_seasons不能为空")

        for season in v:
            if not isinstance(season, int) or season < 0:
                raise ValueError(f"季度号必须是非负整数: {season}")

        return v

    class Config:
        # Gemini API兼容配置
        populate_by_name = True


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

    class Config:
        # Gemini API兼容配置
        populate_by_name = True


class AIAnalysisResult(BaseModel):
    """AI分析结果"""

    confidence: Literal["High", "Medium", "Low"] = Field(
        ..., description="总体置信度等级"
    )
    reason: str = Field(..., description="分析理由说明")
    season_mapping: List[SeasonMapping] = Field(
        default_factory=list,
        description="季度映射列表，如整个子路径下均无匹配命中项，则无需包含",
    )
    file_mapping: List[EpisodeMapping] = Field(
        default_factory=list, description="剧集映射列表"
    )
    extra_notes: Optional[str] = Field(default=None, description="额外特殊情况说明")

    @field_validator("file_mapping")
    @classmethod
    def validate_mapping_not_empty(cls, v, info):
        """验证映射列表不为空（当置信度足够高时）"""
        # 在Pydantic V2中，需要从info.data获取其他字段值
        if hasattr(info, 'data') and info.data:
            confidence = info.data.get("confidence", "Low")
            if confidence in ["High", "Medium"] and not v:
                raise ValueError("高置信度结果必须包含映射信息")
        return v

    class Config:
        # Gemini API不支持additionalProperties，所以不设置extra
        # JSON序列化时使用字段别名
        populate_by_name = True

    @classmethod
    def model_json_schema(
        cls, by_alias: bool = True, ref_template: str = '#/$defs/{model}'
    ):
        """
        生成Gemini API兼容的JSON Schema
        移除additionalProperties以避免Gemini API错误
        """
        schema = super().model_json_schema(by_alias=by_alias, ref_template=ref_template)

        def remove_additional_properties(obj):
            """递归移除所有additionalProperties"""
            if isinstance(obj, dict):
                # 移除additionalProperties
                obj.pop('additionalProperties', None)
                # 递归处理嵌套对象
                for key, value in obj.items():
                    remove_additional_properties(value)
            elif isinstance(obj, list):
                for item in obj:
                    remove_additional_properties(item)

        remove_additional_properties(schema)
        return schema

    # 为了向后兼容，保留schema方法
    @classmethod
    def schema(cls, by_alias: bool = True, ref_template: str = '#/definitions/{model}'):
        """向后兼容的schema方法"""
        return cls.model_json_schema(by_alias=by_alias, ref_template=ref_template)
