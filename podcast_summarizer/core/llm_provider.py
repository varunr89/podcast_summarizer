"""
LLM provider module for Azure OpenAI integration
"""
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
from langchain_openai import AzureOpenAIEmbeddings

from ..core.config import get_settings
from ..core.logging_config import get_logger

logger = get_logger(__name__)

def get_azure_llm(temperature: float = 0.2, deployment_name: str = None):
    """Get Azure AI Chat Completions model"""
    settings = get_settings()
    
    # Allow override of deployment name if provided
    model_name = deployment_name or settings.DEEPSEEK_MODEL
    
    logger.info(f"Initializing Azure LLM with model: {model_name}")
    
    return AzureAIChatCompletionsModel(
        endpoint=settings.DEEPSEEK_ENDPOINT,
        credential=settings.DEEPSEEK_API_KEY,
        model_name=settings.DEEPSEEK_MODEL,
        temperature=temperature
    )

def get_azure_embeddings():
    """Get Azure AI Embeddings model"""
    settings = get_settings()
    
    logger.info("Initializing Azure Embeddings model")
    
    # You might need to adjust these parameters based on your Azure setup
    return AzureOpenAIEmbeddings(
                model=settings.EMBEDDINGS_MODEL,
                api_key=settings.EMBEDDINGS_API_KEY,
                azure_endpoint=settings.EMBEDDINGS_ENDPOINT,
                chunk_size=4000,
            )