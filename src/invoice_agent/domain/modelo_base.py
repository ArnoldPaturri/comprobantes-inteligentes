from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=False)
