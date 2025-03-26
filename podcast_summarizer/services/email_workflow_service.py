from typing import List, Dict, Any, Tuple
from ..api.common import logger
from ..api.models import EpisodeSummaryRequest
from .summarizer_service import generate_episode_summary

def prepare_episodes_to_email(db, user_id: str, max_episodes: int, detail_level: str) -> Tuple[List[Dict], List[Tuple]]:
    """
    Prepare episodes for email by first using existing unemailed summaries,
    then filling up to max_episodes with new summaries if needed.
    
    Args:
        db: Database instance
        user_id: ID of the user
        max_episodes: Maximum number of episodes to include
        detail_level: Summary detail level
    
    Returns:
        Tuple containing:
        - episodes_for_email: list of episodes with their summaries
        - failed_summaries: list of (title, reason) tuples
    """
    logger.info(f"Preparing email content for user {user_id}, max_episodes={max_episodes}")
    
    # Get existing unemailed summaries
    unemailed_summaries = db.summary_manager.get_unemailed_summaries(user_id, max_episodes)
    unemailed_count = len(unemailed_summaries)
    logger.debug(f"Found {unemailed_count} existing unemailed summaries")
    
    # Add titles to unemailed summaries from episodes table
    episodes_for_email = []
    for summary in unemailed_summaries:
        episode_obj = db.episode_manager.get(summary['episode_id']) or {}
        episode_title = episode_obj.get('title', 'Unknown Episode')
        updated_summary = {
            **summary,
            'title': episode_title
        }
        episodes_for_email.append(updated_summary)

    # If we have enough unemailed summaries, use those
    if unemailed_count >= max_episodes:
        logger.info("Have enough unemailed summaries to fill email")
        return episodes_for_email[:max_episodes], []
    
    # We need more summaries - get followed podcasts
    logger.debug("Need more summaries, checking followed podcasts")
    followed_podcasts = db.user_follows_manager.list_followed_podcasts(user_id)
    if not followed_podcasts:
        logger.warning(f"No followed podcasts found for user: {user_id}")
        return episodes_for_email, []
    
    # Get recent episodes from followed podcasts
    all_episodes = []
    for podcast in followed_podcasts:
        episodes = db.episode_manager.list(podcast_id=podcast['podcast_id'], 
                                         limit=max_episodes)
        all_episodes.extend(episodes)
    
    # Sort by published date (newest first)
    all_episodes.sort(key=lambda x: x.get('published_date', ''), reverse=True)
    logger.debug(f"Found {len(all_episodes)} total episodes")
    
    # Track failures
    failed_summaries = []
    
    # Process episodes until we have enough summaries
    needed_summaries = max_episodes - unemailed_count
    episodes_for_email = unemailed_summaries
    
    for episode in all_episodes:
        if len(episodes_for_email) >= max_episodes:
            break
            
        episode_id = episode['id']
        episode_title = episode.get('title', 'Unknown Episode')
        
        # Skip if we already have a summary for this episode
        if any(s['episode_id'] == episode_id for s in episodes_for_email):
            continue
            
        # Check if episode already has a summary in the database
        existing_summary = db.summary_manager.get(episode_id, user_id)
        if existing_summary:
            if not existing_summary.get('summary_emailed', False):
                episode_obj = db.episode_manager.get(episode_id) or {}
                episode_title = episode_obj.get('title', 'Unknown Episode')
                updated_summary = {
                    **existing_summary,
                    'title': episode_title
                }
                episodes_for_email.append(updated_summary)
            continue
        
        # Try to generate a new summary
        try:
            logger.debug(f"Attempting to generate summary for episode {episode_id}")
            transcription = db.transcription_manager.get(episode_id)
            if not transcription:
                logger.warning(f"No transcription found for episode {episode_id}")
                failed_summaries.append((episode_title, "Transcription not available"))
                continue
                
            summary_request = EpisodeSummaryRequest(
                episode_id=episode_id,
                user_id=user_id,
                method='auto',
                detail_level=detail_level
            )
            
            summary, key_points, highlights = generate_episode_summary(
                transcription=transcription,
                config=summary_request
            )
            
            # Store the new summary
            db.summary_manager.store(
                episode_id=episode_id,
                summary=summary,
                user_id=user_id,
                key_points=key_points.get('points', []),
                highlights=highlights,
                detail_level=detail_level,
                metadata={}
            )
            
            # Add to our email list
            new_summary = {
                'episode_id': episode_id,
                'summary': summary,
                'key_points': key_points.get('points', []),
                'highlights': highlights,
                'title': episode_title,
                'summary_emailed': False
            }
            episodes_for_email.append(new_summary)
            
        except Exception as e:
            logger.error(f"Failed to generate summary for {episode_id}: {str(e)}")
            failed_summaries.append((episode_title, f"Summary generation failed: {str(e)}"))
    
    logger.info(f"Prepared {len(episodes_for_email)} episodes for email "
               f"({len(failed_summaries)} failures)")
    return episodes_for_email, failed_summaries

def build_single_episode_summary(db, user_id: str, episode_id: str, detail_level: str) -> Dict[str, Any]:
    """
    Generate or retrieve a single episode summary for the given user.
    
    Args:
        db: Database instance
        user_id: ID of the user
        episode_id: ID of the episode
        detail_level: Summary detail level
        
    Returns:
        Dict containing title, summary, key_points, highlights
        
    Raises:
        ValueError: If transcript is missing or summary generation fails
    """
    logger.debug(f"Building single episode summary: user={user_id}, episode={episode_id}")
    
    # Get episode data first
    episode = db.episode_manager.get(episode_id)
    if not episode:
        raise ValueError(f"Episode not found: {episode_id}")
    
    episode_title = episode.get('title', 'Unknown Episode')
    
    # Check for existing summary for this user
    existing_summary = db.summary_manager.get(episode_id, user_id)
    if existing_summary:
        logger.debug("Using existing summary")
        return {
            'title': episode_title,
            'summary': existing_summary.get('summary', ''),
            'key_points': existing_summary.get('key_points', []),
            'highlights': existing_summary.get('highlights', [])
        }
    
    # Generate new summary
    transcription = db.transcription_manager.get(episode_id)
    if not transcription:
        raise ValueError(f"Transcript not found for episode: {episode_id}")
    
    logger.debug("Generating new summary")
    summary_request = EpisodeSummaryRequest(
        episode_id=episode_id,
        user_id=user_id,
        method='auto',
        detail_level=detail_level
    )
    
    try:
        summary, key_points, highlights = generate_episode_summary(
            transcription=transcription,
            config=summary_request
        )
        
        # Store summary
        db.summary_manager.store(
            episode_id=episode_id,
            summary=summary,
            user_id=user_id,
            key_points=key_points.get('points', []),
            highlights=highlights,
            detail_level=detail_level,
            metadata={}
        )
        
        return {
            'title': episode_title,
            'summary': summary,
            'key_points': key_points.get('points', []),
            'highlights': highlights
        }
        
    except Exception as e:
        logger.error(f"Failed to generate summary: {str(e)}")
        raise ValueError(f"Summary generation failed: {str(e)}")