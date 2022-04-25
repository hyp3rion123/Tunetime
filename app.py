#Things to add in future:
#1. Create a dropdown menu on the song search for reccomendations based on what is being typed
#2. Double check playlist length when generated from events and make sure it lines up
#   We prefer to make the playlist longer than needed and remove songs with the lowest step accuracy until times match up
#3. Only take events from the next day that has at least one event(i.e don't take events from multiple days)
#4. Prevent users from directly accessing non-home endpoints

#from crypt import methods
#from curses.ascii import CR
#from re import search
#from xml.parsers import expat
import requests, base64
from ast import literal_eval
from math import floor
import datetime
import os
from urllib.parse import urlencode
#from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, render_template, request, redirect, url_for, json, make_response
#from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from werkzeug.exceptions import BadRequest

api = Flask(__name__)

@api.route("/login", methods=["GET"])
def login():
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    #User will land on /loginCallback once permissions are granted
    flow = Flow.from_client_secrets_file('./credentials.json', SCOPES, redirect_uri=os.environ["ROOT_URL"] + "/loginCallback")
    #Authorization URL is linked to Login button
    auth_url, _ = flow.authorization_url(prompt='consent')
    return render_template("login.html", auth_url=auth_url)

#Prevents direct access to the endpoints without authentication
def login_required(f):
    def decorated_function(*args, **kwargs):
        #check which endpoint is being accessed
        if (request.path == "/loginCallback" or request.path == '/callback') and request.args.get("code") is None:
            print("no code found")
            return redirect('/')
        elif request.cookies.get('google_token') is None or request.args.get("data") is None:
            return redirect('/')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    decorated_function.__doc__ = f.__doc__
    return decorated_function

@api.route("/loginCallback", methods=["GET"])
#@login_required
def login_callback():
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    #Extract code and exchange for token
    code = request.args.get("code")
    print("CODE: ", code)
    flow = Flow.from_client_secrets_file('./credentials.json', SCOPES, redirect_uri=os.environ["ROOT_URL"] + "/loginCallback")
    flow.fetch_token(code=code)
    #Set the token/exp cookies
    token = flow.credentials.token
    exp = flow.credentials.expiry
    resp = make_response(redirect(url_for("authorize")))
    resp.set_cookie("google_token", token, expires=exp)
    return resp

