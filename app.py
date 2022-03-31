from crypt import methods
from curses.ascii import CR
from re import search
import requests, base64
from ast import literal_eval
from math import floor
import datetime
import os
from urllib.parse import urlencode
from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, render_template, request, redirect, url_for, json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from werkzeug.exceptions import BadRequest

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
api = Flask(__name__)

@api.route("/index", methods=["GET"])
def index():
    # creds = Credentials(
    #     token=os.environ["GOOGLE_AUTH_TOKEN"],
    #     refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
    #     #id_token - if needed refresh creds like before, do to_json and obtain the id_token
    #     token_uri=os.environ["GOOGLE_TOKEN_URI"],
    #     client_id=os.environ["GOOGLE_CLIENT_ID"],
    #     client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    #     scopes=[os.environ["GOOGLE_TOKEN_SCOPES"]],
    #     expiry=datetime.datetime.strptime(os.environ["GOOGLE_TOKEN_EXPIRY"], '%Y-%m-%dT%H:%M:%S.%fZ')
    # )
    # # If there are no (valid) credentials available, let the user log in.
    #if not creds or not creds.valid:
    creds=None
    if creds==None:#if creds and creds.expired and creds.refresh_token:
        print("REFRESHING TOKEN")
        creds.refresh(Request())
        new_creds = creds.to_json()
        print("REFRESHED TOKEN: " + new_creds)
        os.environ["GOOGLE_AUTH_TOKEN"] = new_creds["token"]
        os.environ["GOOGLE_REFRESH_TOKEN"] = new_creds["refresh_token"]
        os.environ["GOOGLE_TOKEN_EXPIRY"] = new_creds["expiry"]
    #     else:
    #         flow = InstalledAppFlow.from_client_secrets_file(
    #             'credentials.json', SCOPES)
    #         creds = flow.run_local_server(port=5001)
    #     # Save the credentials for the next run
    #     with open('./token.json', 'w') as token:
    #         #token.write(creds.to_json())
    #         token.write("TEST123")
    #     with open('./token.json', 'r') as f:
    #         print(f.read())
    try:
        service = build('calendar', 'v3', credentials=creds)
        # calendars = service.calendarList().list().execute()
        # print(calendars)
        #Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()                                    
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return render_template("index.html", events=[], data=request.args.get("data"))

        # Prints the start and name of the next 10 events
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            duration = (datetime.datetime.strptime(end, '%Y-%m-%dT%H:%M:%S%z') - datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z'))
            print(start, event['summary'], duration)

    except HttpError as error:
        print('An error occurred: %s' % error)
    return render_template("index.html", events=events, data=request.args.get("data"))

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


@api.route("/buildPlaylist", methods=["GET"])
def build_playlist():
    # SEARCH FOR FIRST TWO SONGS - add some sort of error handling in case song doesn't exist
    token = request.args.get("token")
    # Using steps
    if request.args.get("first_song") != "":
        user_songs = [request.args.get("first_song"), request.args.get("last_song")]
        songs = build_playlist_from_steps(token, user_songs, int(request.args.get("steps_input")), False)
        return {"songs": songs, "steps": request.args.get("steps_input")}
    #Using events
    else:    
        events = literal_eval(request.args.get("events"))
        event_songs = []
        for i in range(len(events)):
            event_songs.append(request.args.get("event_" + str(i+1) + "_" + events[i]["summary"] + "_song"))
        event_songs.append(request.args.get("last_song"))
        songs = build_playlist_from_events(token, events, event_songs)
        songs = json.dumps(songs, default=str)

    return render_template("info.html")

def build_playlist_from_events(token, events, event_songs):
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
    end = datetime.datetime.strptime(events[-1]["end"]["dateTime"], '%Y-%m-%dT%H:%M:%S%z')
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
        interval_steps = floor(time_intervals[i] / 240) #average song length is 4 minutes = 240 seconds - 1 because we don't duplicate interval boundary songs
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
    user_id = get_current_user_id(token)
    playlist_name = "TuneTimePlaylist-" + datetime.datetime.today().strftime('%Y-%m-%d')
    playlist_create_response = create_spotify_playlist(token, user_id, playlist_name)
    playlist_modify_response = modify_spotify_playlist(token, playlist_create_response["id"], song_objs)
    return {"song_names" : song_names, "song_ids":song_ids, "playlist_creation" : playlist_modify_response}

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
    #Create playlist in spotify
    if called_from_events == False: #without this we would have created a seperate playlist for each interval
        user_id = get_current_user_id(token)
        playlist_create_response = create_spotify_playlist(token, user_id, "TuneTimePlaylist")
        playlist_modify_response = modify_spotify_playlist(token, playlist_create_response["id"], songs)
        #print("PLAYLIST CREATION: ", playlist_modify_response)
    
    return {"song_names": song_list_names,"song_ids": song_list_ids, "steps": steps}

# TODO: ADD GENRE CARRYOVER - e.g if first is rock and soul, second has to be at least either rock or soul to be considered similar
# HOW - take all genres that are the same between the previous and current song and add to the list of genres to search for

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
    return user_id["id"]

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
    return redirect(token_request["url"])


@api.route("/callback", methods=["GET"])
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
    # add_request = {
    #     "url" : "https://accounts.spotify.com/api/token",
    #     "body" : {
    #         "grant_type" : "client_credentials"
    #     },
    #     "headers" : {
    #         "Authorization" : "Basic " + auth_token,
    #         "Content-Type" : "application/x-www-form-urlencoded",
    #     }
    # }

    # response = requests.post(
    #     url=token_request["url"],
    #     data=token_request["body"],
    #     headers=token_request["headers"]
    # )
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
    for ftr in features:
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
            "limit": "20",
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
    api.run()

    # #def get_auth_token():
    # client_id = '4ed89afd07c943c896d7a53da23cdaff'
    # client_secret = 'f0e2a9ce27bd4629ba70073446f9633e'
    # client_auth = client_id + ":" + client_secret
    # secret = "fsdkfansmd,fnas,df"
    # #auth_token = base64.b64encode(client_auth.encode('ascii')).decode('ascii')

    # query_params = urlencode({
    #     "client_id": client_id,
    #     "response_type": "code",
    #     "redirect_uri": os.environ["ROOT_URL"] + "/callback",
    #     "state": secret,
    #     "scope" : "user-read-private playlist-read-private playlist-modify-private"
    # })

    # token_request = {
    #     "url" : "https://accounts.spotify.com/authorize?" + query_params,
    # }

    # token_response = requests.get(url=token_request["url"])
    # # token_request = {
    # #     "url" : "https://accounts.spotify.com/api/token",
    # #     "body" : {
    # #         "grant_type" : "client_credentials", "user-read-private"#, playlist-read-private, playlist-modify-private"
    # #     },
    # #     "headers" : {
    # #         "Authorization" : "Basic " + auth_token,
    # #         "Content-Type" : "application/x-www-form-urlencoded",
    # #     }
    # # }

    # # response = requests.post(
    # #     url=token_request["url"],
    # #     data=token_request["body"],
    # #     headers=token_request["headers"]
    # # )
    # # return token_response.json()#["access_token"]
    # return jsonify(token_response.json())
