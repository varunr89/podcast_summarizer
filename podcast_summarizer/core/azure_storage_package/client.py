"""
Azure Blob Storage client initialization.
"""
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

from podcast_summarizer.core.logging_config import get_logger
from podcast_summarizer.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class AzureBlobStorageClient:
    """Core client for Azure Blob Storage."""
    
    def __init__(self):
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
    
    def get_blob_client(self, blob_name):
        """Get a blob client for the specified blob name."""
        if not self.blob_service_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
            
        return self.blob_service_client.get_blob_client(
            container=self.container_name, 
            blob=blob_name
        )
    
    def ensure_initialized(self):
        """Ensure client is initialized or raise exception."""
        if not self.container_client:
            logger.error("Azure Blob Storage client not initialized")
            raise RuntimeError("Azure Blob Storage client not initialized")
