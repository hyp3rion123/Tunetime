import requests, base64
from urllib.parse import urlencode

#TODO: ADD GENRE CARRYOVER - e.g if first is rock and soul, second has to be at least either rock or soul to be considered similar
#HOW - take all genres that are the same between the previous and current song and add to the list of genres to search for
def main():
    #Only using first genre so that we don't accidentally get very specific recommendations
    token = get_auth_token()
    first_song_artist_obj = search_song(token, "we will rock you")
    first_artist_id = first_song_artist_obj["artist_id"]
    first_song_id = first_song_artist_obj["song_id"]
    first_genres = get_artist_genres(token, first_artist_id)
    first_features = get_song_feature(token, first_song_id)

    sec_song_artist_obj = search_song(token, "the swan")
    sec_artist_id = sec_song_artist_obj["artist_id"]
    sec_song_id = sec_song_artist_obj["song_id"]
    sec_genres = get_artist_genres(token, sec_artist_id)
    sec_features = get_song_feature(token, sec_song_id)

    #print(get_similarity_score(token, first_song_id, sec_song_id, None))
    #Only (steps - 2) features because we already have the first and last song
    #Min steps is 2
    step_count = 15
    step_features = get_step_features(first_features, sec_features, step_count)
    #print(step_features)

    #Get recommendations based on step features
    song_list = []  #stores song objects
    song_list_names = [] #used to prevent duplicate songs - stores song names
    #ADD FIRST SONG(FIRST STEP)
    current_song = {
        "song_name": first_song_artist_obj["song_name"],
        "artist_name": first_song_artist_obj["artist_name"],
        "song_id": first_song_id,
        "artist_id": first_artist_id,
        "song_genre": first_genres
    }
    song_list.append(current_song)
    song_list_names.append(current_song["song_name"])
    #BUILD PLAYLIST
    for i in range(step_count-2):
        #INFLUENCE TOWARDS SECOND SONG
        if(i > ((step_count-2)/2)):
            current_song["song_genre"] = [current_song["song_genre"], sec_genres]
       # print("CURRENT SONG GENRES: " + str(current_song["song_genre"]))
        potential_songs = get_recommendations(
            token, 
            current_song["song_id"], 
            current_song["artist_id"], 
            current_song["song_genre"],
            step_features[i],
        )        
        #CHOOSE CLOSEST SONG THAT HASNT BEEN CHOSEN
        current_song = select_unchosen_song(token, potential_songs, song_list_names, step_features[i])
        print("how close is chosen song to desired song?: ", get_similarity_score(token, current_song["song_id"], None, step_features[i]))
        song_list.append(current_song)
        song_list_names.append(current_song["song_name"])
    current_song = {
        "song_name": sec_song_artist_obj["song_name"],
        "artist_name": sec_song_artist_obj["artist_name"],
        "song_id": sec_song_id,
        "artist_id": sec_artist_id,
        "song_genre": sec_genres
    }
    song_list.append(current_song)
    song_list_names.append(current_song["song_name"])
    #Print song names
    for song in song_list:
        print(song["song_name"] + " by " + song["artist_name"])
    #SIMILARITY SCORE
    similarity_scores_to_first = []
    similarity_scores_to_last = []
    similarity_scores_to_next = []
    i = 0
    for song in song_list:
        #print(song["song_name"] + " by " + song["artist_name"])
        similarity_scores_to_first.append(get_similarity_score(token, song_list[0]["song_id"], song["song_id"], None))
        similarity_scores_to_last.append(get_similarity_score(token, song_list[-1]["song_id"], song["song_id"], None))
        if (i < (len(song_list)-1)):
            similarity_scores_to_next.append(get_similarity_score(token, song_list[i+1]["song_id"], song["song_id"], None))
        i += 1
    print("SIMILARITY SCORES TO FIRST: ", similarity_scores_to_first)
    print("SIMILARITY SCORES TO LAST: ", similarity_scores_to_last)
    print("SIMILARITY SCORES TO EACH NEXT: ", similarity_scores_to_next)

def select_unchosen_song(auth_token, song_list, chosen_songs, step_features):
    most_similar_song = song_list[0]
    most_similar_score = 0
    #Choosing song is a based on feature similarity
    for i in range(len(song_list)):
        current_similarity = get_similarity_score(auth_token, song_list[i]["song_id"], None, step_features)
        if(song_list[i]["song_name"] not in chosen_songs and current_similarity > most_similar_score):
            most_similar_song = song_list[i]
            most_similar_score = current_similarity
            print("updated most similar song: ", most_similar_score)
    return most_similar_song

def get_similarity_score(auth_token, song_1, song_2, song_2_raw_features):
    first_song_features = get_song_feature(auth_token, song_1)
    if(song_2_raw_features):
        second_song_features = song_2_raw_features
    else :
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
        "tempo"
    }
    ignore_count = 0 #used to ommit features that are skewing average(e.g if one feature is zero there is no way to tell how similar the other is)
    for ftr in features:
        ftr_1 = float(first_song_features[ftr])
        ftr_2 = float(second_song_features[ftr])
        if(ftr_1 < 0 and ftr_2 < 0):
            ftr_1 = -1 * ftr_1
            ftr_2 = -1 * ftr_2
        elif(ftr_1 == 0 and ftr_2 == 0):
            ftr_1 = 1
            ftr_2 = 1
        elif(ftr_1 == 0 or ftr_2 == 0):
            ignore_count += 1
         #   print("cannot determine similarity for " + ftr)
            continue
        elif(min(ftr_1, ftr_2) / max(ftr_1, ftr_2) < 0.01):
            ignore_count += 1
         #   print("cannot determine similarity for " + ftr)
            continue
        similarity += min(ftr_1, ftr_2) / max(ftr_1, ftr_2)
       # print(min(ftr_1, ftr_2) / max(ftr_1, ftr_2), "% similarity in " + ftr)
    similarity = abs(similarity / (len(features) - ignore_count))
    #print("Total similarity: ", similarity)
    return similarity

