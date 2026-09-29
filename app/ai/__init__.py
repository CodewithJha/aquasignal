"""Optional AI assist behind a replaceable port. Null provider is required."""

from app.ai.config import AiSettings
from app.ai.errors import AiAssistError, AiAssistSchemaError, AiAssistTimeout, AiAssistUnavailable
from app.ai.factory import build_ai_assist, build_investigation_copilot
from app.ai.fake import FakeAiAssist
from app.ai.investigation_fake import FakeInvestigationCopilot
from app.ai.investigation_null import NullInvestigationCopilot
from app.ai.investigation_port import (
    MISSING_EVIDENCE_VOCAB,
    AdvisoryBrief,
    InvestigationBriefInput,
    InvestigationCopilotPort,
)
from app.ai.investigation_provider import OptionalProviderInvestigationCopilot
from app.ai.claim_safety import contains_forbidden_claim
from app.ai.investigation_validate import (
    hash_investigation_brief,
    validate_advisory_brief,
)
from app.ai.null import NullAiAssist
from app.ai.port import (
    AiAssistPort,
    AiSuggestion,
    FlagExplanation,
    PhotoAssessment,
    Suggestions,
)
from app.ai.provider import OptionalProviderAiAssist
from app.ai.prompts import (
    FLAG_EXPLAIN_PROMPT_VERSION,
    INVESTIGATION_COPILOT_PROMPT_VERSION,
    PROMPT_VERSION,
)
from app.ai.validate import (
    FLAG_EXPLANATIONS_KEY,
    field_suggestion_rows,
    pack_suggestions_for_domain,
    suggestion_value,
    unpack_flag_explanations,
    validate_suggestions_payload,
)

__all__ = [
    "AI_UNAVAILABLE_MESSAGE",
    "AdvisoryBrief",
    "AiAssistError",
    "AiAssistPort",
    "AiAssistSchemaError",
    "AiAssistTimeout",
    "AiAssistUnavailable",
    "AiSettings",
    "AiSuggestion",
    "FakeAiAssist",
    "FakeInvestigationCopilot",
    "FLAG_EXPLANATIONS_KEY",
    "FLAG_EXPLAIN_PROMPT_VERSION",
    "FlagExplanation",
    "INVESTIGATION_COPILOT_PROMPT_VERSION",
    "InvestigationBriefInput",
    "InvestigationCopilotPort",
    "MISSING_EVIDENCE_VOCAB",
    "NullAiAssist",
    "NullInvestigationCopilot",
    "OptionalProviderAiAssist",
    "OptionalProviderInvestigationCopilot",
    "PROMPT_VERSION",
    "PhotoAssessment",
    "Suggestions",
    "build_ai_assist",
    "build_investigation_copilot",
    "contains_forbidden_claim",
    "field_suggestion_rows",
    "hash_investigation_brief",
    "pack_suggestions_for_domain",
    "suggestion_value",
    "unpack_flag_explanations",
    "validate_advisory_brief",
    "validate_suggestions_payload",
]

AI_UNAVAILABLE_MESSAGE = "AI assistance unavailable"
