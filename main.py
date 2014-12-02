#!/usr/bin/env python

import requests
from twitter import *
import json
import os
import logging

FEEDLY_ACCESS_TOKEN_FILE = '.feedly_access_token'

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

class BitlyError(Exception):
    pass

def get_feedly_access_token():
    f = open(FEEDLY_ACCESS_TOKEN_FILE, 'r')
    token = f.read()
    f.close()
    return token.strip()

def save_feedly_access_token(token):
    f = open(FEEDLY_ACCESS_TOKEN_FILE, 'w')
    f.write(token)
    f.close()

def get_feedly_auth_header():
    token = get_feedly_access_token()
    return {"Authorization": "Bearer " + token}

def refresh_feedly_token(refresh_token):
    headers = get_feedly_auth_header()
    payload = {
        "refresh_token": refresh_token,
        "client_id": os.getenv("FEEDLY_CLIENT_ID"),
        "client_secret": os.getenv("FEEDLY_CLIENT_SECRET"),
        "grant_type": "refresh_token"
    }
    r = requests.post("https://cloud.feedly.com/v3/auth/token", data=json.dumps(payload), headers=headers)
    response = r.json()
    new_token = response['access_token']    
    return new_token

def get_unreads():
    headers = get_feedly_auth_header()
    r = requests.get("https://cloud.feedly.com/v3/markers/counts", headers=headers)
    json = r.json()
    unreadcounts = json["unreadcounts"]
    return [unread for unread in unreadcounts
            if not unread['count'] == 0 and unread['id'].startswith("feed/")]

def get_unread_entries(feed_id):
    unread_entries = []
    continuation = None
    title = None
    while True:
        title, entries, continuation = get_unread_entry(feed_id, continuation)
        unread_entries += entries
        if continuation is None:
            break
    return title, unread_entries

def get_unread_entry(feed_id, continuation=None):
    headers = get_feedly_auth_header()
    payload = {'streamId': feed_id, "unreadOnly": "true"}
    if continuation:
        payload['continuation'] = continuation
    r = requests.get("https://cloud.feedly.com/v3/streams/contents", params=payload, headers=headers)
    json = r.json()
    title = json.get('title')
    entries = [entry for entry in json['items'] if entry['unread']]
    if 'continuation' in json:
        continuation = json['continuation']
    else:
        continuation = None
    return title, entries, continuation

def shorten_url(long_url):
    params = {"access_token": os.getenv("BITLY_ACCESS_TOKEN"), "longUrl": long_url}
    r = requests.get("https://api-ssl.bitly.com/v3/shorten", params=params)
    json = r.json()
    if json['status_code'] != 200:
        raise BitlyError(r.text)
    data = json['data']
    return data['url']

def create_tweet_text(title, entry_title, url):
    TEXT_LIMIT = 116 # 23 chars are reserved for url
    LIMIT = 140

    def join_text_and_url(text, url):
        return text + " " + url

    if title:
        text = title + "/" + entry_title
    else:
        text = entry_title

    # first, shorten url
    if len(join_text_and_url(text, url)) > LIMIT:
        url = shorten_url(url)

    # shorten text if still over limit
    if len(join_text_and_url(text, url)) > LIMIT:
        over = len(text) - TEXT_LIMIT
        text = text[0:-1 * over - 1] + "…"

    return join_text_and_url(text, url)

def mark_an_entry_as_read(entry_id):
    headers = get_feedly_auth_header()
    payload = {
        "action": "markAsRead",
        "entryIds": [
            entry_id
        ],
        "type": "entries"
    }
    requests.post("https://cloud.feedly.com/v3/markers", data=json.dumps(payload), headers=headers)

def tweet(text):
    access_token_key = os.getenv("TWITTER_ACCESS_TOKEN_KEY")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
    t = Twitter(
        auth=OAuth(access_token_key, access_token_secret, consumer_key, consumer_secret))
    t.statuses.update(
        status=text)

if __name__ == "__main__":
    unreads = get_unreads()
    for unread in unreads:
        title, entries = get_unread_entries(unread['id'])
        for entry in entries:
            try:
                entry_id = entry['id']
                url = entry['alternate'][0]['href']
                entry_title = entry.get('title', '')
                text = create_tweet_text(title, entry_title, url)
                mark_an_entry_as_read(entry_id)
                logging.info(text)
                tweet(text)
            except BitlyError as e:
                logging.error(e.message)

    access_token = get_feedly_access_token()
    new_access_token = refresh_feedly_token(os.getenv("FEEDLY_REFRESH_TOKEN"))
    save_feedly_access_token(new_access_token)
