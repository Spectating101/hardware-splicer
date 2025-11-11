from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional


class ComponentAnalysis(BaseModel):
    educational_value: str = Field(pattern="^(high|medium|low)$")
    reuse_potential: str = Field(pattern="^(high|medium|low|unknown)$")
    failure_modes: List[str]
    testing_procedures: List[str]
    safety_considerations: Optional[List[str]] = None
    repair_difficulty: Optional[str] = None
    estimated_lifespan: Optional[str] = None
    environmental_impact: Optional[str] = None


class ProjectSuggestion(BaseModel):
    name: str
    description: str
    difficulty: str
    time_estimate: str
    components_used: List[str]
    skills_learned: List[str]
    educational_value: Optional[str] = None
    estimated_cost: Optional[str] = None
    safety_level: Optional[str] = None


class ProjectSuggestionList(BaseModel):
    projects: List[ProjectSuggestion]


class ConditionAssessment(BaseModel):
    condition: str
    confidence: float
    visible_damage: List[str]
    estimated_functionality: str
    reuse_recommendation: str
    safety_concerns: List[str]
    testing_required: List[str]


class EducationalContent(BaseModel):
    tutorial: str
    key_concepts: List[str]
    common_applications: List[str]
    safety_notes: List[str]
    troubleshooting: List[str]


def try_validate(model_cls, data):
    try:
        return model_cls.model_validate(data)
    except ValidationError:
        return None

