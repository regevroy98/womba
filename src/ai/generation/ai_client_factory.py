"""
AI Client Factory - creates OpenAI or Anthropic clients.
"""
from typing import Optional
from src.config.settings import settings


class AIClientFactory:
    """Factory for creating AI clients (OpenAI or Anthropic)."""
    
    @staticmethod
    def create_client(use_openai: bool = True, api_key: Optional[str] = None):
        """
        Create an AI client.
        
        Args:
            use_openai: Use OpenAI (True) or Anthropic (False)
            api_key: API key (defaults to settings)
            
        Returns:
            OpenAI or Anthropic client instance
        """
        if use_openai:
            from openai import OpenAI
            return OpenAI(api_key=api_key or settings.openai_api_key)
        else:
            from anthropic import Anthropic
            return Anthropic(api_key=api_key or settings.anthropic_api_key)
    
    @staticmethod
    def get_default_model(use_openai: bool = True) -> str:
        """Get default model name."""
        if use_openai:
            return "gpt-4o"
        return settings.default_ai_model
