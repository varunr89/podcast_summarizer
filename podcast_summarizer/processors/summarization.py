# Example change (actual implementation will depend on your existing code)
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from ..core.config import get_settings

def get_summarization_model():
    """Get the DeepSeek model for summarization."""
    settings = get_settings()
    
    return AzureAIChatCompletionsModel(
        endpoint=settings.DEEPSEEK_ENDPOINT,
        credential=settings.DEEPSEEK_API_KEY,
        model_name=settings.DEEPSEEK_MODEL,
    )

def create_summary_chain():
    """Create a chain for summarizing text."""
    model = get_summarization_model()
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert podcast summarizer. Provide a concise summary of the following podcast transcript."),
        ("user", "{transcript}")
    ])
    
    parser = StrOutputParser()
    
    return prompt_template | model | parser
