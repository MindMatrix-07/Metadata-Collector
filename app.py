import re
from flask import Flask, request, render_template, make_response, redirect
from asgiref.wsgi import WsgiToAsgi
from mxm import MXM
from spotify import Spotify

app = Flask(__name__)
mxm_handler = MXM()

def get_spotify_client():
    client_id = request.cookies.get('SPOTIPY_CLIENT_ID')
    client_secret = request.cookies.get('SPOTIPY_CLIENT_SECRET')
    if client_id and client_secret:
        return Spotify(client_id, client_secret)
    return Spotify()

@app.route('/', methods=['GET'])
async def index():
    sp = get_spotify_client()
    link = request.args.get('link')
    if link:
        try:
            if (len(link) < 12):
                return render_template('index.html', tracks_data=["Wrong Spotify Link Or Wrong ISRC"])
            elif re.search(r'artist/(\w+)', link):
                return render_template('index.html', artist=sp.artist_albums(link, []))
            else:
                sp_data = sp.get_isrc(link) if len(link) > 12 else [
                    {"isrc": link, "image": None}]
        except Exception as e:
            return render_template('index.html', tracks_data=[str(e)])

        mxmLinks = await mxm_handler.Tracks_Data(sp_data)
        if isinstance(mxmLinks, str):
            return render_template('index.html', tracks_data=[mxmLinks])

        return render_template('index.html', tracks_data=mxmLinks)

    return render_template('index.html')


@app.route('/split', methods=['GET'])
async def split():
    sp = get_spotify_client()
    link = request.args.get('link')
    link2 = request.args.get('link2')
    if link and link2:
        match = re.search(r'open.spotify.com', link) and re.search(r'track', link)
        match = match and re.search(r'open.spotify.com', link2) and re.search(r'track', link2)
        if match:
            sp_data1 = sp.get_isrc(link)
            sp_data2 = sp.get_isrc(link2)
            
            track1_list = await mxm_handler.Tracks_Data(sp_data1, True)
            track1 = track1_list[0] if track1_list else {}
            if isinstance(track1, str):
                return render_template('split.html', error="track1: " + track1)
                
            track2_list = await mxm_handler.Tracks_Data(sp_data2, True)
            track2 = track2_list[0] if track2_list else {}
            if isinstance(track2, str):
                return render_template('split.html', error="track2: " + track2)
                
            if not track1 or not track2:
                return render_template('split.html', error="Failed to fetch track details")
                
            track1["track"] = sp_data1[0]["track"] if sp_data1 and isinstance(sp_data1[0], dict) else {}
            track2["track"] = sp_data2[0]["track"] if sp_data2 and isinstance(sp_data2[0], dict) else {}
            
            try:
                # Compare verified links if they exist, else predict
                link1_used = track1.get("verified_link") or track1.get("predicted_link")
                link2_used = track2.get("verified_link") or track2.get("predicted_link")
                
                if link1_used == link2_used and link1_used is not None:
                    message = f"""Identical Links Found! </br>
                        They likely share the same page.</br>
                        :mxm: <a href="{link1_used}" target="_blank">MXM Page</a> </br>
                        :spotify: <a href="{link}" target="_blank">{track1["track"].get("name", "Track 1")}</a>,
                        :isrc: {track1.get("isrc", "")} </br>
                        :spotify: <a href="{link2}" target="_blank">{track2["track"].get("name", "Track 2")}</a>,
                        :isrc: {track2.get("isrc", "")}
                        """
                else:
                    message = "They appear to be on different pages (Links differ)."
            except Exception as e:
                return render_template('split.html', error=f"Something went wrong: {e}")

            return render_template('split.html', split_result={"track1": track1, "track2": track2}, message=message)
        else:
            return render_template('split.html', error="Wrong Spotify Link")

    else:
        return render_template('split.html')


@app.route('/spotify', methods=['GET'])
def isrc():
    sp = get_spotify_client()
    link = request.args.get('link')
    if link:
        match = re.search(r'open.spotify.com', link) and re.search(r'track|album', link)
        if match:
            return render_template('isrc.html', tracks_data=sp.get_isrc(link))
        else:
            if len(link) == 12:
                return render_template('isrc.html', tracks_data=sp.search_by_isrc(link))
            return render_template('isrc.html', tracks_data=["Wrong Spotify Link"])
    else:
        return render_template('isrc.html')

@app.route('/api', methods=['GET', 'POST'])
def api():
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')
        
        try:
            from spotipy.oauth2 import SpotifyClientCredentials
            import spotipy
            cred = SpotifyClientCredentials(client_id, client_secret)
            test_sp = spotipy.Spotify(client_credentials_manager=cred)
            test_sp.search(q='test', limit=1)
            
            resp = make_response(redirect('/'))
            resp.set_cookie('SPOTIPY_CLIENT_ID', client_id, max_age=31536000)
            resp.set_cookie('SPOTIPY_CLIENT_SECRET', client_secret, max_age=31536000)
            return resp
        except Exception as e:
            return render_template('api.html', error=f"Invalid Credentials: {e}")
            
    return render_template('api.html')


asgi_app = WsgiToAsgi(app)
if __name__ == '__main__':
    import asyncio
    from hypercorn.config import Config
    from hypercorn.asyncio import serve
    asyncio.run(serve(app, Config()))
