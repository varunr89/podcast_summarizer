"""Various methods for downloading podcast episodes."""

import requests
import time
import wget
import youtube_dl
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

from fake_useragent import UserAgent
from playwright.sync_api import sync_playwright

from ...core.logging_config import get_logger
from .episode import Episode

logger = get_logger(__name__)

def download_with_headers(episode: Episode, output_dir: Path) -> Optional[Path]:
    """Download using proper headers that mimic a browser."""
    try:
        # Create a user agent
        ua = UserAgent()
        headers = {
            'User-Agent': ua.random,
            'Accept': 'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': urlparse(episode.url).netloc,
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        file_name = f"{episode.title[:30].replace('/', '_').replace(' ', '_')}.mp3"
        file_path = output_dir / file_name
        
        # Stream the download with headers
        with requests.get(episode.url, headers=headers, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        episode.file_path = file_path
        logger.info(f"Successfully downloaded: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to download {episode.title} with headers: {e}")
        return None

def download_with_wget(episode: Episode, output_dir: Path) -> Optional[Path]:
    """Download using wget which often handles redirects better."""
    try:
        file_name = f"{episode.title[:30].replace('/', '_').replace(' ', '_')}.mp3"
        file_path = output_dir / file_name
        
        # Use wget to download
        wget.download(episode.url, out=str(file_path))
        
        episode.file_path = file_path
        logger.info(f"Successfully downloaded with wget: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to download {episode.title} with wget: {e}")
        return None

def download_with_youtube_dl(episode: Episode, output_dir: Path) -> Optional[Path]:
    """Download using youtube-dl which handles a variety of websites."""
    try:
        file_name = f"{episode.title[:30].replace('/', '_').replace(' ', '_')}.mp3"
        file_path = output_dir / file_name
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(file_path),
            'quiet': True,
            'no_warnings': True,
        }
        
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([episode.url])
        
        episode.file_path = file_path
        logger.info(f"Successfully downloaded with youtube-dl: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to download {episode.title} with youtube-dl: {e}")
        return None

def download_with_playwright(episode: Episode, output_dir: Path) -> Optional[Path]:
    """Download using Playwright to automate browser actions."""
    try:
        file_name = f"{episode.title[:30].replace('/', '_').replace(' ', '_')}.mp3"
        file_path = output_dir / file_name
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            
            # Configure browser context
            context = browser.new_context(
                accept_downloads=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            page = context.new_page()
            
            try:
                # Navigate to the URL
                page.goto(episode.url, wait_until="networkidle")
                
                # Wait for the audio element to load
                audio_element = None
                try:
                    audio_element = page.wait_for_selector("audio", timeout=10000)
                except:
                    pass
                
                if audio_element:
                    # Get the audio source
                    audio_src = audio_element.get_attribute("src")
                    
                    # If we found a source URL, download it directly
                    if audio_src:
                        with requests.get(audio_src, stream=True) as response:
                            response.raise_for_status()
                            with open(file_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                    else:
                        # Try to click on download button if available
                        download_button = page.query_selector("a:has-text('Download'), a.download")
                        if download_button:
                            with page.expect_download() as download_info:
                                download_button.click()
                            download = download_info.value
                            download.save_as(file_path)
                else:
                    # Try to find and click a download button if no audio element
                    download_button = page.query_selector("a:has-text('Download'), a.download")
                    if download_button:
                        with page.expect_download() as download_info:
                            download_button.click()
                        download = download_info.value
                        download.save_as(file_path)
            finally:
                browser.close()
        
        episode.file_path = file_path
        logger.info(f"Successfully downloaded with Playwright: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to download {episode.title} with Playwright: {e}")
        return None
