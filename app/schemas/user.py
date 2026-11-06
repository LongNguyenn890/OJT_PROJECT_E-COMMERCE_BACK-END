from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=5, max_length=100, examples=["Nguyễn Văn A"])
    email: str = Field(..., min_length=5, max_length=255)
    
    
    model_config = ConfigDict(from_attributes=True)