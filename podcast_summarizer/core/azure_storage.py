"""
Azure Blob Storage integration for podcast summarizer.
"""
import os
import uuid
from pathlib import Path
from io import BytesIO
from typing import Optional, BinaryIO, Union
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError

from .logging_config import get_logger
from .config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class AzureBlobStorage:
    """Manager for Azure Blob Storage operations."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one storage client instance."""
        if cls._instance is None:
            cls._instance = super(AzureBlobStorage, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance
    
    def _initialize_client(self):
        """Initialize the Azure Blob Storage client."""
        try:
            connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
            self.container_name = settings.AZURE_STORAGE_CONTAINER_NAME
            
            if not connection_string:
                logger.error("AZURE_STORAGE_CONNECTION_STRING environment variable not set")
                raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable not set")
            
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            
            # Check if container exists, create if it doesn't
            try:
                self.container_client = self.blob_service_client.get_container_client(self.container_name)
                # Test container exists by listing blobs
                next(self.container_client.list_blobs(), None)
                logger.info(f"Connected to Azure Blob Storage container: {self.container_name}")
            except Exception:
                logger.info(f"Container {self.container_name} doesn't exist. Creating...")
                self.container_client = self.blob_service_client.create_container(self.container_name)
                logger.info(f"Created Azure Blob Storage container: {self.container_name}")
        
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Storage client: {str(e)}")
            self.blob_service_client = None
            self.container_client = None
            raise

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
        if not self.container_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
            
        try:
            file_path = Path(file_path)
            # Use filename as blob_name if not provided
            if not blob_name:
                blob_name = file_path.name
                
            # Get the blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_name
            )
            
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
        if not self.container_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
            
        try:
            # Add .txt extension if not already present
            if not blob_name.endswith(".txt"):
                blob_name = f"{blob_name}.txt"
                
            # Get the blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_name
            )
            
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
        if not self.container_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
            
        try:
            # Get the blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_name
            )
            
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
        """
        Get URL for a blob without downloading it.
        
        Args:
            blob_name: Name of the blob
            
        Returns:
            URL of the blob
        """
        if not self.container_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
            
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, 
            blob=blob_name
        )
        return blob_client.url
        
    def blob_exists(self, blob_name: str) -> bool:
        """
        Check if a blob exists in storage.
        
        Args:
            blob_name: Name of the blob
            
        Returns:
            True if blob exists, False otherwise
        """
        if not self.container_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
            
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_name
            )
            properties = blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking if blob exists: {str(e)}")
            return False
            
    def delete_blob(self, blob_name: str) -> bool:
        """
        Delete a blob from storage.
        
        Args:
            blob_name: Name of the blob
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        if not self.container_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
            
        try:
            # Check if the blob is a transcript - never delete transcripts
            if blob_name.startswith("transcripts/") or "_transcript" in blob_name:
                logger.warning(f"Attempted to delete transcript blob {blob_name} - Operation blocked for data protection")
                return False
                
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_name
            )
            blob_client.delete_blob()
            logger.info(f"Deleted blob: {blob_name}")
            return True
        except ResourceNotFoundError:
            logger.warning(f"Blob {blob_name} not found when attempting deletion")
            return False
        except Exception as e:
            logger.error(f"Error deleting blob: {str(e)}")
            return False

def get_storage():
    """Get Azure Blob Storage manager instance."""
    return AzureBlobStorage()
