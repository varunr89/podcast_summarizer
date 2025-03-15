"""
Transcription module for converting audio to text using Azure OpenAI.
"""
import os
from typing import List, Dict, Any
from langchain_core.documents.base import Blob
from langchain_community.document_loaders.parsers.audio import AzureOpenAIWhisperParser

from ..core.logging_config import get_logger

logger = get_logger(__name__)

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
