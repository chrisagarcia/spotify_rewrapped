
from flask import Flask, render_template, request, redirect, url_for, make_response

# python modules for data manipulation and visualization
import pandas as pd
import mpld3
import seaborn as sns
import matplotlib

import os

# this fixes the problem with threading in matplotlib
matplotlib.use('Agg')

# spotify api authorization and call handling library
import spotipy
from spotipy.oauth2 import SpotifyOAuth


import requests
import base64
import json


def top_tracks_cleaner(data):
	x = []
	s = data['items']

	for i in s:
		x.append({
        	'song': i['name'],
            'album': i['album']['name'],
            'artists': [artist['name'] for artist in i['artists']],
            'id': i['id'],
            'popularity': i['popularity'],
            'img': i['album']['images'][0]['url']
            })
	
	return x

def top_artists_cleaner(data):
	x = []
	s = data['items']

	for i in s:
		x.append({
        	'artist': i['name'],
            'genres': i['genres'],
            'id': i['id'],
            'popularity': i['popularity'],
            'images': i['images'][0]['url']
			})
	
	return x


app = Flask(__name__)
app.secret_key = os.urandom(64)


# function passed to jinja
@app.context_processor
def track_string_format():
	
	def delengthener(name: str):
	
		if len(name) > 20:
			return name[:20] + '...'
	
		return name


	return dict(delengthener=delengthener)

client_id=os.environ['CLIENT_ID'],
client_secret=os.environ['CLIENT_SECRET']


# spotipy authentification object
auth_manager = SpotifyOAuth(
	scope=['user-top-read',
	'user-read-recently-played',
	'user-library-read'
	],
	client_id=client_id,
	client_secret=client_secret,
	redirect_uri=f"https://spotify-test-deployment.herokuapp.com/",
	show_dialog=True,
	)


# home route. renders index.html 
@app.route('/', methods=['GET', 'POST'])
def home():

	# executes if api sends a get request with the 'code' argument
	if request.args.get('code'):
		
		# this saves the auth token into a session object
		code = request.args.get('code')
		resp = make_response(redirect('user_data'))
		resp.set_cookies('code', code)

		return resp

	# initial load in template this renders essentially only renders on the first load
	return render_template('index.html')

@app.route('/user_data')
def user_data():

	code = request.cookies.get('code')
	
	auth_manager.get_access_token(code)
	sp = spotipy.Spotify(access_token)

	if not request.args.get('time_range'):
		return redirect(url_for('user_data', code=code, time_range='short_term', search='tracks'))

	# checks url for a num argument and assigns num variable to the arg
	# default is 10
	if request.args.get('num'):
		num = int(request.args.get('num'))
	else:
		num = 10


	# return your top tracks and a matplot viz
	if request.args.get('search') == 'tracks':

		# api call to get top songs in some range, clean and set as artist_df
		time_range = request.args['time_range']
		
		track_df = pd.DataFrame(top_tracks_cleaner(
				sp.current_user_top_tracks(limit=50, time_range=time_range)))

		# saving IDs for future calls
		id_list = track_df['id'].to_list()

		# api call to grab the features of those songs from their IDs
		features_json = sp.audio_features(id_list)
		features_artist_df = pd.DataFrame(features_json)

		# merge the two artist_df on their ID
		merged = pd.merge(track_df, features_artist_df).drop(labels=['uri', 'track_href', 'analysis_url', 'duration_ms'], axis=1)


		# plotting each feature / saving the svg in a dictionary
		sns.set_style('dark')
		sns.set_context("paper")

		histogram_svg_elements = {}
		histogrammable_features = ['popularity', 'key', 'loudness', 'tempo']

		for feature in histogrammable_features:
			song_feature_series = merged[feature]


			fig = sns.displot(data=song_feature_series, kde=True, height=4, aspect=1).set(ylabel=None, xlabel=None).fig


			# using mpld3 library to save as an html svg
			histogram_svg_elements[feature] = mpld3.fig_to_html(fig)
			matplotlib.pyplot.clf()


		features = merged[['danceability', 'energy', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence']]

		return render_template(
			'user_data.html',
			plots=histogram_svg_elements,
			data=merged,
			time=time_range,
			num=num,
			code=code
			)

	
	#return your top artists
	if request.args.get('search') == 'artists':

		# api call to get top songs in some range, clean and set as artist_df
		time_range = request.args['time_range']
		
		artist_df = pd.DataFrame(top_artists_cleaner(
				sp.current_user_top_artists(limit=50, time_range=time_range)))

		# collecting genres
		genre_dict = {}
		for genre_list in artist_df['genres'].to_list():
			for genre in genre_list:
				for word in genre.split():
					if word not in genre_dict:
						genre_dict[word] = 1
					else:
						genre_dict[word] += 1
		
		# grab top user genres
		top_10_genre_2dlist = sorted(genre_dict.items(), key=lambda item: item[1])[:10]

		# ax = sns.barplot(data=top_10_genre_2dlist)
		# genre_plot = ax.get_figure()

		return  render_template(
			'user_data_artists.html',
			data=artist_df,
			time=time_range,
			num=num,
			code=code
			)




	# if neither condition is met
	return '<a href="/">Home</a>'



# this route is essentially only the middleman so the page doesnt save
@app.route('/login', methods=['POST'])
def login_function():

	auth_url = auth_manager.get_authorize_url()
	return redirect(auth_url)



if __name__ == '__main__':
	app.run(debug=True)