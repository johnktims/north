import csv
import io
from datetime import datetime
from enum import IntEnum
from typing import List, Dict, Any

from pydantic import BaseModel, Field, field_validator


class MentalHealthStatus(IntEnum):
  NORMAL = 0
  CONCERN = 1
  SEVERE = 2


class MentalHealthRecord(BaseModel):
  timestamp: datetime
  location_id: int
  temperature_celsius: float
  humidity_percent: float
  air_quality_index: int
  noise_level_db: float
  lighting_lux: float
  crowd_density: int
  stress_level: int
  sleep_hours: float
  mood_score: float
  mental_health_status: MentalHealthStatus

  @field_validator('stress_level')
  def validate_stress_level(cls, v):
    if not 0 <= v <= 100:
      raise ValueError(f'stress_level must be between 0 and 100, got {v}')
    return v

  @field_validator('humidity_percent')
  def validate_humidity(cls, v):
    if not 0 <= v <= 100:
      raise ValueError(f'humidity_percent must be between 0 and 100, got {v}')
    return v

  @field_validator('sleep_hours')
  def validate_sleep_hours(cls, v):
    if not 0 <= v <= 24:
      raise ValueError(f'sleep_hours must be between 0 and 24, got {v}')
    return v


class MentalHealthDataset(BaseModel):
  records: List[MentalHealthRecord]

  @field_validator('records')
  def validate_records(cls, v):
    if not v:
      raise ValueError('Dataset must contain at least one record')
    return v


class StressAnalysisResult(BaseModel):
  stress_score: float = Field(..., ge=0, le=100)
  reason: str = Field(..., max_length=5000)

  @field_validator('stress_score')
  def validate_stress_score(cls, v):
    """Validate that stress_score is within range (0-100)."""
    if not 0 <= v <= 100:
      raise ValueError(f'stress_score must be between 0 and 100, got {v}')
    return v


class StressAnalysisResponse(BaseModel):
  message: str
  user_id: str
  stress_analysis: Dict[str, Any]


def parse_csv_to_models(csv_content: str) -> MentalHealthDataset:
  """Parse CSV content into MentalHealthDataset model.
  >>> csv = '''timestamp,location_id,temperature_celsius,humidity_percent,air_quality_index,noise_level_db,lighting_lux,crowd_density,stress_level,sleep_hours,mood_score,mental_health_status
  ... 2025-07-27T10:00:00Z,1,23.5,45.0,50,65.5,500.0,10,75,7.5,6.5,1'''
  >>> dataset = parse_csv_to_models(csv)
  >>> len(dataset.records)
  1

  >>> invalid_csv = '''timestamp,location_id
  ... 2025-07-27T10:00:00Z,1'''
  >>> parse_csv_to_models(invalid_csv)
  Traceback (most recent call last):
      ...
  KeyError: 'temperature_celsius'
  """
  csv_file = io.StringIO(csv_content)
  csv_reader = csv.DictReader(csv_file)

  records = []
  for row in csv_reader:
    # Convert string values to appropriate types
    record = MentalHealthRecord(
      timestamp=datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')),
      location_id=int(row['location_id']),
      temperature_celsius=float(row['temperature_celsius']),
      humidity_percent=float(row['humidity_percent']),
      air_quality_index=int(row['air_quality_index']),
      noise_level_db=float(row['noise_level_db']),
      lighting_lux=float(row['lighting_lux']),
      crowd_density=int(row['crowd_density']),
      stress_level=int(row['stress_level']),
      sleep_hours=float(row['sleep_hours']),
      mood_score=float(row['mood_score']),
      mental_health_status=int(row['mental_health_status'])
    )
    records.append(record)

  return MentalHealthDataset(records=records)
