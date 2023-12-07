#import necessary packages
import os
import pickle
import re
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd

#automatically sets credentials to none (assumes users have not been authenticated through google's OAuth)
credentials = None

#if the user has been authenticated already, set credentials to the previously set credentials
if os.path.exists("token.pickle"):
    print("Loading Credentials From File...")
    with open("token.pickle", "rb") as token:
        credentials = pickle.load(token)

#if the user has not been authenticated, authenticate with google's OAuth
if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
        print("Refreshing Access Token...")
        credentials.refresh(Request())
    else:
        print("Fetching New Tokens...")
        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secret.json", scopes=["https://www.googleapis.com/auth/youtube.readonly"],
            )
        flow.run_local_server(
            port=8080, prompt="consent", authorization_prompt_message=""
        )
        credentials = flow.credentials

        with open("token.pickle", "wb") as f:
            print("Saving Credentials for Future Use...")
            pickle.dump(credentials, f)


youtube = build("youtube", "v3", credentials= credentials)

#retrieve user history data
history_response = youtube.videos().list(
    part='snippet,contentDetails',
    myRating='like',
).execute()


# Function to get the full watch history with pagination
def get_full_watch_history(youtube):
    playlist_items = []
    next_page_token = None

    while True:
        request = youtube.videos().list(
            part='snippet,contentDetails',
            myRating='like',
            maxResults=50,  # Adjust as needed
            pageToken=next_page_token,
        )
        response = request.execute()

        items = response.get('items', [])
        playlist_items.extend(items)

        next_page_token = response.get('nextPageToken')

        if not next_page_token:
            break

    return playlist_items

def get_video_details(video_id, youtube):
    video_details = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()
    return video_details['items'][0]['snippet']


def get_top_channels_this_year(playlist_items, youtube, top_n=5):
    channel_duration = {}

    for item in playlist_items:
        video_id = item['id']
        snippet = item['snippet']

        video_details = get_video_details(video_id, youtube)
        channel_title = video_details['channelTitle']
        video_published_at = snippet['publishedAt']
        video_duration = parse_duration(item['contentDetails']['duration'])

        if video_published_at.startswith('2023'):
            channel_duration[channel_title] = channel_duration.get(channel_title, 0) + video_duration

    return sorted(channel_duration.items(), key=lambda x: x[1], reverse=True)[:top_n]

def get_top_channels_all_time(playlist_items, youtube, top_n=5):
    channel_duration = {}

    for item in playlist_items:
        video_id = item['id']
        video_details = get_video_details(video_id, youtube)
        channel_title = video_details['channelTitle']
        video_duration = parse_duration(item['contentDetails']['duration'])

        channel_duration[channel_title] = channel_duration.get(channel_title, 0) + video_duration

    return sorted(channel_duration.items(), key=lambda x: x[1], reverse=True)[:top_n]

def parse_duration(duration):
    match = re.match(r'PT(\d+H)?(\d+M)?(\d+S)?', duration)
    if not match:
        return 0

    hours = int(match.group(1)[:-1]) if match.group(1) else 0
    minutes = int(match.group(2)[:-1]) if match.group(2) else 0
    seconds = int(match.group(3)[:-1]) if match.group(3) else 0

    return hours * 3600 + minutes * 60 + seconds

# Function to get the total watch time
def get_total_watch_time(playlist_items):
    total_time = 0
    for item in playlist_items:
        total_time += parse_duration(item['contentDetails']['duration'])
    return total_time

'''def plot_time_over_time(history_data):
    df = pd.DataFrame(history_data, columns=['Date', 'Minutes Watched'])
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.resample('M', on='Date').sum()  # Resample by month

    plt.figure(figsize=(10, 5))
    plt.bar(df.index, df['Minutes Watched'], color='blue', alpha=0.7)
    plt.title('Total Watch Time Over Time (Per Month)')
    plt.xlabel('Month')
    plt.ylabel('Total Minutes Watched')
    plt.xticks(rotation=45, ha='right')  # Rotate x-axis labels for better readability
    plt.tight_layout()
    plt.show()'''

def create_pie_charts(playlist_items, youtube, top_n=5):
    def get_channel_info(video_id):
        video_details = get_video_details(video_id, youtube)
        channel_title = video_details['channelTitle']
        return channel_title

    def create_pie_chart(labels, sizes, title):
        plt.figure(figsize=(8, 8))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        plt.title(title)
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.show()

    # Extract relevant data
    channel_info_all_time = [get_channel_info(item['id']) for item in playlist_items]
    channel_info_this_year = [get_channel_info(item['id']) for item in playlist_items if item['snippet']['publishedAt'].startswith('2023')]

    # Get top channels
    top_channels_all_time = pd.Series(channel_info_all_time).value_counts().head(top_n)
    top_channels_this_year = pd.Series(channel_info_this_year).value_counts().head(top_n)

    # Create pie charts
    create_pie_chart(top_channels_all_time.index, top_channels_all_time.values, 'Top Channels Watched All Time')
    create_pie_chart(top_channels_this_year.index, top_channels_this_year.values, 'Top Channels Watched This Year')

# Extract relevant data
playlist_items = get_full_watch_history(youtube)

video_data = []
for item in playlist_items:
    video_id = item['id']
    snippet = item['snippet']

    video_details = get_video_details(video_id, youtube)

    video_title = snippet['title']
    channel_name = video_details['channelTitle']
    thumbnail_url = snippet['thumbnails']['default']['url']
    tags = video_details.get('tags', [])

    video_data.append({
        'Video Title': video_title,
        'Channel Name': channel_name,
        'Thumbnail URL': thumbnail_url,
        'Tags': tags
    })

# Convert to DataFrame for easy analysis
history_df = pd.DataFrame(video_data)
history_df.to_csv('YThistory.csv', index=True)

#print(history_df)

top_channels_this_year = get_top_channels_this_year(playlist_items, youtube)
print("Top 5 channels watched this year:")
for channel, channel_duration in top_channels_this_year[:5]:
    duration_minutes = channel_duration // 60
    print(f"{channel}: {duration_minutes} minutes")

top_channels_all_time = get_top_channels_all_time(playlist_items, youtube)
print("\nTop 5 channels watched all time:")
for channel, channel_duration in top_channels_all_time[:5]:
    duration_minutes = channel_duration // 60
    print(f"{channel}: {duration_minutes} minutes")

total_watch_time_this_year = get_total_watch_time(playlist_items)//60
print(f"\nTotal watch time this year: {total_watch_time_this_year} minutes")


history_data = [(item['snippet']['publishedAt'], parse_duration(item['contentDetails']['duration']))
                for item in playlist_items if 'snippet' in item and 'publishedAt' in item['snippet']]

# Convert the duration to minutes
history_data_minutes = [(published_at, duration // 60) for published_at, duration in history_data]

#plot_time_over_time(history_data_minutes)

create_pie_charts(playlist_items, youtube, top_n=5)