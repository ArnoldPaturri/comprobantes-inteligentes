from pydantic import BaseModel, ConfigDict


class ModeloDominio(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=False)
