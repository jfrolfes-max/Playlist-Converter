# -*- coding: utf-8 -*-
"""Playlist A>S Converter.ipynb

"""

#!pip install spotipy requests beautifulsoup4
# Uncomment the line above and run it in a separate cell if you don't have the libraries installed.

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re
import requests
from bs4 import BeautifulSoup
import json

# --- Configuration ---
# IMPORTANT: Replace with your actual Spotify API credentials
# Go to https://developer.spotify.com/dashboard/ to get these.
# Make sure SPOTIPY_REDIRECT_URI below is also added to your app's 'Redirect URIs' in the Spotify Developer Dashboard.
SPOTIPY_CLIENT_ID = '' # Replace with your Spotify Client ID
SPOTIPY_CLIENT_SECRET = '' # Replace with your Spotify Client Secret
SPOTIPY_REDIRECT_URI = '' # Must match your Spotify App settings
SCOPE = "playlist-modify-public playlist-modify-private user-read-private" # Permissions needed

# --- Spotify Functions ---

def get_spotify_client():
    """Authenticates with Spotify and returns a Spotify client object."""
    try:
        print("Attempting to authenticate with Spotify...")
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=SCOPE,
            show_dialog=True # Force user to re-authenticate if token expires or scopes change
        ))
        print("Successfully authenticated with Spotify.")
        return sp
    except Exception as e:
        print(f"Error during Spotify authentication setup: {e}")
        print("Please ensure your SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI are correct.")
        print("You might need to open the generated URL in your browser to complete authentication.")
        return None

def search_spotify_track(sp_client, track_name, artist_name=None, album_name=None):
    """Searches Spotify for a track and returns its URI if found."""
    query_parts = [track_name]
    if artist_name: query_parts.append(f"artist:{artist_name}")
    if album_name: query_parts.append(f"album:{album_name}")
    query = " ".join(query_parts)

    try:
        results = sp_client.search(q=query, type="track", limit=1)
        if results['tracks']['items']:
            track_info = results['tracks']['items'][0]
            track_uri = track_info['uri']
            print(f"  - Found: '{track_info['name']}' by '{track_info['artists'][0]['name']}' (Spotify)")
            return track_uri
        else:
            print(f"  - No match found for '{track_name}' by '{artist_name}'.")
            return None
    except Exception as e:
        print(f"Error searching Spotify for '{track_name}': {e}")
        return None

def create_spotify_playlist(sp_client, user_id, playlist_name, public=False, collaborative=False, description=""):
    """Creates a new Spotify playlist and returns its ID."""
    try:
        playlist = sp_client.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=public,
            collaborative=collaborative,
            description=description
        )
        print(f"Created new Spotify playlist: '{playlist['name']}' (ID: {playlist['id']})")
        return playlist['id']
    except Exception as e:
        print(f"Error creating Spotify playlist: {e}")
        return None

def add_tracks_to_playlist(sp_client, playlist_id, track_uris):
    """Adds a list of track URIs to a specified Spotify playlist."""
    if not track_uris:
        print("No tracks to add to the playlist.")
        return

    # Spotify API limits adding to 100 tracks per request
    chunk_size = 100
    for i in range(0, len(track_uris), chunk_size):
        chunk = track_uris[i:i + chunk_size]
        try:
            sp_client.playlist_add_items(playlist_id=playlist_id, items=chunk)
            print(f"Added {len(chunk)} tracks to playlist ID: {playlist_id}")
        except Exception as e:
            print(f"Error adding tracks to playlist ID {playlist_id} (chunk {i}-{i+len(chunk)}): {e}")

