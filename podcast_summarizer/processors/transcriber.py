"""
Transcription module for converting audio to text using local Whisper or Azure OpenAI.
"""
import os
from typing import List, Dict, Any, Optional
from langchain_core.documents.base import Blob
from langchain_community.document_loaders.parsers.audio import AzureOpenAIWhisperParser

from ..core.logging_config import get_logger

logger = get_logger(__name__)

# Add imports for local Whisper
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    logger.warning("Local Whisper not available. Install with 'pip install openai-whisper'")
    WHISPER_AVAILABLE = False

def parse_audio_with_local_whisper(
    audio_files: List[str],
    model_size: str = "base.en"
) -> List[Dict[str, Any]]:
    """
    Transcribe audio files using local Whisper model.
    
    Args:
        audio_files: List of paths to audio files
        model_size: Size of Whisper model to use ('tiny', 'base', 'small', 'medium', 'large')
    
    Returns:
        List of document dictionaries containing transcriptions
    """
    if not WHISPER_AVAILABLE:
        logger.error("Local Whisper package not available")
        return []
    
    documents = []
    
    try:
        # Load the model (only once)
        logger.info(f"Loading local Whisper model '{model_size}'")
        model = whisper.load_model(model_size)
        
        for audio_file in audio_files:
            if not os.path.exists(audio_file):
                logger.error(f"Audio file does not exist: {audio_file}")
                continue
                
            logger.info(f"Starting local transcription for {audio_file}")
            try:
                # Transcribe using Whisper
                result = model.transcribe(audio_file)
                
                if result and "text" in result:
                    doc_dict = {
                        "content": result["text"],
                        "metadata": {"source": audio_file, "model": f"whisper-{model_size}"},
                        "source": audio_file
                    }
                    documents.append(doc_dict)
                    logger.info(f"Successfully transcribed {audio_file} with local Whisper ({len(doc_dict['content'])} chars)")
                else:
                    logger.warning(f"No transcription content returned for {audio_file}")
            except Exception as e:
                logger.error(f"Error transcribing {audio_file} with local Whisper: {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"Error initializing local Whisper: {str(e)}", exc_info=True)
    
    return documents

def parse_audio_with_azure_openai(
    audio_files: List[str],
    api_key: str,
    api_version: str,
    endpoint: str,
    deployment_name: str,
) -> List[Dict[str, Any]]:
    """
    Transcribe audio files using Azure OpenAI's Whisper model.
    
    Args:
        audio_files: List of paths to audio files
        api_key: Azure OpenAI API key
        api_version: Azure OpenAI API version
        endpoint: Azure OpenAI endpoint
        deployment_name: Azure OpenAI deployment name
    
    Returns:
        List of document dictionaries containing transcriptions
    """
    parser = AzureOpenAIWhisperParser(
        api_key=api_key,
        azure_endpoint=endpoint,
        deployment_name=deployment_name,
        api_version=api_version,
    )
    
    documents = []
    
    for audio_file in audio_files:
        if not os.path.exists(audio_file):
            logger.error(f"Audio file does not exist: {audio_file}")
            continue
            
        logger.info(f"Starting transcription for {audio_file}")
        try:
            audio_file = Blob(path=audio_file)
                
            # Parse the audio file and convert generator to a list
            doc_generator = parser.lazy_parse(blob=audio_file)
            
            # The parse method returns a generator, so we need to convert it to a list
            docs_list = list(doc_generator)
            
            if docs_list and len(docs_list) > 0:
                doc_dict = {
                    "content": docs_list[0].page_content,
                    "metadata": docs_list[0].metadata,
                    "source": audio_file
                }
                documents.append(doc_dict)
                logger.info(f"Successfully transcribed {audio_file} ({len(doc_dict['content'])} chars)")
            else:
                logger.warning(f"No transcription content returned for {audio_file}")
        except Exception as e:
            logger.error(f"Error transcribing {audio_file}: {str(e)}", exc_info=True)
    
    return documents

def transcribe_audio(
    audio_files: List[str],
    use_local_first: bool = True,
    local_model_size: str = "base",
    azure_api_key: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    azure_deployment_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Transcribe audio files using either local Whisper (if available) or Azure OpenAI.
    
    Args:
        audio_files: List of paths to audio files
        use_local_first: Try local Whisper first before using Azure
        local_model_size: Size of Whisper model to use ('tiny', 'base', 'small', 'medium', 'large')
        azure_api_key: Azure OpenAI API key
        azure_api_version: Azure OpenAI API version
        azure_endpoint: Azure OpenAI endpoint
        azure_deployment_name: Azure OpenAI deployment name
    
    Returns:
        List of document dictionaries containing transcriptions
    """
    # Try local Whisper first if requested and available
    if use_local_first and WHISPER_AVAILABLE:
        logger.info("Attempting transcription with local Whisper")
        documents = parse_audio_with_local_whisper(audio_files, local_model_size)
        if documents:
            return documents
        logger.warning("Local transcription failed or returned no results, falling back to Azure")
    
    # Fall back to Azure OpenAI if local failed or wasn't requested
    if all([azure_api_key, azure_api_version, azure_endpoint, azure_deployment_name]):
        logger.info("Transcribing with Azure OpenAI")
        return parse_audio_with_azure_openai(
            audio_files,
            azure_api_key,
            azure_api_version,
            azure_endpoint,
            azure_deployment_name
        )
    else:
        if not use_local_first or not WHISPER_AVAILABLE:
            logger.error("Transcription failed: Local Whisper unavailable and Azure credentials missing")
        else:
            logger.error("Transcription failed: Azure credentials missing for fallback")
        return []

def save_transcription_to_txt(documents: List[Dict[str, Any]], output_file: str) -> None:
    """
    Save transcriptions to a text file.
    
    Args:
        documents: List of document dictionaries containing transcriptions
        output_file: Path to save the output text file
    """
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            for doc in documents:
                f.write(f"Source: {doc['source']}\n\n")
                f.write(doc["content"])
                f.write("\n\n" + "-" * 80 + "\n\n")
                
        logger.info(f"Saved transcription to {output_file}")
    except Exception as e:
        logger.error(f"Error saving transcription to {output_file}: {str(e)}", exc_info=True)