def get_step_features(start_song_features, end_song_features, steps):
    target_feature_objs = []
    features = {
        "danceability",
        "energy",
        "loudness",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "tempo"
    }
    
    for i in range(steps-2):
        #Build the next step
        next_step = {}
        for ftr in features:
            next_step[ftr] = round(start_song_features[ftr] + (((end_song_features[ftr] - start_song_features[ftr])/(steps-1)) * (i+1)), 3)
        #Append next step to step array
        target_feature_objs.append(next_step)
    return target_feature_objs

def get_song_feature(auth_token, song_id):
    song_feature_request = {
        "url" : "https://api.spotify.com/v1/audio-features/" + song_id,
        "headers" : {
            'Authorization': 'Bearer ' + auth_token,
            'Content-Type': 'application/json',
        }
    }

    song_feature_response = requests.get(url=song_feature_request["url"], headers=song_feature_request["headers"])
    features = {
        "danceability",
        "energy",
        "loudness",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "tempo"
    }
    # for ftr in features:
    #     print(ftr + ": " + str(song_feature_response.json()[ftr]))
    # print('\n')
    
    return song_feature_response.json()


def get_recommendations(auth_token, seed_tracks, seed_artists, seed_genres, song_features):
    #print("calling get_recommendations with auth_token: ", auth_token, " seed_tracks: ", seed_tracks, " seed_artists ", seed_artists, " seed_genres: ", seed_genres)
    encoded_qparams = urlencode({
        'seed_artists': seed_artists,
        'seed_genres': seed_genres,
        'seed_tracks': seed_tracks,
        'limit': '10',
        'target_danceability': str(song_features["danceability"]),
        'target_energy': str(song_features["energy"]),
        'target_loudness': str(song_features["loudness"]),
        'target_speechiness': str(song_features["speechiness"]),
        'target_acousticness': str(song_features["acousticness"]),
        'target_instrumentalness': str(song_features["instrumentalness"]),
        'target_liveness': str(song_features["liveness"]),
        'target_tempo': str(song_features["tempo"]),
    })

    reccomend_request = {
        "url" : "https://api.spotify.com/v1/recommendations?" + encoded_qparams,
        "headers" : {
            'Authorization': 'Bearer ' + auth_token,
            'Content-Type': 'application/json',
        }
    }

    reccomend_response = requests.get(url=reccomend_request["url"], headers=reccomend_request["headers"])
    recommended_objs = []
    # print("RESPONSEEE: " , reccomend_response.json())
    for i in range(10):
        recommended_objs.append({
            "song_name": reccomend_response.json()["tracks"][i]["name"],
            "artist_name": reccomend_response.json()["tracks"][i]["artists"][0]["name"],
            "song_id": reccomend_response.json()["tracks"][i]["id"],
            "artist_id": reccomend_response.json()["tracks"][i]["artists"][0]["id"],
            "song_genre": get_artist_genres(auth_token, reccomend_response.json()["tracks"][i]["artists"][0]["id"])
        })
    #print("MY NEXT RECOMMENDATION IS: ", recommended_objs)
    return recommended_objs

def get_auth_token():
    client_id = '4ed89afd07c943c896d7a53da23cdaff'
    client_secret = 'f0e2a9ce27bd4629ba70073446f9633e'
    client_auth = client_id + ":" + client_secret
    auth_token = base64.b64encode(client_auth.encode('ascii')).decode('ascii')

    token_request = {
        "url" : "https://accounts.spotify.com/api/token",
        "body" : {
            "grant_type" : "client_credentials"
        },
        "headers" : {
            "Authorization" : "Basic " + auth_token,
            "Content-Type" : "application/x-www-form-urlencoded",
        }
    }

    response = requests.post(
        url=token_request["url"], 
        data=token_request["body"], 
        headers=token_request["headers"]
    )
    return response.json()["access_token"]

def get_artist_genres(auth_token, artist_id):
    search_request = {
        "url" : 'https://api.spotify.com/v1/artists/' + artist_id,
        "headers" : {
            'Authorization': 'Bearer ' + auth_token,
            'Content-Type': 'application/json',
        }
    }
    genre_response = requests.get(url=search_request["url"], headers=search_request["headers"])
    #print("GENRES: ", genre_response.json()["genres"])
    if genre_response.json()["genres"]:
        return genre_response.json()["genres"][0]
    return None

def search_song(auth_token, song_name):
    query_song = song_name.replace(" ", "%")
    encoded_req = urlencode({
        "q" : query_song,
        "type": "track",
    })

    search_request = {
        "url" : "https://api.spotify.com/v1/search?" + encoded_req,
        "headers" : {
            'Authorization': 'Bearer ' + auth_token,
            'Content-Type': 'application/json',
        }
    }

    search_response = requests.get(url=search_request["url"], headers=search_request["headers"])
    response_name = search_response.json()["tracks"]["items"][0]["name"]
    response_id = search_response.json()["tracks"]["items"][0]["id"]
    response_artist = search_response.json()["tracks"]["items"][0]["artists"][0]["name"]
    response_artist_id = search_response.json()["tracks"]["items"][0]["artists"][0]["id"]
   # print("Found song called " + response_name + " with id " + response_id)
    #print("This song is sung is sung by " + response_artist + " with id " + response_artist_id)
    return {
        "song_id" : response_id, 
        "artist_id" : response_artist_id,
        "song_name" : response_name,
        "artist_name" : response_artist,
    }

if __name__ == "__main__":
    main()