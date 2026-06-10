# Skill normalization moved to the kernel so every bounded context shares one
# canonical algorithm and alias map; re-exported here for compatibility.
from hiresense.kernel import SKILL_ALIASES, normalize_skill
from hiresense.matching.domain.batch_service import BatchEvaluationService
from hiresense.matching.domain.deep_analysis_result import DeepAnalysisResult
from hiresense.matching.domain.deep_dimension import DeepDimension
from hiresense.matching.domain.services import MatchingOrchestrator
from hiresense.matching.domain.skill_matcher import SkillMatcher, SkillMatchResult

__all__ = [
    "SKILL_ALIASES",
    "BatchEvaluationService",
    "DeepAnalysisResult",
    "DeepDimension",
    "MatchingOrchestrator",
    "SkillMatchResult",
    "SkillMatcher",
    "normalize_skill",
]
