from typing import Dict, Any, Optional

class UserManager:
    """Manager for users table operations."""
    
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
        self.table = "users"
    
    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user details by ID.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Dict containing user details or None if not found
        """
        try:
            response = self.client.from_(self.table)\
                .select("*")\
                .eq("id", user_id)\
                .single()\
                .execute()
                
            if response.data:
                return response.data
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching user {user_id}: {str(e)}")
            return None
    
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user details by email.
        
        Args:
            email: The user's email address
            
        Returns:
            Dict containing user details or None if not found
        """
        try:
            response = self.client.from_(self.table)\
                .select("*")\
                .eq("email", email)\
                .single()\
                .execute()
                
            if response.data:
                return response.data
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching user by email {email}: {str(e)}")
            return None
    
    def update(self, user_id: str, data: Dict[str, Any]) -> bool:
        """
        Update user details.
        
        Args:
            user_id: The user's ID
            data: Dictionary of fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = self.client.from_(self.table)\
                .update(data)\
                .eq("id", user_id)\
                .execute()
                
            return bool(response.data)
            
        except Exception as e:
            self.logger.error(f"Error updating user {user_id}: {str(e)}")
            return False