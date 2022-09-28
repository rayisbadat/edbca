#!/usr/bin/env python
import logging
import os
import shlex
import sys
import subprocess
import re
import argparse

#Musicbrainz
import discid
import musicbrainzngs
import requests

#Debug
from pprint import pprint

#Logging
logger = logging.getLogger('edcba')
logger.setLevel(logging.INFO)
#logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s: %(message)s')
#formatter = logging.Formatter('%(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

#Hard coded encoder
encoder='oggenc'

#Set useragent needed by musicbrainz db
musicbrainzngs.set_useragent("edcba cd ripper", "0.1", "")

def clean_string( string_value):
    """
    Cleans up strings to make safe for writing to filesystem
    """

    #Inverse match, so we sub out anything not in regex
    regex="[^a-zA-z0-9()]+"
    regexed_string = re.sub(regex, "_", string_value)
    return regexed_string.rstrip("_")

def validate_disc_id( disc_id ):
  if disc_id:
    return disc_id
  raise ValueError

def validate_release_id( release_id ):
  if release_id:
    return release_id
  raise ValueError

def validate_release_group_id( release_group_id ):
  if release_group_id:
    return release_group_id
  raise ValueError   

def main( args=None ):
    """
    """

    if args.disc_id:
        disc_id = args.disc_id
    else:
        disc = discid.read()  # use default device
        disc_id = disc.id
    logger.info("id: %s" % disc_id)

    if args.release_group_id:
        release_group_id = args.release_group_id
    else:
        release_group_id = None

    try:
        if args.release_id:
            result_raw = musicbrainzngs.get_release_by_id(args.release_id,includes=["artists", "recordings"])
        else:
            result_raw = musicbrainzngs.get_releases_by_discid(disc_id,includes=["artists", "recordings"])
        logger.debug( result_raw )
    except musicbrainzngs.ResponseError:
        logger.critical("disc not found or bad response")
        exit(1)
        raise Exception
    
    if result_raw.get("disc"):
        r_index='disc'
        s_index='release-list'
        result=result_raw[r_index][s_index][0]
    elif result_raw.get("cdstub"):
        r_index='cdstub'
        s_index='release-list'
        result=result_raw[r_index][s_index][0]
    elif result_raw.get("release"):
        r_index='release'
        s_index='medium-list'
        result=result_raw[r_index]
    else:
        logger.critical("couldnt get disc or cdstub key index")
        raise Exception

    #FIXME: Hardcoded to the first entry only for the disc_id
    try:
        release_id = result['id']
        release_id_short = release_id.split("-")[0]
        release_artist = result['artist-credit-phrase']
        release_title_raw = result['title']
        release_title_clean = clean_string( release_title_raw )
        release_track_list = result['medium-list'][0]['track-list']
    except KeyError:
        logger.critical("Couldnt find values")
        raise Exception
    except Exception as e:
        logger.critical(e)
        raise Exception

    try:
        release_date = result['date']
        release_year = release_date.split("-")[0]
    except:
        release_date = '0000-00-00'
        release_year = release_date.split("-")[0]

    #Genre not always there
    try:
        release_genre = result['genre']
    except:
        release_genre = None

    #If we were given a release group extract album art list
    cover_art_list=None
    if release_group_id:
        try:
            cover_art_list=musicbrainzngs.get_release_group_image_list( release_group_id )
        except:
            cover_art_list=None
            logger.debug("Could not pull image list from release group id: %s"%( release_group_id ) )

    # Try to pull album art from release and if not try release-group
    if not cover_art_list:
        try:
            cover_art_list = musicbrainzngs.get_image_list( release_id )
        except:
            if 'artist' in result.keys():
                artist_id = result['artist']['id']
            elif 'artist-credit' in result.keys():
                artist_id = result['artist-credit'][0]['artist']['id']
            else:
                artist_id = None

            if artist_id:
                release_group_id=musicbrainzngs.search_release_groups(arid=artist_id,reid=release_id,strict=True)['release-group-list'][0]['id']
                cover_art_list=musicbrainzngs.get_release_group_image_list( release_group_id )
                logger.warn( "Couldnt find value cover_art_list" )
            else:
                cover_art_list=None

    if cover_art_list:
      try:
          cover_art_url = cover_art_list['images'][0]['image']
      except KeyError:
          logger.critical( "Couldnt extract cover_art_list URL" )
          raise Exception
      except Exception as e:
          logger.critical( e )
          raise Exception
    else:
        cover_art_url = None
    
    logger.info( "Release id: %s" %( release_id ) )
    logger.info( "Release id_short: %s" %( release_id_short ) )
    logger.info( "Release artist: %s" %( release_artist ) )
    logger.info( "Release title: %s" %( release_title_clean ) )
    logger.info( "Release date: %s" %( release_date ) )
    logger.info( "Release year: %s" %( release_year ) )
    logger.info( "Album Art Url: %s" %( cover_art_url ) )
    #logger.info( "Release release_track_list: %s" %( release_track_list  ) )

    #Create the temp and dst directory
    wav_dir = "tmp_edcba.%s"%(release_id_short)
    enc_dir = "%s_%s"%(release_year,release_title_clean)
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
    if cover_art_url:
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
        track_title_raw = release_track['recording']['title']
        track_title_clean=clean_string( track_title_raw )
    
        wav_file = '%s/%s_%s.wav'%( wav_dir, track_number, track_title_clean)
        enc_file = '%s/%s_%s.%s'%( enc_dir, track_number, track_title_clean, 'ogg')

        #FIXME: Hardcoded to oggenc 
        #FIXME: change the --artist to the track artist from musicbrainz
        logger.debug( '%s: %s'%( 'release_artist', release_artist ))
        logger.debug( '%s: %s'%( 'release_title_raw', release_title_raw ))
        logger.debug( '%s: %s'%( 'release_title_clean', release_title_clean ))
        logger.debug( '%s: %s'%( 'track_title_clean', track_title_clean ))
        logger.debug( '%s: %s'%( 'track_title_raw', track_title_raw ))
        logger.debug( '%s: %s'%( 'release_date', release_date ))
        logger.debug( '%s: %s'%( 'track_number', track_number ))
        logger.debug( '%s: %s'%( 'release_artist', release_artist ))
        logger.debug( '%s: %s'%( 'release_id_short', release_id_short ))

        tag_flags = '--artist "%s" --album "%s" --title "%s" --date "%s" --tracknum "%s" --comment "albumartist=%s" --comment "CDDB=%s"'%(
            release_artist,
            release_title_raw,
            track_title_raw,
            release_date,
            track_number,
            release_artist,
            release_id_short,
        )
        if release_genre:
            tag_flags += ' --genre "%s"'

        logger.debug( '%s: %s'%( 'tag_flags', tag_flags ))

        #Rip to wav
        rip_command = shlex.split( '%s -d %s %s %s'%('cdparanoia', '/dev/sr0', track_number, wav_file) )
        logger.debug( rip_command )
        try:
            p1 = subprocess.check_call(rip_command, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            logger.critical( 'cdparadnoia failed' )
            raise Exception
    
        #Encode wav to ogg
        encode_command=shlex.split( '%s %s --output %s %s'%(encoder, wav_file, enc_file, tag_flags) )
        try:
            logger.debug( encode_command )
            p1 = subprocess.check_call( encode_command, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            logger.critical( 'encoder failed' )
            raise Exception
    
  
if __name__ == "__main__":

    #Set up logging
    funcName = __name__

    #Args
    parser = argparse.ArgumentParser(description='CLI Flags or overrides')
    parser.add_argument('-d', '--disc-id', dest='disc_id', help='Override release (cd) id from musicbrainz.', default=None, required=False, type=validate_disc_id)
    parser.add_argument('-r', '--release', dest='release_id', help='Override release (cd) id with a release from musicbrainz.', default=None, required=False, type=validate_release_id)
    parser.add_argument('-g', '--release-group-id', dest='release_group_id', help='Override release (cd) id with a release-group from musicbrainz.', default=None, required=False, type=validate_release_group_id)
    args = parser.parse_args()

    main(args=args)
