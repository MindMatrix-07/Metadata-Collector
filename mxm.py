import re
import asyncio
import requests
from duckduckgo_search import DDGS

class MXM:
    def __init__(self, key=None, session=None):
        pass # No API key needed for the hybrid approach

    def _sync_get_verified_link(self, track_name, artist_name):
        query = f'"{track_name}" "{artist_name}" site:musixmatch.com/lyrics/'
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=1))
                if results and len(results) > 0:
                    href = results[0].get('href')
                    if href and "musixmatch.com/lyrics/" in href:
                        return href
        except Exception as e:
            print(f"Search error: {e}")
        return None

    async def get_verified_link(self, track_name, artist_name):
        # Run synchronous search in a separate thread so it doesn't block the async event loop
        return await asyncio.to_thread(self._sync_get_verified_link, track_name, artist_name)

    def format_slug(self, text):
        # Remove special characters, replace spaces with hyphens
        text = re.sub(r'[^\w\s-]', '', text).strip()
        text = re.sub(r'[-\s]+', '-', text).strip('-')
        return text

    def _sync_check_link(self, url):
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}, timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"Error checking link {url}: {e}")
            return False

    async def check_link(self, url):
        return await asyncio.to_thread(self._sync_check_link, url)

    def get_predicted_link(self, track_name, artist_name):
        artist_slug = self.format_slug(artist_name)
        track_slug = self.format_slug(track_name)
        # Sometimes artists are combined or have different slugs, but this is a best-effort prediction
        return f"https://www.musixmatch.com/lyrics/{artist_slug}/{track_slug}"

    async def process_single_track(self, sp_track):
        if isinstance(sp_track, dict) and sp_track.get("track"):
            t = sp_track["track"]
            track_name = t.get("name", "")
            artist_name = ", ".join([a.get("name", "") for a in t.get("artists", [])]) if t.get("artists") else ""
            album_name = t["album"].get("name", "") if t.get("album") else ""
            
            predicted = self.get_predicted_link(track_name, artist_name)
            
            # Check if predicted link actually loads
            is_valid = await self.check_link(predicted)
            if is_valid:
                verified = predicted
            else:
                verified = await self.get_verified_link(track_name, artist_name)
            
            # Format the output for the templates
            return {
                "track": t,
                "track_name": track_name,
                "album_name": album_name,
                "artist_name": artist_name,
                "isrc": sp_track.get("isrc"),
                "image": sp_track.get("image"),
                "predicted_link": predicted,
                "verified_link": verified,
                "note": None
            }
        else:
            return sp_track

    async def Tracks_Data(self, sp_data, split_check=False):
        if not sp_data:
            return []
        
        # sp_data is a list of spotify tracks or error strings
        tasks = [asyncio.create_task(self.process_single_track(item)) for item in sp_data]
        results = await asyncio.gather(*tasks)
        return list(results)
