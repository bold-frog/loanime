#!/usr/bin/env python3

import sys
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from pathlib import Path
from subprocess import check_call, check_output, DEVNULL


def soup(data):
    return BeautifulSoup(data, 'html.parser')


def video_duration(filename):
    return float(check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filename], encoding='utf-8'))


def get_metadata_parse(series_id, episode_id, lang):
    episode_html = soup(requests.get(f'https://hianime.to/ajax/v2/episode/servers?episodeId={episode_id}').json()['html'])
    media_id = int(episode_html.select_one(f'div.server-item[data-type="{lang}"]')['data-id'])

    media_link = requests.get(f'https://hianime.to/ajax/v2/episode/sources?id={media_id}').json()['link']
    megacloud_id = urlparse(media_link).path.split('/')[-1]

    metadata = requests.get(f'https://megacloud.tv/embed-2/ajax/e-1/getSources?id={megacloud_id}').json()
    return metadata


def get_metadata_script(script, series_id, episode_id, lang):
    return json.loads(check_output([script, series_id, episode_id, lang], encoding='utf-8'))


def scrap(series_id, lang, get_metadata):
    series_html = soup(requests.get(f'https://hianime.to/ajax/v2/episode/list/{series_id}').json()['html'])
    for episode_node in series_html.select('div.ss-list a.ep-item'):
        episode_num = int(episode_node['data-number'])
        episode_id = int(episode_node['data-id'])
        episode_name = {
            'dub': episode_node['title'],
            'sub': episode_node.select_one('div.ep-name')['data-jname'],
        }[lang].strip().replace('/', '∕')

        basename = f'{episode_num:02d} {episode_name}'
        if Path(f'{basename}.mp4').exists():
            print(f'Skipping "{basename}" (already downloaded)', file=sys.stderr)
            continue
        print(f'Downloading "{basename}"', file=sys.stderr)

        metadata = get_metadata(series_id, episode_id, lang)

        for track in metadata['tracks']:
            if track['kind'] == 'thumbnails':
                continue
            if track['kind'] == 'captions':
                ext = urlparse(track['file']).path.split('.')[-1]
                subtitles = requests.get(track['file']).content
                subtitles_lang = track['label'][:3].lower()
                with Path(f'{basename}.{subtitles_lang}.{ext}').open('wb') as f:
                    f.write(subtitles)
                continue
            print(f'WARNING: Unknown track kind "{track["kind"]}"!', file=sys.stderr)

        if metadata['encrypted']:
            print('WARNING: Video streams are encrypted, decryption is not supported :(', file=sys.stderr)
            continue
        if len(metadata['sources']) != 1:
            print('WARNING: Wrong number of sources!', file=sys.stderr)
        check_call(['ffmpeg', '-i', metadata['sources'][0]['file'], '-c', 'copy', '-f', 'mp4', f'{basename}.mp4.part'], stdout=DEVNULL, stderr=DEVNULL)

        if any([
            metadata['intro']['start'] > metadata['intro']['end'],
            metadata['intro']['end'] > metadata['outro']['start'] > 0,
            metadata['outro']['start'] > metadata['outro']['end'],
            ]):
            print('WARNING: Inconsistent intro and outro timestamps!')
        with Path(f'{basename}.chapters').open('wt') as f:
            duration = int(video_duration(f'{basename}.mp4.part') * 1000) - 1
            f.write(';FFMETADATA1\n')
            f.write('[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\n')
            if metadata['intro']['start'] > 0:
                f.write(f'END={metadata["intro"]["start"]*1000-1}\ntitle=Prologue\n')
                f.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={metadata["intro"]["start"]*1000}\n')
            if metadata['intro']['end'] > 0:
                f.write(f'END={metadata["intro"]["end"]*1000-1}\ntitle=Opening\n')
                f.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={metadata["intro"]["end"]*1000}\n')
            if metadata['outro']['start'] > 0:
                f.write(f'END={metadata["outro"]["start"]*1000-1}\ntitle=Movie\n')
                f.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={metadata["outro"]["start"]*1000}\n')
                f.write(f'END={metadata["outro"]["end"]*1000-1}\ntitle=Ending\n')
                if metadata['outro']['end'] * 1000 - 1 < duration:
                    f.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={metadata["outro"]["end"]*1000}\n')
                    f.write(f'END={duration}\ntitle=Epilogue\n')
            else:
                f.write(f'END={duration}\ntitle=Movie\n')

        check_call(['ffmpeg', '-i', f'{basename}.mp4.part', '-i', f'{basename}.chapters', '-map_metadata', '1', '-c', 'copy', f'{basename}.mp4'], stdout=DEVNULL, stderr=DEVNULL)
        Path(f'{basename}.mp4.part').unlink()
        Path(f'{basename}.chapters').unlink()


if __name__ == '__main__':
    try:
        series_id = int(sys.argv[1])
        lang = {'eng': 'dub', 'jap': 'sub'}[sys.argv[2]]
    except:
        print(f'usage: {sys.argv[0]} <series_id> eng|jap')
        sys.exit(1)

    if len(sys.argv) <= 3:
        scrap(series_id, lang, get_metadata_parse)
    else:
        scrap(series_id, lang, lambda series_id, episode_id, lang: get_metadata_script(sys.argv[3], series_id, episode_id, lang))
