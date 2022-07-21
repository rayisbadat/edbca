import sys
import discid
import musicbrainzngs
import subprocess
import shlex

from pprint import pprint


disc = discid.read()  # use default device
pprint("id: %s" % disc.id) # Python 3
#pprint( vars(disc)['_handle'] )


musicbrainzngs.set_useragent("edcba cd ripper", "0.1", "")

try:
    #result = musicbrainzngs.get_releases_by_discid(disc.id,includes=["artists"])
    result = musicbrainzngs.get_releases_by_discid(disc.id,includes=["artists", "recordings"])
    #pprint( result )
    #pprint( result["disc"]["release-list"][0] )
    #pprint( result["disc"]["release-list"][0]['id'] )
except musicbrainzngs.ResponseError:
    print("disc not found or bad response")
    raise Exception

if result.get("disc"):
    #print("artist:\t%s" % result["disc"]["release-list"][0]["artist-credit-phrase"])
    #print("title:\t%s" % result["disc"]["release-list"][0]["title"])
    r_index='disc'
elif result.get("cdstub"):
    r_index='cdstub'
    #print("artist:\t" % result["cdstub"]["artist"])
    #print("title:\t" % result["cdstub"]["title"])
else:
    raise Exception

#FIXME: Hardcoded to the first entry only for the disc_id
try:
    #pprint( result[r_index] )
    release_id = result[r_index]["release-list"][0]['id']
    release_artist = result[r_index]["release-list"][0]['artist-credit-phrase']
    release_title = result[r_index]["release-list"][0]['title']
    release_date = result[r_index]["release-list"][0]['date']
    release_track_list = result[r_index]["release-list"][0]['medium-list'][0]['track-list']
except KeyError:
    pprint( "Couldnt find values" )
    raise Exception

pprint( "Release id: %s" %( release_id ) )
pprint( "Release artist: %s" %( release_artist ) )
pprint( "Release title: %s" %( release_title ) )
pprint( "Release date: %s" %( release_date ) )
#pprint( "Release release_track_list: %s" %( release_track_list  ) )

try:
    cover_art_list = musicbrainzngs.get_image_list( release_id )
    #pprint( cover_art_list )
    #pprint( cover_art_list['images'][0]['image'] )
except Exception:
    pprint( "Couldnt find values" )
    raise Exception

wav_dir = "abcde.820a8a0b"
enc_dir = "abcde.820a8a0b"
for release_track in release_track_list:
    #pprint( release_track )
    # Do I need position or number
    track_number = release_track['number'].zfill(2)
    track_position = release_track['position'].zfill(2)
    track_title = release_track['recording']['title'].replace(" ","_")
    pprint( track_title )

    wav_file = "%s/%s_%s.wav"%( wav_dir, track_number, track_title)
    enc_file = "%s/%s_%s.%s"%( enc_dir, track_number, track_title, "ogg")

    rip_command = shlex.split( "%s -d %s %s %s"%("cdparanoia", "/dev/sr0", track_number, wav_file) )
    try:
        pprint( rip_command )
        p1 = subprocess.check_call(rip_command, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError:
        pprint( "cdparadnoia failed" )
        raise Exception

    encoder='oggenc'
    encode_command=shlex.split( "%s %s --output %s"%(encoder, wav_file, enc_file) )
    try:
        pprint( encode_command )
        p1 = subprocess.check_call( encode_command, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError:
        pprint( "encoder failed" )
        raise Exception

