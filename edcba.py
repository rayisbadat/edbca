#!/usr/bin/env python
import logging
import os
from pprint import pprint
import shlex
import sys
import subprocess

import discid
import musicbrainzngs
import requests


encoder='oggenc'
musicbrainzngs.set_useragent("edcba cd ripper", "0.1", "")

def main():
    """
    """

    #Logging
    logger = logging.getLogger('edcba')
    #logger.setLevel(logging.INFO)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    #formatter = logging.Formatter('%(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    disc = discid.read()  # use default device
    logger.info("id: %s" % disc.id)
    
    try:
        result = musicbrainzngs.get_releases_by_discid(disc.id,includes=["artists", "recordings"])
    except musicbrainzngs.ResponseError:
        logger.critical("disc not found or bad response")
        raise Exception
    
    if result.get("disc"):
        r_index='disc'
    elif result.get("cdstub"):
        r_index='cdstub'
    else:
        logger.critical("couldnt get disc or cdstub")
        raise Exception
    
    #FIXME: Hardcoded to the first entry only for the disc_id
    try:
        release_id = result[r_index]["release-list"][0]['id']
        release_id_short = release_id.split("-")[0]
        release_artist = result[r_index]["release-list"][0]['artist-credit-phrase']
        release_title = result[r_index]["release-list"][0]['title']
        release_date = result[r_index]["release-list"][0]['date']
        release_year = release_date.split("-")[0]
        release_track_list = result[r_index]["release-list"][0]['medium-list'][0]['track-list']
    except KeyError:
        logger.critical("Couldnt find values")
        raise Exception
    except Exception as e:
        logger.critical(e)
        raise Exception

    #Genre not always there
    try:
        release_genre = result[r_index]["release-list"][0]['genre']
    except:
        release_genre = None


    try:
        cover_art_list = musicbrainzngs.get_image_list( release_id )
    except Exception:
        logger.critical( "Couldnt find values" )
        raise Exception
    try:
        cover_art_url = cover_art_list['images'][0]['image']
    except KeyError:
        logger.critical( "Couldnt extract URL" )
        raise Exception
    except Exception as e:
        logger.critical( e )
        raise Exception

    
    logger.info( "Release id: %s" %( release_id ) )
    logger.info( "Release id_short: %s" %( release_id_short ) )
    logger.info( "Release artist: %s" %( release_artist ) )
    logger.info( "Release title: %s" %( release_title ) )
    logger.info( "Release date: %s" %( release_date ) )
    logger.info( "Release year: %s" %( release_year ) )
    logger.info( "Album Art Url: %s" %( cover_art_url ) )
    #logger.info( "Release release_track_list: %s" %( release_track_list  ) )

    #Create the temp and dst directory
    wav_dir = "tmp_edcba.%s"%(release_id_short)
    enc_dir = "%s_%s"%(release_year,release_title.replace(" ","_"))
    album_art_file = "%s/cover.jpg"%(enc_dir)
    try:
        os.mkdir( wav_dir )
    except FileExistsError:
        logger.warning( "%s already exists" %( wav_dir) )
    except Exception as e:
        logger.critical( "Exception mkdir %s: " %(wav_dir,e) )
        raise Exception
    try:
        os.mkdir( enc_dir )
    except FileExistsError:
        logger.warning( "%s already exists" %( enc_dir) )
    except Exception as e:
        logger.critical( "Exception mkdir %s: " %(enc_dir,e) )
        raise Exception
    
    #Try to download album art
    try:
        r = requests.get(cover_art_url, stream=True)
        logger.debug( "Successfully downloaded %s"%(cover_art_url))
    except requests.exceptions as e:
        logger.critical( "Failed to download album art: %s"%(e) )
        raise Exception
    try:
        with open(album_art_file, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=128):
                fd.write(chunk)
        logger.info( "Successfully wrote album art from %s to %s ."%(cover_art_url,album_art_file))
    except Exception as e:
        logger.critical( "Failed to write album art to %s: %s"%(album_art_file,e) )
        raise Exception

    # Rip and encode each track
    for release_track in release_track_list:
        # Do I need position or number
        track_number = release_track['number'].zfill(2)
        track_position = release_track['position'].zfill(2)
        track_title = release_track['recording']['title']
    
        wav_file = "%s/%s_%s.wav"%( wav_dir, track_number, track_title.replace(" ","_"))
        enc_file = "%s/%s_%s.%s"%( enc_dir, track_number, track_title.replace(" ","_"), "ogg")

        #FIXME: Hardcoded to oggenc 
        #FIXME: change the --artist to the track artist from musicbrainz
        tag_flags = '--artist "%s" --album "%s" --title "%s" --date "%s" --tracknum "%s" --comment "albumartist=%s" --comment "CDDB=%s"'%(
            release_artist,
            release_title,
            track_title,
            release_date,
            track_number,
            release_artist,
            release_id_short,
        )

        if release_genre:
            tag_flags += ' --genre "%s"'

        rip_command = shlex.split( "%s -d %s %s %s"%("cdparanoia", "/dev/sr0", track_number, wav_file) )
        try:
            logger.debug( rip_command )
            #p1 = subprocess.check_call(rip_command, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            logger.critical( "cdparadnoia failed" )
            raise Exception
    
        encode_command=shlex.split( "%s %s --output %s %s"%(encoder, wav_file, enc_file, tag_flags) )
        pprint( encode_command )
        try:
            logger.debug( encode_command )
            p1 = subprocess.check_call( encode_command, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            logger.critical( "encoder failed" )
            raise Exception
    
  
if __name__ == "__main__":

    #Set up logging
    funcName = __name__
    
    main()
