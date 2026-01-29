from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    restaurant_id: str
    items_count: int = Field(..., gt=0, description="Number of items in the order")
    cuisine_complexity: float = Field(..., ge=1.0, le=2.0, description="1.0 (Fast Food) to 2.0 (Gourmet)")
    rider_supply_index: float = Field(..., ge=0.5, le=2.0, description="0.5 (Scarce) to 2.0 (Abundant)")
    
    # Location Data
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    
    # Time Context
    hour_of_day: int = Field(..., ge=0, le=23)
    day_of_week: int = Field(..., ge=0, le=6)

class ETAResponse(BaseModel):
    total_eta_seconds: int
    total_eta_minutes: float
    breakdown: dict
    physics_data: dict