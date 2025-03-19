"""
Azure Blob Storage operations implementation.
"""
import os
from pathlib import Path
from typing import Optional, Union
from azure.core.exceptions import ResourceNotFoundError

from podcast_summarizer.core.logging_config import get_logger

logger = get_logger(__name__)

class AzureBlobStorageOperations:
    """Operations for Azure Blob Storage."""
    
    def __init__(self, client):
        """Initialize with Azure Blob Storage client."""
        self.client = client
    
    def upload_file(self, file_path: Union[str, Path], 
                   blob_name: Optional[str] = None, 
                   content_type: Optional[str] = None) -> str:
        """
        Upload a file to Azure Blob Storage.
        
        Args:
            file_path: Path to the file to upload
            blob_name: Optional name for the blob (default: filename)
            content_type: Optional content type (default: auto-detected)
            
        Returns:
            URL of the uploaded blob
        """
        self.client.ensure_initialized()
            
        try:
            file_path = Path(file_path)
            # Use filename as blob_name if not provided
            if not blob_name:
                blob_name = file_path.name
                
            # Get the blob client
            blob_client = self.client.get_blob_client(blob_name)
            
            # Upload file
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True, content_type=content_type)
                
            # Get the blob URL
            blob_url = blob_client.url
            
            logger.info(f"Uploaded file {file_path} to {blob_url}")
            return blob_url
            
        except Exception as e:
            logger.error(f"Error uploading file to Azure Blob Storage: {str(e)}")
            raise
    
    def upload_text(self, text: str, blob_name: str) -> str:
        """
        Upload text content directly to Azure Blob Storage.
        
        Args:
            text: Text content to upload
            blob_name: Name for the blob
            
        Returns:
            URL of the uploaded blob
        """
        self.client.ensure_initialized()
            
        try:
            # Add .txt extension if not already present
            if not blob_name.endswith(".txt"):
                blob_name = f"{blob_name}.txt"
                
            # Get the blob client
            blob_client = self.client.get_blob_client(blob_name)
            
            # Upload text content
            encoded_text = text.encode('utf-8')
            blob_client.upload_blob(encoded_text, overwrite=True, content_type="text/plain")
                
            # Get the blob URL
            blob_url = blob_client.url
            
            logger.info(f"Uploaded text content to {blob_url}")
            return blob_url
            
        except Exception as e:
            logger.error(f"Error uploading text to Azure Blob Storage: {str(e)}")
            raise
    
    def download_blob(self, blob_name: str, output_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """
        Download a blob from Azure Blob Storage.
        
        Args:
            blob_name: Name of the blob to download
            output_path: Optional path to save the downloaded file
            
        Returns:
            Path to the downloaded file or None if download failed
        """
        self.client.ensure_initialized()
            
        try:
            blob_client = self.client.get_blob_client(blob_name)
            
            # If no output_path provided, use a temp directory
            if not output_path:
                temp_dir = Path("./temp_downloads")
                temp_dir.mkdir(exist_ok=True)
                output_path = temp_dir / Path(blob_name).name
                
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the blob
            with open(output_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
                
            logger.info(f"Downloaded blob {blob_name} to {output_path}")
            return output_path
            
        except ResourceNotFoundError:
            logger.warning(f"Blob {blob_name} not found in container")
            return None
        except Exception as e:
            logger.error(f"Error downloading blob from Azure Blob Storage: {str(e)}")
            return None
    
    def get_blob_url(self, blob_name: str) -> str:
        """Get URL for a blob without downloading it."""
        self.client.ensure_initialized()
        blob_client = self.client.get_blob_client(blob_name)
        return blob_client.url
        
    def blob_exists(self, blob_name: str) -> bool:
        """Check if a blob exists in storage."""
        self.client.ensure_initialized()
        try:
            blob_client = self.client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking if blob exists: {str(e)}")
            return False
            
    def delete_blob(self, blob_name: str) -> bool:
        """Delete a blob from storage."""
        self.client.ensure_initialized()
        try:
            # Check if the blob is a transcript - never delete transcripts
            if blob_name.startswith("transcripts/") or "_transcript" in blob_name:
                logger.warning(f"Attempted to delete transcript blob {blob_name} - Operation blocked for data protection")
                return False
                
            blob_client = self.client.get_blob_client(blob_name)
            blob_client.delete_blob()
            logger.info(f"Deleted blob: {blob_name}")
            return True
        except ResourceNotFoundError:
            logger.warning(f"Blob {blob_name} not found when attempting deletion")
            return False
        except Exception as e:
            logger.error(f"Error deleting blob: {str(e)}")
            return False
