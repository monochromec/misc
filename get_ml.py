#!/usr/bin/env python3
#
# Poor man's podcatcher
# Motivation to build this was a podcast called Malicious Life changing its provider causing 
# my original RSS feed downloader to repeatly download episodes all named "stream.mp3" (the
# original file as offered by the RSS feed).
#
# The following code analyses the RSS feed, extracts some meta information from the individual entries,
# builds a filename from this metadata and downloads the episode if the filename is not already present
# in a particular location. As an addon, it copies ID3 v2 metadata from the RSS entry to the mp3 file
#
# Caveat: at the moment, the code uses the OS's native curl binary to download the mp3 files after extracting 
# the URLs from the feed entries as pycurl was way too slow. If somebody knows a hack to speed up
# pycurl, I am looking forward to a corresponding PR.
#
# The code relies heavily on the mutagen and feedparser packages in order to manipulate the ID3 tags and to 
# download and analyse the RSS feeds (https://mutagen.readthedocs.io/en/latest and https://pythonhosted.org/feedparser).
#
# It reads a config file called config.ini which should have the following format:
# [podcast name]
# path=<location of download path>
# url=<link to RSS feed>
# filename=<filename suffix in RSS feed items>
#
# The section name consists of the podcast name which is used for the filename creation in 
# get_feed. Depending on your preferences and file system, watch out for spaces in that name. 

import feedparser
import pathlib
import mutagen.easyid3
import urllib
import datetime
import configparser
import os
import shutil
import subprocess
import sys

# Check if desination exists
def check_presence(file_name):
   target = pathlib.Path(file_name)
   return target.exists()

# Parse date based on PUBLISHED tag from the RSS feed 
def get_date(date_parm):
    return datetime.datetime.strptime(date_parm, '%a, %d %b %Y %H:%M:%S %z')

# Store meta information extracted from RSS entries. A default ID3 
# is created if the downloaded audio file does not contain a corresponding
# header structure already.
def store_meta(target, entry, date):
    dest = pathlib.Path(target)
    if dest.exists():
        try:
            audio = mutagen.easyid3.EasyID3(target)
        except:
            audio = mutagen.easyid3.EasyID3()
    else:
        audio = mutagen.easyid3.EasyID3()
            
    audio['title'] = entry['title']
    audio['date'] = date
    try:
        audio.save(target, v2_version=3)
    except MutagenError as e:
        print('Could not save audio metadata: {}'.format(str(e)), file=sys.stderr)

# Download a single file based on the URL parameter. At the moment, this requires a native
# cURL binary as I couldn't get pycurl to run in a fast / performant way. Tips are welcome!
def download_mp3(file_name, url):
    # Use curl command for now, maybe substitued by pycurl later if performance problems are addressed
    success = True
    # Give it 5 minutes to download
    try:
        proc = subprocess.run(['curl', '-Lso', file_name, url], timeout=5*60)
    except: 
        print('Could not download {}'.format(url))
        sucess = False
    if proc.returncode != 0:
        print('curl returned exit code {}'.format(proc.returncode), file=sys.stderr)
        success = False
    return success

# Main working horse. Get RSS feed and iterate through the list of items, downloading these if a corresponding
# file doesn't exist a the configured location (or has file size 0).
def get_feed(path, url, show_name, suffix, date_func):
    rss = feedparser.parse(url)
    if 'bozo' in rss:
       print('Caught exception in RSS parse: {}', str(rss['bozo_exception']), file=sys.stderr)
    else:
        if rss.status == 200:
            # Sanitize title for proper file name
            for i in rss['items']:
                if 'title' in i:
                    name = i['title'].replace(' ', '.').replace('/', '-')
                else:
                    name = show_name
                    if 'published' in i:
                        date = date_func(i['published'])
                    else:
                        date = datetime.datetime.now()
                        # Transform according to ID3 v2 published format
                        date_id3 = date.strftime('%Y-%m-%d')
                        if 'links' in i:
                            li = i['links']
                            for j in li:
                                if 'href' in j:
                                    if j['href'].endswith(suffix):
                                        if name[-1] != '.':
                                            name += '.'
                                            file_name = path + '/' + name + date_id3 + '.mp3'
                                            if not check_presence(file_name) or os.path.getsize(file_name) == 0:
                                                # if download went OK, store metadata
                                                if download_mp3(file_name, j['href']):
                                                    store_meta(file_name, i, date_id3)
                                                else:
                                                    # Remove file if download went south
                                                    os.unlink(file_name)

# Main function: check for curl presence and read config.
def main():
    if shutil.which('curl') == None:
        print('No curl in $PATH, aborting', file=sys.stderr)
        return -1

    if check_presence('./config.ini'):
        parser = configparser.ConfigParser()
        parser.read('config.ini')
        for i in parser.sections():
            sec = parser[i]

            if len(sec['filename']) == 0:
                file_name = 'stream.mp3'
            else:
                file_name = sec['filename']

                path = sec['path']

            if os.path.isdir(path) and os.access(path, os.W_OK):
                get_feed(path, sec['url'], i, file_name, get_date)
            else:
                print('{} is not a path or not writable, skipping'.format(path), file=sys.stderr)
    else:
        print('No config.ini in current directory, exiting', file=sys.stderr)

if __name__ == '__main__':
    exit (main())