# --- Apple Music (Web Scraping Attempt) ---
def get_apple_music_playlist_tracks(apple_music_playlist_url):
    """
    Attempts to extract track information from an Apple Music playlist URL using web scraping.
    NOTE: This method is fragile and highly dependent on Apple's website structure.
    If Apple changes their HTML/JSON-LD, this function may break.
    For more robust solutions, consider:
    1. Using a dedicated music migration service (e.g., Soundiiz, TuneMyMusic).
    2. Manually inputting track details if scraping fails.
    3. Exploring the official Apple Music API (requires developer account and user authentication).
    """
    print(f"\nAttempting to extract tracks from Apple Music URL: {apple_music_playlist_url}")
    tracks = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(apple_music_playlist_url, headers=headers, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors

        soup = BeautifulSoup(response.text, 'html.parser')

        # Attempt to find data from script tags with JSON-LD (most reliable for scraping)
        json_ld_script = soup.find('script', type='application/ld+json')
        if json_ld_script:
            data = json.loads(json_ld_script.string)

            # JSON-LD can be a single object or a list of objects
            items_to_process = [data] if not isinstance(data, list) else data

            for item in items_to_process:
                if item.get('@type') == 'MusicPlaylist' and 'track' in item:
                    for track_item in item['track']:
                        track_name = track_item.get('name')
                        artist_name = track_item.get('byArtist', {}).get('name')
                        album_name = track_item.get('inAlbum', {}).get('name')
                        if track_name:
                            tracks.append({'title': track_name, 'artist': artist_name, 'album': album_name})
                    if tracks: # If tracks were found from this playlist item, stop searching
                        break

        if not tracks:
            print("  Could not find tracks using JSON-LD. Trying direct HTML element scraping (less reliable).")
            # Fallback to direct HTML element scraping (highly page-structure dependent)
            # These selectors are examples and may need to be updated based on current Apple Music HTML.
            for section in soup.find_all('section', class_='section-playlist-tracks'):
                for li in section.find_all('li', class_='track-list-item'):
                    track_name_tag = li.find('div', class_='track-name')
                    artist_name_tag = li.find('div', class_='track-artist')
                    album_name_tag = li.find('div', class_='track-album') # May not always exist

                    track_name = track_name_tag.get_text(strip=True) if track_name_tag else None
                    artist_name = artist_name_tag.get_text(strip=True) if artist_name_tag else None
                    album_name = album_name_tag.get_text(strip=True) if album_name_tag else None

                    if track_name:
                        tracks.append({'title': track_name, 'artist': artist_name, 'album': album_name})

        if not tracks:
            print("  Failed to extract any tracks from the Apple Music URL. The page structure might have changed.")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error for Apple Music URL {apple_music_playlist_url}: {e.response.status_code} - {e.response.reason}")
        if e.response.status_code == 404: print("  (Playlist not found or URL is incorrect)")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error for Apple Music URL {apple_music_playlist_url}: {e}")
    except requests.exceptions.Timeout:
        print("Request to Apple Music URL timed out.")
    except requests.exceptions.RequestException as e:
        print(f"An unexpected request error occurred for Apple Music URL: {e}")
    except json.JSONDecodeError:
        print("Could not decode JSON-LD data from Apple Music page (malformed JSON).")
    except Exception as e:
        print(f"An unexpected error occurred during Apple Music scraping: {e}")

    return tracks

# --- Main Script ---
def main():
    print("\n--- Apple Music to Spotify Playlist Migrator ---")
    apple_music_url = input("Enter the Apple Music playlist URL: ")
    spotify_playlist_name = input("Enter the desired name for the new Spotify playlist: ")

    # 1. Get Apple Music Tracks
    apple_tracks = get_apple_music_playlist_tracks(apple_music_url)

    if not apple_tracks:
        print("No tracks found from the Apple Music playlist. Exiting.")
        return

    print(f"\nSuccessfully extracted {len(apple_tracks)} tracks from Apple Music playlist.")
    print("Example tracks from Apple Music (first 5):")
    for i, track in enumerate(apple_tracks[:5]):
        artist_info = f" by {track.get('artist')}" if track.get('artist') else ""
        album_info = f" (Album: {track.get('album')})" if track.get('album') else ""
        print(f"  - {track.get('title')}{artist_info}{album_info}")
    print("-" * 40)

    # 2. Authenticate with Spotify
    sp = get_spotify_client()
    if not sp:
        print("Spotify authentication failed. Please check your credentials and network connection.")
        return

    # Get current user ID to create playlist
    try:
        user_id = sp.current_user()['id']
        print(f"Logged in as Spotify user: {user_id}")
    except Exception as e:
        print(f"Could not get current Spotify user ID. Ensure authentication is complete. Error: {e}")
        return

    # 3. Create Spotify Playlist
    new_playlist_id = create_spotify_playlist(sp, user_id, spotify_playlist_name, public=True, description=f"Migrated from Apple Music playlist: {apple_music_url}")
    if not new_playlist_id:
        print("Failed to create Spotify playlist. Exiting.")
        return

    # 4. Search for and Add Tracks to Spotify Playlist
    print("\nSearching for matching tracks on Spotify...")
    spotify_track_uris = []
    for i, track in enumerate(apple_tracks):
        print(f"  ({i+1}/{len(apple_tracks)}) Searching for '{track['title']}' by '{track.get('artist', 'Unknown')}'...")
        spotify_uri = search_spotify_track(sp, track['title'], track.get('artist'), track.get('album'))
        if spotify_uri:
            spotify_track_uris.append(spotify_uri)

    if spotify_track_uris:
        print(f"\nAdding {len(spotify_track_uris)} matched tracks to the new Spotify playlist...")
        add_tracks_to_playlist(sp, new_playlist_id, spotify_track_uris)
        print(f"\nSuccessfully migrated {len(spotify_track_uris)} tracks to your new Spotify playlist!")
        print(f"You can view your new Spotify playlist here: https://open.spotify.com/playlist/{new_playlist_id}")
    else:
        print("No matching Spotify tracks were found to add to the playlist.")

    print("\n--- Migration process complete. ---")

if __name__ == "__main__":
    main()
