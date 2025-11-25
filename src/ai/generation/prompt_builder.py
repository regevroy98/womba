"""
Prompt builder that uses existing QA-focused prompts.
"""
from src.ai.prompts_qa_focused import (
    EXPERT_QA_SYSTEM_PROMPT,
    BUSINESS_CONTEXT_PROMPT,
    USER_FLOW_GENERATION_PROMPT,
    FEW_SHOT_EXAMPLES,
    MANAGEMENT_API_CONTEXT,
)

# Use existing prompts - no need for REWRITTEN_PROMPT
REWRITTEN_PROMPT = USER_FLOW_GENERATION_PROMPT

class PromptBuilder:
    """Builds prompts for test plan generation using existing QA-focused prompts."""
    
    @staticmethod
    def build_prompt(context: str, business_context: str = "", **kwargs) -> str:
        """Build a prompt using existing prompts."""
        return USER_FLOW_GENERATION_PROMPT.format(
            business_context=business_context or BUSINESS_CONTEXT_PROMPT,
            management_api_context=MANAGEMENT_API_CONTEXT,
            context=context,
            existing_tests_context=kwargs.get('existing_tests_context', ''),
            tasks_context=kwargs.get('tasks_context', ''),
            folder_context=kwargs.get('folder_context', ''),
            figma_context=kwargs.get('figma_context', ''),
        )
