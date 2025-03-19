"""
Azure Blob Storage integration for podcast summarizer.
"""
from podcast_summarizer.core.azure_storage_package.client import AzureBlobStorageClient
from podcast_summarizer.core.azure_storage_package.operations import AzureBlobStorageOperations

class AzureBlobStorage:
    """Manager for Azure Blob Storage operations (maintains backward compatibility)."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one storage client instance."""
        if cls._instance is None:
            cls._instance = super(AzureBlobStorage, cls).__new__(cls)
            client = AzureBlobStorageClient()
            cls._instance.operations = AzureBlobStorageOperations(client)
            
            # Add all methods from operations to this instance for backward compatibility
            for method_name in dir(cls._instance.operations):
                if not method_name.startswith('_'):  # Only public methods
                    method = getattr(cls._instance.operations, method_name)
                    if callable(method):
                        setattr(cls._instance, method_name, method)
        return cls._instance

def get_storage():
    """Get Azure Blob Storage manager instance."""
    return AzureBlobStorage()
