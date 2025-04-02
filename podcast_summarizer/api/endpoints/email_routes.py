from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..common import logger, handle_api_exception, get_db_instance
from ...services.email_workflow_service import (
    prepare_episodes_to_email,
    build_single_episode_summary
)
from ...services.email_content_service import format_email_content
from datetime import datetime
from ..models import UserEmailRequest, EpisodeEmailRequest

router = APIRouter()

@router.post("/send-user-emails", response_model=Dict[str, Any])
async def send_user_emails(request: UserEmailRequest):
    """
    Generate and send email summaries for a user's followed podcasts.
    
    Steps:
    1. Get user email and preferences
    2. Prepare episodes (uses existing summaries first, then generates new ones if needed)
    3. Format and send email
    4. Mark summaries as emailed
    """
    user_id = request.user_id
    logger.info(f"Starting email summary process for user: {user_id}")
    
    try:
        db = get_db_instance()
        
        # Get user email and preferences
        user = db.user_manager.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        email_prefs = db.email_preferences_manager.get(user_id)
        if not email_prefs:
            raise HTTPException(status_code=404, detail="Email preferences not found")
        
        detail_level = email_prefs.get('detail_level', 'standard')
        max_episodes = email_prefs.get('max_episodes_per_email', 5)
        
        # Prepare episodes for email
        episodes_for_email, failed_summaries = prepare_episodes_to_email(
            db, user_id, max_episodes, detail_level
        )
        
        if not episodes_for_email and not failed_summaries:
            raise HTTPException(status_code=404, detail="No new episodes available for summarization")
        
        # Format and send email
        formatted_email = format_email_content(episodes_for_email, failed_summaries)
        email_service = get_email_service()
        today = datetime.now().strftime('%Y-%m-%d')
        sent = email_service.send(
            to_email=user['email'],
            subject=f"Your Podcast Summaries for {today}",
            content=formatted_email
        )
        
        if not sent:
            raise HTTPException(status_code=500, detail="Failed to send email")
        
        # Mark summaries as emailed
        if episodes_for_email:
            episode_ids = [ep['episode_id'] for ep in episodes_for_email]
            db.summary_manager.mark_as_emailed(episode_ids, user_id)
        
        logger.info("Email process completed successfully")
        return {
            "status": "success",
            "message": f"Email sent to {user['email']}",
            "episodes_processed": len(episodes_for_email),
            "failed_summaries": len(failed_summaries)
        }
        
    except Exception as e:
        handle_api_exception(e, "processing email summaries")

@router.post("/send-episode-summary", response_model=Dict[str, Any])
async def send_episode_summary(request: EpisodeEmailRequest):
    """
    Send a summary of a specific episode to a user.
    
    Steps:
    1. Get user email and preferences
    2. Build single summary
    3. Format and send email
    4. Mark summary as emailed
    """
    user_id = request.user_id
    episode_id = request.episode_id
    logger.info(f"Starting single episode summary process - User: {user_id}, Episode: {episode_id}")
    
    try:
        db = get_db_instance()
        
        # Get user and preferences
        user = db.user_manager.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        episode = db.episode_manager.get(episode_id)
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")
        
        email_prefs = db.email_preferences_manager.get(user_id) or {}
        detail_level = email_prefs.get('detail_level', 'standard')
        
        # Build summary
        try:
            summary_data = build_single_episode_summary(db, user_id, episode_id, detail_level)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        summary_content = [{
            'title': episode.get('title', 'Unknown Episode'),
            'summary': summary_data.get('summary', ''),
            'key_points': summary_data.get('key_points', []),
            'highlights': summary_data.get('highlights', [])
        }]
        
        # Send email
        formatted_email = format_email_content(summary_content, [])
        email_service = get_email_service()
        sent = email_service.send(
            to_email=user['email'],
            subject=f"Summary: {episode.get('title', 'Podcast Episode')}",
            content=formatted_email
        )
        
        if not sent:
            raise HTTPException(status_code=500, detail="Failed to send email")
        
        # Mark as emailed
        db.summary_manager.mark_as_emailed([episode_id], user_id)
        
        logger.info("Single episode email process completed successfully")
        return {
            "status": "success",
            "message": f"Episode summary sent to {user['email']}",
            "episode_title": episode.get('title', 'Unknown Episode')
        }
        
    except Exception as e:
        handle_api_exception(e, "sending episode summary")

def get_email_service():
    """Get email service instance."""
    from ...services.email_service import EmailService
    return EmailService()