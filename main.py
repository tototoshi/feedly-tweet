#!/usr/bin/env python

import requests
from twitter import *
import json
import os

def get_feedly_auth_header():
    return {"Authorization": "Bearer " + os.getenv("FEEDLY_ACCESS_TOKEN")}

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
    title = json['title']
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
    data = json['data']
    return data['url']

def create_tweet_text(title, entry_title, url):
    text = title + "/" + entry_title + " " + url
    if len(text) > 140:
        url = shorten_url(url)
        text = title + "/" + entry_title + " " + url
    if len(text) > 140:
        over = len(text) - 140
        entry_title = entry_title[0:-1 * over - 1] + "…"
        print(entry_title)
        text = title + "/" + entry_title + " " + url
    return text

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
            entry_id = entry['id']
            url = entry['alternate'][0]['href']
            entry_title = entry['title']
            text = create_tweet_text(title, entry_title, url)
            mark_an_entry_as_read(entry_id)
            print(text)
            tweet(text)
