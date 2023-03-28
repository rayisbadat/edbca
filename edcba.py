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

def validate_disc_number( disc_number ):
  try:
    return int( disc_number)
  except:
    raise ValueError

def validate_release_id( release_id ):
  if release_id:
    return release_id
  raise ValueError

def validate_release_group_id( release_group_id ):
  if release_group_id:
    return release_group_id
  raise ValueError   

def get_result(release_id=None, disc_id=None):
    """
    """
    try:
        if release_id:
            result_raw = musicbrainzngs.get_release_by_id(args.release_id,includes=["artists", "recordings", "release-groups"])
        else:
            result_raw = musicbrainzngs.get_releases_by_discid(disc_id,includes=["artists", "recordings", "release-groups"])
        logger.debug( result_raw )
    except musicbrainzngs.ResponseError as e:
        logger.critical("disc not found or bad response: %s"%(e))
        raise Exception
    except Exception as e:
        logger.critical("Unknown error attempting to get disc/result id: %s"%(e))
    
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
    return result

def get_cover_art_url(release_group_id=None, release_id=None, result=None):
    """
    """

    #If we were given a release group extract album art list
    cover_art_list=None

    # Try to pull album art from release and if not try release-group
    if not cover_art_list:
        try:
            cover_art_list = musicbrainzngs.get_image_list( release_id )
        except:
            cover_art_list=None
            logger.debug("Could not pull image list from release group id: %s"%( release_group_id ) )

    if not cover_art_list:
        if release_group_id:
            try:
                cover_art_list=musicbrainzngs.get_release_group_image_list( release_group_id )
            except:
                cover_art_list=None
                logger.debug("Could not pull image list from release group id: %s"%( release_group_id ) )

    if cover_art_list:
        try:
            cover_art_url = cover_art_list['images'][0]['image']
        except KeyError as e:
            logger.warning( "Couldnt extract cover_art_list URL: %s"%(e) )
            cover_art_url = None
            #raise Exception
        except Exception as e:
            logger.warning( "Couldnt extract cover_art_list URL: %s"%(e) )
            #raise Exception
    else:
        logger.warning( "could not determine cover_art_url, there might not be any")
        cover_art_url = None

    return cover_art_url

def make_rip_dirs(wav_dir, enc_dir):
    """
    """
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

###### Main ######
def main( args=None ):
    """
    """

    if args.disc_id:
        disc_id = args.disc_id
    else:
        try: 
            disc = discid.read()  # use default device
            disc_id = disc.id
        except Exception as e:
            logger.critical( "Error trying to read disc: %s"%(e) )

    #Default args.disc_number of 0 means this will get set to -1 and tryigger the auto indexer code below
    disc_index = args.disc_number - 1

    try:
        result = get_result(release_id=args.release_id, disc_id=disc_id)
    except Exception as e:
        logger.critical( "Error trying to get disc/release info from musicbrainz: %s"%(e) )
        raise Exception

    #Get track from multi disc sets
    if disc_index < 0:
        try:
            result_disc_index = 0
            for x in result['medium-list']:
                if x['disc-list'][0]['id'] == disc_id:
                    disc_index = result_disc_index
                    break
                else:
                    result_disc_index = result_disc_index + 1
        except Exception as e:
            logger.critical( "Error trying to get multidisc results: %s"%(e) )
            sys.exit(1)

    try:
        release_id = result['id']
        release_id_short = release_id.split("-")[0]
        release_artist = result['artist-credit-phrase']
        release_track_list = result['medium-list'][disc_index]['track-list']
        release_disc_number = len(result['medium-list'])
    except KeyError as e:
        logger.critical("Could not find key in release result: %s"%(e))
        raise Exception
    except Exception as e:
        logger.critical(e)
        raise Exception

    try:
        if "title" in result['medium-list'][disc_index].keys():
            release_title_raw = result['medium-list'][disc_index]['title']
        elif "title" in result.keys():
            release_title_raw = result['title']
        else:
            raise Exception
        release_title_clean = clean_string( release_title_raw )
    except Exception:
        logger.critical("Could not title in release result")

    try:
        release_date = result['date']
        release_year = release_date.split("-")[0]
    except:
        release_date = '0000-00-00'
        release_year = release_date.split("-")[0]

    if args.release_group_id:
        release_group_id = args.release_group_id
        logger.info("release id: %s" % disc_id)
    else:
        try:
            release_group_id = result['release-group']['id']
        except:
            logger.warning("could not determine release-group id")
            release_group_id = none

    #Genre not always there
    try:
        release_genre = result['genre']
    except:
        release_genre = None

    #Get the cover art url if possible
    cover_art_url =  get_cover_art_url(release_group_id=release_group_id, release_id=release_id, result=result )
    
    #Print out harvested cd info
    logger.info( "Disc id: %s" %( disc_id ) )
    logger.info( "Release id: %s" %( release_id ) )
    logger.info( "Release id_short: %s" %( release_id_short ) )
    logger.info( "Release group_id: %s" %( release_group_id ) )
    logger.info( "Release artist: %s" %( release_artist ) )
    logger.info( "Release title: %s" %( release_title_clean ) )
    logger.info( "Release date: %s" %( release_date ) )
    logger.info( "Release year: %s" %( release_year ) )
    logger.info( "Album Art Url: %s" %( cover_art_url ) )
    logger.debug( "Release release_track_list: %s" %( release_track_list  ) )


    #Create the temp and dst directory
    wav_dir = "tmp_edcba.%s"%(release_id_short)
    enc_dir = "%s_%s"%(release_year,release_title_clean)
    if release_disc_number > 1:
        enc_dir = "%s_CD%s"%( enc_dir, disc_index+1)
    album_art_file = "%s/cover.jpg"%(enc_dir)

    #Make rip directories
    try:
        make_rip_dirs(wav_dir=wav_dir, enc_dir=enc_dir)
    except Exception as e:
        logger.critical( "Couldnt mkdirs : %s"%(e) )
        exit( 1 )

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
        logger.debug( '%s: %s'%( 'release_disc_number', release_disc_number ))

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
    parser.add_argument('-n', '--disc-number', dest='disc_number', help='Choose CD number in album, multi CD albums get one release-id and return N sets of tracks.', default=0, required=False, type=validate_disc_number)
    parser.add_argument('-r', '--release', dest='release_id', help='Override release (cd) id with a release from musicbrainz.', default=None, required=False, type=validate_release_id)
    parser.add_argument('-g', '--release-group-id', dest='release_group_id', help='Override release (cd) id with a release-group from musicbrainz.', default=None, required=False, type=validate_release_group_id)
    args = parser.parse_args()

    try: 
        main(args=args)
    except Exception as e:
        exit( 1 ) 
