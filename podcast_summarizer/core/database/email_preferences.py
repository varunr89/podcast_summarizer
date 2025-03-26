from typing import Dict, Any, Optional

class EmailPreferencesManager:
    """Manager for email preferences table operations."""
    
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
        self.table = "email_preferences"
    
    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get email preferences for a user.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Dict containing email preferences or None if not found
        """
        try:
            response = self.client.from_(self.table)\
                .select("*")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
                
            if response.data:
                return response.data
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching email preferences for user {user_id}: {str(e)}")
            return None
    
    def set(self, user_id: str, detail_level: str = "standard", 
            max_episodes_per_email: int = 5) -> bool:
        """
        Set email preferences for a user.
        
        Args:
            user_id: The user's ID
            detail_level: Summary detail level (brief, standard, detailed)
            max_episodes_per_email: Maximum number of episodes per email
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            data = {
                "user_id": user_id,
                "detail_level": detail_level,
                "max_episodes_per_email": max_episodes_per_email
            }
            
            response = self.client.from_(self.table)\
                .upsert(data)\
                .execute()
                
            return bool(response.data)
            
        except Exception as e:
            self.logger.error(f"Error setting email preferences for user {user_id}: {str(e)}")
            return False