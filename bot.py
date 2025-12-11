import telebot
from telebot import types
from flask import Flask, request
import threading
import requests
import urllib.parse
from config import TELEGRAM_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from db import save_user_token, get_user_token

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

REDIRECT_URI = "https://unimitated-lyric-presumptuously.ngrok-free.dev/callback"
SCOPE = "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-read-private user-read-email user-library-read"

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    auth_url = (
        "https://accounts.spotify.com/authorize?"
        f"client_id={SPOTIFY_CLIENT_ID}&"
        "response_type=code&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"scope={urllib.parse.quote(SCOPE)}&"
        f"state={user_id}"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    btn = telebot.types.InlineKeyboardButton("Войти через Spotify", url=auth_url)
    markup.add(btn)
    bot.send_message(message.chat.id, "Чтобы пользоваться ботом -войдите в свой Spotify аккаунт:", reply_markup=markup)

def send_inline_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("Мои плейлисты", callback_data="menu_playlist")
    btn2 = types.InlineKeyboardButton("Найти трек", callback_data="menu_search")
    btn3 = types.InlineKeyboardButton("Похожие треки", callback_data="menu_recommend")
    btn4 = types.InlineKeyboardButton("Добавить трек в плейлист", callback_data="menu_add_track")
    btn5 = types.InlineKeyboardButton("Анализ трека", callback_data="menu_analyze")
    markup.add(btn1, btn2, btn3, btn4, btn5)
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

@bot.message_handler(commands=['menu'])
def menu(message):
    send_inline_menu(message.chat.id)

def get_user_playlists(user_id):
    token = get_user_token(user_id)
    if not token:
        return None
    access_token, refresh_token = token
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(
        "https://api.spotify.com/v1/me/playlists",
        headers = headers
    )
    data = response.json()
    return data["items"]

@bot.callback_query_handler(func=lambda call: call.data == "menu_playlist")
def show_playlists(call):
    user_id = call.from_user.id
    playlists = get_user_playlists(user_id)
    if len(playlists) == 0:
        bot.send_message(call.message.chat.id, "У вас нет плейлистов.")
        return
    text = "*Ваши плейлисты:*\n\n"
    for pl in playlists:
        name = pl['name']
        url = pl['external_urls']['spotify']
        tracks = pl['tracks']['total']
        text += f"• [{name}]({url}) -{tracks} треков\n"
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "menu_search")
def ask_track_name(call):
    bot.send_message(call.message.chat.id, "Введите название трека:")
    bot.register_next_step_handler(call.message, process_track_query)

def search_track(user_id, query):
    token = get_user_token(user_id)
    if not token:
        return None
    access_token, refresh_token = token
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "q": query,
        "type": "track",
        "limit": 5
    }
    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers,
        params=params
    )
    return response.json()["tracks"]["items"]

def process_track_query(message):
    user_id = message.from_user.id
    query = message.text
    tracks = search_track(user_id, query)
    if not tracks or len(tracks) == 0:
        bot.send_message(message.chat.id, "Ничего не найдено.")
        return
    text = "*Найденные треки:*\n\n"
    for i in tracks:
        name = i["name"]
        artists = ", ".join(a["name"] for a in i["artists"])
        url = i["external_urls"]["spotify"]
        text += f"• [{name} -{artists}]({url})\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "menu_recommend")
def ask_similar_track(call):
    bot.send_message(call.message.chat.id, "Пришлите ссылку на трек Spotify:")
    bot.register_next_step_handler(call.message, process_similar_track)

def get_artist_top_tracks(user_id, track_id):
    token = get_user_token(user_id)
    if not token:
        return None
    access_token, refresh_token = token
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    track_res = requests.get(
        f"https://api.spotify.com/v1/tracks/{track_id}",
        headers=headers
    )
    artist_id = track_res.json()["artists"][0]["id"]
    top_res = requests.get(
        f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks",
        headers=headers
    )
    return top_res.json().get("tracks", [])

def process_similar_track(message):
    user_id = message.from_user.id
    url = message.text
    if "open.spotify.com/track/" not in url:
        bot.send_message(message.chat.id, "Это не похоже на ссылку трека.")
        return
    track_id = url.split("track/")[1].split("?")[0]
    bot.send_message(message.chat.id, "Ищу похожие треки...")
    tracks = get_artist_top_tracks(user_id, track_id)
    if not tracks:
        bot.send_message(message.chat.id, "Не удалось найти похожие треки.")
        return
    text = "*Похожие треки (по артисту):*\n\n"
    for t in tracks[:5]:
        name = t["name"]
        artists = ", ".join(a["name"] for a in t["artists"])
        link = t["external_urls"]["spotify"]

        text += f"• [{name} -{artists}]({link})\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "menu_add_track")
