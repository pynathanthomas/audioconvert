
'''
parses .cue files and splits audio
'''
import re
import os
import music_tag
from pathlib import Path

# input: str path of .cue file
# output: dict of cue info
'''
{
'artist': str
'album': str
'filepath': str
'tracklist': list of titles
'timestamps': list of stamps in seconds; starts at 0, ends at start of last track
}
'''

class Cue(object):
    def __init__(self, path):
        self.path = path
        self._info = {
            'album': None,
            'albumartist': None,
            'files': [],
        }
        parent_dir = '/'.join(self.path.split('/')[:-1])
        lines = open(self.path).readlines()

        for l in lines:
            if l.startswith('REM'):
                m = re.match(r'REM (\w+) "?([\w\d-]+)"?', l).groups()
                self._info[m[0].lower()] = m[1]
                continue
            elif l.startswith('PERFORMER'):
                self._info['albumartist'] = get_in_quotes(l)
                continue
            elif l.startswith('TITLE') and self._info['album'] is None:
                self._info['album'] = get_in_quotes(l)
                continue

            elif l.startswith('FILE'):
                self._info['files'].append({
                    'artist': self._info['albumartist'],
                    'album': self._info['album'],
                    'filepath': parent_dir + '/' + get_in_quotes(l),
                    'tracklist': [],
                    'timestamps': []
                })
                curr_file = len(self._info['files']) - 1

            # parse lines that are indented
            l = l.strip()
            if l.startswith('TITLE'):
                self._info['files'][curr_file]['tracklist'].append(get_in_quotes(l))
            elif l.startswith('INDEX'):
                stamp = re.findall('\d\d:\d\d:\d\d', l)[0]
                self._info['files'][curr_file]['timestamps'].append(format_time(stamp))
            else:
                continue

    # input: str timestamp in format hh:mm:ss
    # output: int timestamp in seconds
    def format_time(stamp):
        sl = stamp.split(':')
        mins = int(sl[0][0]) * 10 + int(sl[0][1])
        sec = int(sl[1][0]) * 10 + int(sl[1][1])
        ms = int(sl[2][0]) * 10 + int(sl[2][1])
        time = 60*mins + sec + ms / 100
        return time

    def format_query(self, q):
        return ''.join(re.findall('\w', q)).lower()

    def get(self, key):
        if key == 'tracklist':
            tracklist = []
            stamps = []
            for file in self._info['files']:
                tracklist.extend(file['tracklist'])
                stamps.extend(file['timestamps'])
            return list(zip(tracklist, stamps))
        elif key in ['artist', 'albumartist']:
            return self._info['albumartist']
        elif key in ['path', 'filepath', 'filepaths']:
            return [file['filepath'] for file in self._info['files']]
        else:
            return self._info[key]

    # TODO: add set function
    # TODO: add remove function





    def get_in_quotes(s):
        match = re.findall('"([^"]+)"', s)[0]
        return match

    def __getitem__(self, key):
        return self.get(self.format_query(key))

    def __setitem__(self, key, val):
        self.set(self.format_query(key), val)

    def __str__(self):
        tracklist = []
        for file in self._info['files']:
            tracklist.extend(file['tracklist'])
        tracks = '\n'.join(tracklist)
        s = f'Album: {self.get("album")}\nArtist: {self.get("artist")}\n\nTracks:\n{tracks}'
        return s










def parse_cue(cue_path):
    f = open(cue_path, 'r')
    parent_dir = '/'.join(cue_path.split('/')[:-1])
    lines = f.readlines()
    comments = []
    files = []
    album = ''
    for l in lines:
        # parse lines that are not indented
        if l.startswith('REM'):
            comments.append(l)
            continue
        if l.startswith('PERFORMER'):
            artist = get_in_quotes(l)
            continue
        if l.startswith('TITLE') and album == '':
            album = get_in_quotes(l)
            continue

        if l.startswith('FILE'):
            files.append({
                'artist': artist,
                'album': album,
                'filepath': parent_dir + '/' + get_in_quotes(l),
                'tracklist': [],
                'timestamps': []
            })
            curr_file = len(files) - 1

        # parse lines that are indented
        if 'TITLE' in l:
            files[curr_file]['tracklist'].append(get_in_quotes(l))
        elif 'INDEX' in l:
            # finds timestamp
            stamp = re.findall('\d\d:\d\d:\d\d', l)[0]
            files[curr_file]['timestamps'].append(format_time(stamp))
        else:
            continue


    # TODO: add support for REM comments
    return files


# returns whatever is in double quotes ("") inside the str
# input str: str to search
# output str: str in quotes
def get_in_quotes(s):
    match = re.findall('"([^"]+)"', s)[0]
    return match

# input: str timestamp in format hh:mm:ss
# output: int timestamp in seconds
def format_time(stamp):
    sl = stamp.split(':')
    mins = int(sl[0][0]) * 10 + int(sl[0][1])
    sec = int(sl[1][0]) * 10 + int(sl[1][1])
    ms = int(sl[2][0]) * 10 + int(sl[2][1])
    time = 60*mins + sec + ms / 100
    return time


# converts audio file to flac, splits into tracks
# renames and tags the new files
# input: cue dict
# output: None
def split_cue(cuesheet):
    for file in cuesheet:
        tracklist = file['tracklist']
        path = file['filepath']
        stamps = file['timestamps']
        ext = path.split('.')[-1]
        parent_dir = '/'.join(path.split('/')[:-1])

        # loops through titles, splits audio based on timestamp
        # adds metadata for album based on cue
        for i in range(len(tracklist)):
            start = stamps[i]

            if i is len(tracklist) - 1:
                end = None
            else:
                end = stamps[i + 1]

            title = tracklist[i]
            form_title = title.replace('/', '|')
            track_path = f'{parent_dir}/{form_title}.m4a'
            split_file(path, track_path, start, end)

            # tags new flac files
            f = music_tag.load_file(track_path)
            f['album'] = file['album']
            f['artist'] = file['artist']
            f['tracknumber'] = i + 1
            f['tracktitle'] = title

            files = []
            pathlist = Path(parent_dir).rglob(f'*front*')
            [files.append(f) for f in pathlist]
            if len(files) > 0:
                art = files[0]
                with open(art, 'rb') as img_in:
                        f['artwork'] = img_in.read()
            else:
                pass

            f.save()

        system(f'rm "{path}"')



def split_file(in_file, out_file, start, end):
    if end is None:
        length = None
        length_str = ''
    else:
        length = end - start
        length_str = f'-t {length}'

    command = f'ffmpeg -i "{in_file}" -map_metadata -1 -ss {start} {length_str} -vn -acodec alac -map 0:0 -y "{out_file}"'
    system(command)

