# Skill normalization moved to the kernel so every bounded context shares one
# canonical algorithm and alias map; re-exported here for compatibility.
from hiresense.kernel import SKILL_ALIASES, normalize_skill
from hiresense.matching.domain.batch_service import BatchEvaluationService
from hiresense.matching.domain.deep_analysis_result import DeepAnalysisResult
from hiresense.matching.domain.deep_dimension import DeepDimension
from hiresense.matching.domain.eligibility import (
    EligibilityResult,
    EligibilityStatus,
    determine_work_authorization_eligibility,
)
from hiresense.matching.domain.dimension_evaluator import DimensionEvaluator
from hiresense.matching.domain.evaluation_result import EvaluationResult
from hiresense.matching.domain.match_analyzer import MatchAnalyzer
from hiresense.matching.domain.skill_matcher import SkillMatcher, SkillMatchResult

__all__ = [
    "SKILL_ALIASES",
    "BatchEvaluationService",
    "DeepAnalysisResult",
    "DeepDimension",
    "EligibilityResult",
    "EligibilityStatus",
    "DimensionEvaluator",
    "EvaluationResult",
    "MatchAnalyzer",
    "SkillMatchResult",
    "SkillMatcher",
    "normalize_skill",
    "determine_work_authorization_eligibility",
]