def add_track_menu(call):
    bot.send_message(call.message.chat.id, "Введите название трека, который хотите добавить:")
    bot.register_next_step_handler(call.message, add_track_search)

def add_track_search(message):
    user_id = message.from_user.id
    query = message.text
    tracks = search_track(user_id, query)
    if not tracks:
        bot.send_message(message.chat.id, "Трек не найден.")
        return
    track = tracks[0]
    track_id = track["id"]
    track_name = track["name"]
    artists = ", ".join(a["name"] for a in track["artists"])
    bot.send_message(message.chat.id, f"Трек найден: *{track_name} -{artists}*\n\nТеперь выберите плейлист.", parse_mode="Markdown")
    show_playlist_selection(message, track_id)

def show_playlist_selection(message, track_id):
    user_id = message.from_user.id
    playlists = get_user_playlists(user_id)
    if not playlists:
        bot.send_message(message.chat.id, "У вас нет плейлистов.")
        return
    markup = types.InlineKeyboardMarkup()
    for pl in playlists:
        btn = types.InlineKeyboardButton(
            pl["name"],
            callback_data=f"addtrack_{track_id}_{pl['id']}"
        )
        markup.add(btn)
    bot.send_message(message.chat.id, "Выберите плейлист:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("addtrack_"))
def add_track_to_playlist(call):
    user_id = call.from_user.id
    parts = call.data.split("_")
    track_id = parts[1]
    playlist_id = parts[2]
    token = get_user_token(user_id)
    if not token:
        bot.send_message(call.message.chat.id, "Ошибка авторизации.")
        return
    access_token, refresh_token = token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    payload = {
        "uris": [f"spotify:track:{track_id}"]
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code in (200, 201):
        bot.send_message(call.message.chat.id, "Трек успешно добавлен в плейлист!")
    else:
        return

@bot.callback_query_handler(func=lambda call: call.data == "menu_analyze")
def ask_track_for_analysis(call):
    bot.send_message(call.message.chat.id, "Пришлите ссылку на трек Spotify:")
    bot.register_next_step_handler(call.message, process_track_analysis)

def process_track_analysis(message):
    user_id = message.from_user.id
    text = message.text
    if "open.spotify.com/track/" not in text:
        bot.send_message(message.chat.id, "Пришлите корректную ссылку на трек.")
        return
    track_id = text.split("track/")[1].split("?")[0]
    bot.send_message(message.chat.id, "Анализирую трек...")
    result = analyze_track(user_id, track_id)
    if not result:
        bot.send_message(message.chat.id, "Ошибка анализа.")
    else:
        bot.send_message(message.chat.id, result, parse_mode="Markdown")

def analyze_track(user_id, track_id):
    token_data = get_user_token(user_id)
    if not token_data:
        return "Вы не авторизованы. Введите /start"
    access_token, refresh_token = token_data
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    track_res = requests.get(
        f"https://api.spotify.com/v1/tracks/{track_id}",
        headers=headers)
    track_res = track_res.json()
    artist_id = track_res["artists"][0]["id"]

    artist_res = requests.get(
        f"https://api.spotify.com/v1/artists/{artist_id}",
        headers=headers)
    artist_res = artist_res.json()

    album_id = track_res["album"]["id"]
    album_res = requests.get(
        f"https://api.spotify.com/v1/albums/{album_id}",
        headers=headers)
    album_res = album_res.json()

    track_name = track_res["name"]
    artists = ", ".join(a["name"] for a in track_res["artists"])
    duration = track_res["duration_ms"] // 1000
    album_name = album_res["name"]
    release_date = album_res["release_date"]
    artist_genres = ", ".join(artist_res.get("genres", [])) or "Жанры не указаны"
    followers = artist_res["followers"]["total"]

    text = f"""
*Анализ трека -{track_name}*
Исполнитель: *{artists}*

*Длительность:* {duration // 60} мин {duration % 60} сек  

*Анализ исполнителя:*  
Фолловеры: {followers:,}  
Жанры: {artist_genres}

*Альбом:* {album_name}  
Дата релиза: {release_date}  
Треков в альбоме: {album_res["total_tracks"]}
"""
    return text

@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return "Missing code or state"
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET
        }
    )
    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token:
        return f"Error: {token_data}"
    save_user_token(int(state), access_token, refresh_token)
    bot.send_message(int(state), "Вы успешно авторизованы в Spotify!")
    send_inline_menu(int(state))
    return "Авторизация завершена. Можете закрыть вкладку."
def run_flask():
    app.run(port=5000)

threading.Thread(target=run_flask).start()
bot.infinity_polling(timeout=20, long_polling_timeout=15)