@api.route("/index", methods=["GET"])
#@login_required
def index():
    try:
        #Creds are guaranteed to be valid since they were refreshed in loginCallback
        creds = Credentials(
            token=request.cookies.get("google_token"),
            token_uri=os.environ["GOOGLE_TOKEN_URI"],
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            scopes=[os.environ["GOOGLE_TOKEN_SCOPES"]]
        )
        service = build('calendar', 'v3', credentials=creds)
        
        #Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        #three months from today
        timeMax = (datetime.datetime.utcnow() + datetime.timedelta(days=94)).isoformat() + 'Z'
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='primary', timeMin=now, timeMax=timeMax, singleEvents=True,
                                              orderBy='startTime').execute()                                    
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return render_template("index.html", events=[], data=request.args.get("data"))
        formatted_events = {}
        # Prints the start and name of the events
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            duration = (datetime.datetime.strptime(end, '%Y-%m-%dT%H:%M:%S%z') - datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z'))
            print(start, event['summary'], duration)

            event = {
                "start": event['start'],
                "end": event['end'],
                "summary": event['summary']
            }
            key = start[0:10]
            if key not in formatted_events:
                formatted_events[key] = [event]
            else:
                formatted_events[key].append(event)
        print(formatted_events)
    except HttpError as error:
        print('An error occurred: %s' % error)
    return render_template("index.html", events=formatted_events, data=request.args.get("data"))

@api.route("/buildPlaylist", methods=["GET"])
#@login_required
def build_playlist():
    # SEARCH FOR FIRST TWO SONGS - add some sort of error handling in case song doesn't exist
    token = request.args.get("token")
    playlist_url = ""
    user_name = ""
    # Using steps
    if request.args.get("first_song") != "":
        user_songs = [request.args.get("first_song"), request.args.get("last_song")]
        playlist_obj = build_playlist_from_steps(token, user_songs, int(request.args.get("steps_input")), False)
        playlist_url = playlist_obj["playlist_url"]
        user_name = playlist_obj["display_name"]
        #return {"songs": songs, "steps": request.args.get("steps_input")}
    #Using events
    else:    
        events = literal_eval(request.args.get("events"))
        #date_select = request.args.get("event_date_select")
        #print("DATE SELECT: ", date_select)
        event_songs = []
        for i in range(len(events)):
            event_songs.append(request.args.get("event_" + str(i+1) + "_" + events[i]["summary"] + "_song"))
        event_songs.append(request.args.get("last_song"))
        last_selected_event = int(request.args.get("last_selected_event"))
        playlist_obj = build_playlist_from_events(token, events, event_songs, last_selected_event)
        playlist_url = playlist_obj["playlist_url"]
        user_name = playlist_obj["display_name"]
        print("DISPLAY NAME IN BUILD PLAYLIST: ", user_name)
       # songs = json.dumps(songs, default=str)
    data = {
        "playlist_url" : playlist_url,
        "created_by" : user_name,
        "base_url" : os.environ["ROOT_URL"]
    }

    return render_template("info.html", data=data)

def build_playlist_from_events(token, events, event_songs, last_selected_event):
    time_intervals = []
    current_interval_index = 0
    #Find first song 
    for i in range(len(event_songs)):
        if(event_songs[i] != ""):
            current_interval_index = i
            break
    #Find next song 
    for i in range(current_interval_index+1, len(event_songs)-1):
        if(event_songs[i] != ""):
            end = datetime.datetime.strptime(events[i]["start"]["dateTime"], '%Y-%m-%dT%H:%M:%S%z')
            start = datetime.datetime.strptime(events[current_interval_index]["start"]["dateTime"], '%Y-%m-%dT%H:%M:%S%z')
            time_intervals.append(int((end-start).total_seconds()))#{"start": events[i]["start"], "end": events[i]["end"]})
            current_interval_index = i
    #Add last interval
    end = datetime.datetime.strptime(events[last_selected_event]["end"]["dateTime"], '%Y-%m-%dT%H:%M:%S%z')
    start = datetime.datetime.strptime(events[current_interval_index]["start"]["dateTime"], '%Y-%m-%dT%H:%M:%S%z')
    time_intervals.append(int((end-start).total_seconds()))

    #Remove empty songs
    #print("EVENT_SONGS: ", event_songs)
    songs_removed = 0
    for i in range(len(event_songs)-1):
        #print("i: ", i)
        if event_songs[i-songs_removed] == "":
            event_songs.pop(i-songs_removed)
            songs_removed+=1
    #print(event_songs)
    #Build playlist
    song_names = []
    song_ids = []
    song_objs = []
    for i in range(len(time_intervals)):
        interval_songs = [event_songs[i], event_songs[i+1]]
        interval_steps = floor(time_intervals[i] / 197) #average song length(Spotify 2020) is 3 minutes and 17 seconds = 197 seconds
        songs = build_playlist_from_steps(token, interval_songs, interval_steps, True)
        for id in songs["song_ids"]:
            song_ids.append(id)
        for name in songs["song_names"]:
            song_names.append(name)
    #Remove duplicate songs from interval boundaries
    #print("BEFORE songnames: ", song_names, "songids:", song_ids)
    song_names = list(dict.fromkeys(song_names))
    song_ids = list(dict.fromkeys(song_ids))
    #print("AFTER CUTTING SAME SONGS songnames: ", song_names, "songids:", song_ids)
    #Build array in format readable by modify_playlist spotify function
    for i in range(len(song_ids)):
        song_objs.append({
            "song_id" : song_ids[i],
            "song_name" : song_names[i],
        })
    #print("songobjs: ", song_objs)
    #Create the playlist in spotify
    user_obj = get_current_user_id(token)
    user_id = user_obj["id"]
    display_name = user_obj["display_name"]
    print("DISPLAY NAME IN BUILD PLAYLIST FROM EVENTS: ", display_name)
    playlist_name = "TuneTimePlaylist-" + datetime.datetime.today().strftime('%Y-%m-%d')
    playlist_create_response = create_spotify_playlist(token, user_id, playlist_name)
    playlist_modify_response = modify_spotify_playlist(token, playlist_create_response["id"], song_objs)
    return {
        "song_names" : song_names,
        "song_ids":song_ids,
        "playlist_creation" : playlist_modify_response,
        "playlist_url": playlist_create_response["external_urls"]["spotify"],
        "display_name": display_name
    }

def build_playlist_from_steps(token, user_songs, steps, called_from_events):
    for i in range(2):
        user_songs[i] = search_song(token, user_songs[i])
        # Add song genre too - used for song similarity comparison
        user_songs[i]["song_genre"] = get_artist_genres(token, user_songs[i]["artist_id"])
    # MIN STEPS = 2
    #print(get_song_feature(token, user_songs[0]["song_id"]))
    #print(get_song_feature(token, user_songs[1]["song_id"]))
    step_features = get_step_features(
        get_song_feature(token, user_songs[0]["song_id"]),
        get_song_feature(token, user_songs[1]["song_id"]),
        steps,
    )
    #print("step_features: ", step_features)
    # Get recommendations based on step features
    current_song = user_songs[0]
    songs = [current_song]
    song_list_names = [user_songs[0]["song_name"]]
    song_list_ids = [user_songs[0]["song_id"]]
    artist_names = [user_songs[0]["artist_name"]]
    for i in range(steps - 2):
        if i > ((steps - 2) / 2):
            current_song["song_genre"] = [
                current_song["song_genre"],
                user_songs[1]["song_genre"],
            ]
        potential_songs = get_recommendations(
            token,
            current_song["song_id"],
            current_song["artist_id"],
            current_song["song_genre"],
            step_features[i],
        )
        current_song = select_unchosen_song(
            token, potential_songs, song_list_names, step_features[i], artist_names
        )
        # Similarity scores
        current_song["similarity_score_first"] = round(
            get_similarity_score(
                token, user_songs[0]["song_id"], current_song["song_id"], None
            ),
            3,
        )
        current_song["similarity_score_last"] = round(
            get_similarity_score(
                token, user_songs[1]["song_id"], current_song["song_id"], None
            ),
            3,
        )
        songs.append(current_song)
        song_list_names.append(current_song["song_name"])
        song_list_ids.append(current_song["song_id"])
        artist_names.append(current_song["artist_name"])
    current_song = user_songs[1]
    songs.append(current_song)
    song_list_names.append(current_song["song_name"])
    song_list_ids.append(current_song["song_id"])
    artist_names.append(current_song["artist_name"])
    print("SONGS: ", songs)
    playlist_create_response = {
        "external_urls" : {
            "spotify" : "",
        }
    }
    display_name = ""
    #Create playlist in spotify
    if called_from_events == False: #without this we would have created a seperate playlist for each interval
        user_obj = get_current_user_id(token)
        user_id = user_obj["id"]
        display_name = user_obj["display_name"]
        print("DISPLAY NAME IN BUILD PLAYLIST FROM STEPS: ", display_name)
        playlist_create_response = create_spotify_playlist(token, user_id, "TuneTimePlaylist")
        playlist_modify_response = modify_spotify_playlist(token, playlist_create_response["id"], songs)
        print("PLAYLIST CREATION: ", playlist_modify_response)
    return {
        "song_names": song_list_names,
        "song_ids": song_list_ids, 
        "steps": steps, 
        "playlist_url": playlist_create_response["external_urls"]["spotify"],
        "display_name": display_name
    }

def get_song_feature(auth_token, song_id):
    song_feature_request = {
        "url": "https://api.spotify.com/v1/audio-features/" + song_id,
        "headers": {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
    }
    song_feature_response = requests.get(
        url=song_feature_request["url"], headers=song_feature_request["headers"]
    )
    return song_feature_response.json()

def modify_spotify_playlist(token, playlist_id, songs):
    data = {
        "uris": [
            "spotify:track:" + song["song_id"]
            for song in songs
        ]
    }
    playlist_modify_request = {
        "url": "https://api.spotify.com/v1/playlists/" + playlist_id + "/tracks",
        "headers": {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        "data": json.dumps(data),
    }
    playlist_modify_response = requests.post(
        url=playlist_modify_request["url"],
        headers=playlist_modify_request["headers"],
        data=playlist_modify_request["data"],
    )
    return playlist_modify_response.status_code

def create_spotify_playlist(auth_token, user_id, playlist_name):
    playlist_request = {
        "url": "https://api.spotify.com/v1/users/" + user_id + "/playlists",
        "headers": {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
        "data": json.dumps({"name": playlist_name, "public": False}),
    }
    playlist_response = requests.post(
        url=playlist_request["url"],
        headers=playlist_request["headers"],
        data=playlist_request["data"],
    )
    return playlist_response.json()

def get_current_user_id(auth_token):
    user_id_request = {
        "url": "https://api.spotify.com/v1/me",
        "headers": {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
    }
    user_id = requests.get(
        url=user_id_request["url"], headers=user_id_request["headers"]
    ).json()
    return user_id

def search_song(auth_token, song_name):
    query_song = song_name.replace(" ", "%")
    encoded_req = urlencode(
        {
            "q": query_song,
            "type": "track",
        }
    )

    search_request = {
        "url": "https://api.spotify.com/v1/search?" + encoded_req,
        "headers": {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
    }

    search_response = requests.get(
        url=search_request["url"], headers=search_request["headers"]
    )
    if (len(search_response.json()["tracks"]["items"]) == 0):
        err_msg = "Error, song " + song_name + " could not be found!"
        raise BadRequest(err_msg)

    response_name = search_response.json()["tracks"]["items"][0]["name"]
    response_id = search_response.json()["tracks"]["items"][0]["id"]
    response_artist = search_response.json()["tracks"]["items"][0]["artists"][0]["name"]
    response_artist_id = search_response.json()["tracks"]["items"][0]["artists"][0][
        "id"
    ]
    return {
        "song_id": response_id,
        "artist_id": response_artist_id,
        "song_name": response_name,
        "artist_name": response_artist,
    }


@api.route("/", methods=["GET"])
def authorize():
    #Ensure GOOGLE token is valid
    print("Searching for cookie...")
    token = request.cookies.get('google_token')
    if token is None:
        print("No cookie found ")
        return redirect(url_for("login"))
    client_id = "4ed89afd07c943c896d7a53da23cdaff"
    secret = "fsdkfansmd,fnas,df"
    red_uri = os.environ["ROOT_URL"] + "/callback"

    query_params = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": red_uri,
            "state": secret,
            "scope": "user-read-private playlist-read-private playlist-modify-private",
        }
    )

    token_request = {
        "url": "https://accounts.spotify.com/authorize?" + query_params,
    }
    #After user authorizes, redirects to /callback
    return redirect(token_request["url"])


@api.route("/callback", methods=["GET"])
#@login_required
def callback():
    client_id = "4ed89afd07c943c896d7a53da23cdaff"
    client_secret = "f0e2a9ce27bd4629ba70073446f9633e"
    client_auth = client_id + ":" + client_secret
    auth_token = base64.b64encode(client_auth.encode("ascii")).decode("ascii")
    token_request = {
        "url": "https://accounts.spotify.com/api/token",
        "body": {
            "grant_type": "authorization_code",
            "code": request.args.get("code"),
            "redirect_uri": os.environ["ROOT_URL"] + "/callback",
        },
        "headers": {
            "Authorization": "Basic " + auth_token,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    }

    response = requests.post(
        url=token_request["url"],
        data=token_request["body"],
        headers=token_request["headers"],
    )
    print("SPOTIFY AUTH RESPONSE: " + str(response.json()))
    return redirect(url_for("index", data=response.json()["access_token"]))


def add_playlist_to_spotify(auth_token, song_list):
    user_id_request = {
        "url": "https://api.spotify.com/v1/me",
        "headers": {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
    }
    user_id = requests.get(
        url=user_id_request["url"], headers=user_id_request["headers"]
    ).json()
    return user_id


def select_unchosen_song(auth_token, song_list, chosen_songs, step_features, artist_names):
    most_similar_song = song_list[0]
    most_similar_score = 0
    # Choosing song is a based on feature similarity
    for i in range(len(song_list)):
        current_similarity = get_similarity_score(
            auth_token, song_list[i]["song_id"], None, step_features
        )
        if (
            song_list[i]["song_name"] not in chosen_songs
            and current_similarity > most_similar_score
            and song_list[i]["artist_name"] not in artist_names
        ):
            most_similar_song = song_list[i]
            most_similar_score = current_similarity
            print("updated most similar song: ", most_similar_score)
    most_similar_song["percent_match"] = most_similar_score
    return most_similar_song


def get_similarity_score(auth_token, song_1, song_2, song_2_raw_features):
    first_song_features = get_song_feature(auth_token, song_1)
    if song_2_raw_features:
        second_song_features = song_2_raw_features
    else:
        second_song_features = get_song_feature(auth_token, song_2)
    similarity = 0
    features = {
        "danceability",
        "energy",
        "loudness",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "tempo",
    }
    ignore_count = 0  # used to ommit features that are skewing average(e.g if one feature is zero there is no way to tell how similar the other is)
    print("features for ", song_1, ": ", first_song_features)
    print("features for ", song_2, ": ", second_song_features)
    for ftr in features:
        if ftr in first_song_features and ftr in second_song_features:
            ftr_1 = float(first_song_features[ftr])
            ftr_2 = float(second_song_features[ftr])
            if ftr_1 < 0 and ftr_2 < 0:
                ftr_1 = -1 * ftr_1
                ftr_2 = -1 * ftr_2
            elif ftr_1 == 0 and ftr_2 == 0:
                ftr_1 = 1
                ftr_2 = 1
            elif ftr_1 == 0 or ftr_2 == 0:
                ignore_count += 1
                #   print("cannot determine similarity for " + ftr)
                continue
            elif min(ftr_1, ftr_2) / max(ftr_1, ftr_2) < 0.01:
                ignore_count += 1
                #   print("cannot determine similarity for " + ftr)
                continue
            similarity += min(ftr_1, ftr_2) / max(ftr_1, ftr_2)
        else :
            ignore_count += 1
            print("cannot determine similarity for " + ftr)
    # print(min(ftr_1, ftr_2) / max(ftr_1, ftr_2), "% similarity in " + ftr)
    similarity = abs(similarity / (len(features) - ignore_count))
    # print("Total similarity: ", similarity)
    return similarity


def get_step_features(start_song_features, end_song_features, steps):
    #print("ENTERING GET STEP FEATS FUNCTION")
    target_feature_objs = []
    features = {
        "danceability",
        "energy",
        "loudness",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "tempo",
    }

    for i in range(steps - 2):
        # Build the next step
        next_step = {}
        for ftr in features:
            next_step[ftr] = round(
                start_song_features[ftr]
                + (
                    ((end_song_features[ftr] - start_song_features[ftr]) / (steps - 1))
                    * (i + 1)
                ),
                3,
            )
        # Append next step to step array
        target_feature_objs.append(next_step)
    return target_feature_objs


def get_recommendations(
    auth_token, seed_tracks, seed_artists, seed_genres, song_features
):
    # print("calling get_recommendations with auth_token: ", auth_token, " seed_tracks: ", seed_tracks, " seed_artists ", seed_artists, " seed_genres: ", seed_genres)
    encoded_qparams = urlencode(
        {
            "seed_artists": seed_artists,
            "seed_genres": seed_genres,
            "seed_tracks": seed_tracks,
            "limit": "10",
            "target_danceability": str(song_features["danceability"]),
            "target_energy": str(song_features["energy"]),
            "target_loudness": str(song_features["loudness"]),
            "target_speechiness": str(song_features["speechiness"]),
            "target_acousticness": str(song_features["acousticness"]),
            "target_instrumentalness": str(song_features["instrumentalness"]),
            "target_liveness": str(song_features["liveness"]),
            "target_tempo": str(song_features["tempo"]),
        }
    )

    reccomend_request = {
        "url": "https://api.spotify.com/v1/recommendations?" + encoded_qparams,
        "headers": {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
    }

    reccomend_response = requests.get(
        url=reccomend_request["url"], headers=reccomend_request["headers"]
    )
    recommended_objs = []
    # print("RESPONSEEE: " , reccomend_response.json())
    for i in range(10):
        recommended_objs.append(
            {
                "song_name": reccomend_response.json()["tracks"][i]["name"],
                "artist_name": reccomend_response.json()["tracks"][i]["artists"][0][
                    "name"
                ],
                "song_id": reccomend_response.json()["tracks"][i]["id"],
                "artist_id": reccomend_response.json()["tracks"][i]["artists"][0]["id"],
                "song_genre": get_artist_genres(
                    auth_token,
                    reccomend_response.json()["tracks"][i]["artists"][0]["id"],
                ),
            }
        )
    # print("MY NEXT RECOMMENDATION IS: ", recommended_objs)
    return recommended_objs


def get_artist_genres(auth_token, artist_id):
    search_request = {
        "url": "https://api.spotify.com/v1/artists/" + artist_id,
        "headers": {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
    }
    genre_response = requests.get(
        url=search_request["url"], headers=search_request["headers"]
    )
    # print("GENRES: ", genre_response.json()["genres"])
    if genre_response.json()["genres"]:
        return genre_response.json()["genres"][0]
    return None


if __name__ == "__main__":
    api.debug = True
    api.run()
