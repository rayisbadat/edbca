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

#Cd text
import cdio, pycdio

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

def clean_string( string_value ):
    """
    Cleans up strings to make safe for writing to filesystem
    """
    #Inverse match, so we sub out anything not in regex
    regex="[^a-zA-z0-9()]+"
    regexed_string = re.sub(regex, "_", string_value)
    return regexed_string.rstrip("_")

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

def validate_disc_id(disc_id ):
  if disc_id:
    return disc_id
  raise ValueError

def validate_disc_number(disc_number ):
  try:
    return int( disc_number )
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

class Edcba:
    """
    """
    def __init__(self, args):
        #self.args = args
        funcName = sys._getframe(1).f_code.co_name
        pprint( funcName )

        #Set default values to None
        self.cover_art_url = None
        self.disc_index = None
        self.release_track_list = []
        self.release_title_raw = None
        self.release_title_clean = None

        #Set overrides we set via cmd line flags
        if args.disc_id:
            self.disc_id = args.disc_id
        else:
            self.disc_id = None
        if args.release_id:
            self.release_id = args.release_id
            self.release_id_short = self.release_id.split("-")[0]
        else:
            self.release_id = None
            self.release_id_short = None

        if args.release_artist:
            self.release_artist = args.release_artist
        else:
            self.release_artist = None

        if args.release_album:
            self.release_album = args.release_album
        else:
            self.release_album = None

        if args.release_group_id:
            self.release_group_id = args.release_group_id
        else:
            self.release_group_id = None

        if args.release_date:
            self.release_date = args.release_date
        else:
            self.release_date = None

        if args.release_year:
            self.release_year = args.release_year
        elif args.release_date:
            self.release_year = self.release_date.split("-")[0]
        else:
            self.release_year = None

        self.release_disc_number = args.release_disc_number
        self.release_genre = args.release_genre
        pprint( "1")


    def get_musicbrainz_results(self):
        """
        """
        funcName = sys._getframe(1).f_code.co_name
        pprint( funcName )

        try:
            if self.release_id:
                result_raw = musicbrainzngs.get_release_by_id(self.release_id,includes=["artists", "recordings", "release-groups"])
            else:
                result_raw = musicbrainzngs.get_releases_by_discid(self.disc_id,includes=["artists", "recordings", "release-groups"])
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
    
    def get_cover_art_url(self):
        """
        """
        funcName = sys._getframe(1).f_code.co_name
        pprint( funcName )

        #If we were given a release group extract album art list
        cover_art_list=None
    
        # Try to pull album art from release and if not try release-group
        if self.release_id:
            try:
                cover_art_list = musicbrainzngs.get_image_list( self.release_id )
            except:
                cover_art_list=None
                logger.debug("Could not pull image list from release group id: %s"%( release_group_id ) )
        elif self.release_group_id:
            try:
                cover_art_list=musicbrainzngs.get_release_group_image_list( release_group_id )
            except:
                cover_art_list=None
                logger.debug("Could not pull image list from release group id: %s"%( release_group_id ) )

        if cover_art_list:
            try:
                self.cover_art_url = cover_art_list['images'][0]['image']
            except KeyError as e:
                logger.warning( "Couldnt extract cover_art_list URL: %s"%(e) )
                self.cover_art_url = None
                #raise Exception
            except Exception as e:
                logger.warning( "Couldnt extract cover_art_list URL: %s"%(e) )
                #raise Exception
        else:
            logger.warning( "could not determine cover_art_url, there might not be any")
            self.cover_art_url = None
    
    def get_from_cdtext(self):
        """
        """
        funcName = sys._getframe(1).f_code.co_name
        pprint( funcName )

        try:
            d = cdio.Device(driver_id=pycdio.DRIVER_UNKNOWN)
            drive_name = d.get_device()
        except IOError:
            logger.critical("Problem finding a CD-ROM")
            raise Exception
        
        # Show CD-Text for an audio CD
        cdt = d.get_cdtext()
        i_tracks = d.get_num_tracks()
        i_first_track = pycdio.get_first_track_num(d.cd)
        for t in range(i_first_track, i_tracks + i_first_track):
            for i in range(pycdio.MIN_CDTEXT_FIELD, pycdio.MAX_CDTEXT_FIELDS):
                value = cdt.get(i, t)
                # value can be empty but exist, compared to NULL values
                if value is not None and pycdio.cdtext_field2str(i) == 'TITLE':
                    print("\t%s: %s" % (pycdio.cdtext_field2str(i), value))
                    self.release_track_list.append( {'number': str(t), 'position': str(t), 'recording': {'title': str(value) }} )
                    pass
                pass
            pass
        d.close()
        logger.debug(self.release_track_list)
        pprint( "2" )
    
        self.release_title_raw = self.release_album
        self.release_title_clean = clean_string( self.release_title_raw )
        if not self.release_id:
            self.release_id = self.release_title_clean
            self.release_id_short = self.release_title_clean
        #self.release_artist = clean_string( self.args.artist )
        #self.release_group_id = self.release_artist
        #self.release_date = clean_string( self.args.year )
        #self.release_year = self.release_date.split("-")[0]
        #self.release_disc_number = self.args.release_disc_number
        #self.release_genre = None
    

    def get_from_musicbrainz(self):
        """
        """
        funcName = sys._getframe(1).f_code.co_name
        pprint( funcName )

        #if self.args.disc_id:
        #    self.disc_id = args.disc_id
        if self.disc_id:
            pass
        else:
            try: 
                disc = discid.read()  # use default device
                self.disc_id = disc.id
            except Exception as e:
                logger.critical( "Error trying to read disc: %s"%(e) )
    
        #if self.args.release_id:
        #    self.release_id = self.args.release_id

        #if self.args.release_group_id:
        #    self.release_id = self.args.release_group_id

        try:
            result = self.get_musicbrainz_results()
        except Exception as e:
            logger.critical( "Error trying to get disc/release info from musicbrainz: %s"%(e) )
            raise Exception
    
        #Default args.disc_number of 0 means this will get set to -1 and tryigger the auto indexer code below
        self.disc_index = self.release_disc_number - 1
    
        #Get track from multi disc sets
        if self.disc_index < 0:
            try:
                result_disc_index = 0
                for x in result['medium-list']:
                    if x['disc-list'][0]['id'] == self.disc_id:
                        self.disc_index = result_disc_index
                        break
                    else:
                        result_disc_index = result_disc_index + 1
            except Exception as e:
                logger.critical( "Error trying to get multidisc results: %s"%(e) )
                sys.exit(1)
    
        try:
            self.release_id = result['id']
            self.release_id_short = self.release_id.split("-")[0]
            self.release_artist = result['artist-credit-phrase']
            self.release_track_list = result['medium-list'][self.disc_index]['track-list']
            self.release_disc_number = len(result['medium-list'])
        except KeyError as e:
            logger.critical("Could not find key in release result: %s"%(e))
            raise Exception
        except Exception as e:
            logger.critical(e)
            raise Exception

        try:
            if "title" in result['medium-list'][self.disc_index].keys():
                self.release_title_raw = result['medium-list'][self.disc_index]['title']
            elif "title" in result.keys():
                self.release_title_raw = result['title']
            else:
                raise Exception
            self.release_title_clean = clean_string( self.release_title_raw )
        except Exception:
            logger.critical("Could not title in release result")
    
        try:
            self.release_date = result['date']
            self.release_year = self.release_date.split("-")[0]
        except:
            self.release_date = '0000-00-00'
            self.release_year = self.release_date.split("-")[0]
    
        #if self.args.release_group_id:
        #   self.release_group_id = args.release_group_id
        #    logger.info("release id: %s" % (self.disc_id) )
        else:
            try:
                self.release_group_id = result['release-group']['id']
            except:
                logger.warning("could not determine release-group id")
                self.release_group_id = none
    
        #Genre not always there
        try:
            self.release_genre = result['genre']
        except:
            self.release_genre = None
    
        #Get the cover art url if possible
        self.cover_art_url =  self.get_cover_art_url()
    

###### Main ######
def main( args=None ):
    """
    """
    funcName = sys._getframe(1).f_code.co_name
    pprint( funcName )

    edcba = Edcba(args)

    if args.do_cdtext_tracks:
        result = edcba.get_from_cdtext()
    else:
        result = edcba.get_from_musicbrainz()
        
    #Print out harvested cd info
    logger.info( "Disc id: %s" %( edcba.disc_id ) )
    logger.info( "Release id: %s" %( edcba.release_id ) )
    logger.info( "Release id_short: %s" %( edcba.release_id_short ) )
    logger.info( "Release group_id: %s" %( edcba.release_group_id ) )
    logger.info( "Release artist: %s" %( edcba.release_artist ) )
    logger.info( "Release title: %s" %( edcba.release_title_clean ) )
    logger.info( "Release date: %s" %( edcba.release_date ) )
    logger.info( "Release year: %s" %( edcba.release_year ) )
    logger.info( "Album Art Url: %s" %( edcba.cover_art_url ) )
    logger.debug( "Release release_track_list: %s" %( edcba.release_track_list  ) )


    #Create the temp and dst directory
    wav_dir = "tmp_edcba.%s"%(edcba.release_id_short)
    enc_dir = "%s_%s"%(edcba.release_year,edcba.release_title_clean)
    if edcba.release_disc_number > 1:
        enc_dir = "%s_CD%s"%( enc_dir, edcba.disc_index+1)
    album_art_file = "%s/cover.jpg"%(enc_dir)

    #Make rip directories
    try:
        make_rip_dirs(wav_dir=wav_dir, enc_dir=enc_dir)
    except Exception as e:
        logger.critical( "Couldnt mkdirs : %s"%(e) )
        raise Exception

    #Try to download album art
    if edcba.cover_art_url:
      try:
          r = requests.get(edcba.cover_art_url, stream=True)
          logger.debug( "Successfully downloaded %s"%(edcba.cover_art_url))
      except requests.exceptions as e:
          logger.critical( "Failed to download album art: %s"%(e) )
          raise Exception
      try:
          with open(album_art_file, 'wb') as fd:
              for chunk in r.iter_content(chunk_size=128):
                  fd.write(chunk)
          logger.info( "Successfully wrote album art from %s to %s ."%(edcba.cover_art_url,album_art_file))
      except Exception as e:
          logger.critical( "Failed to write album art to %s: %s"%(album_art_file,e) )
          raise Exception

    # Rip and encode each track
    for release_track in edcba.release_track_list:
        # Do I need position or number
        track_number = release_track['number'].zfill(2)
        track_position = release_track['position'].zfill(2)
        track_title_raw = release_track['recording']['title']
        track_title_clean=clean_string( track_title_raw )
    
        wav_file = '%s/%s_%s.wav'%( wav_dir, track_number, track_title_clean)
        enc_file = '%s/%s_%s.%s'%( enc_dir, track_number, track_title_clean, 'ogg')

        #FIXME: Hardcoded to oggenc 
        #FIXME: change the --artist to the track artist from musicbrainz
        logger.debug( '%s: %s'%( 'release_artist', edcba.release_artist ))
        logger.debug( '%s: %s'%( 'release_title_raw', edcba.release_title_raw ))
        logger.debug( '%s: %s'%( 'release_title_clean', edcba.release_title_clean ))
        logger.debug( '%s: %s'%( 'track_title_clean', track_title_clean ))
        logger.debug( '%s: %s'%( 'track_title_raw', track_title_raw ))
        logger.debug( '%s: %s'%( 'release_date', edcba.release_date ))
        logger.debug( '%s: %s'%( 'track_number', track_number ))
        logger.debug( '%s: %s'%( 'release_artist', edcba.release_artist ))
        logger.debug( '%s: %s'%( 'release_id_short', edcba.release_id_short ))
        logger.debug( '%s: %s'%( 'release_disc_number', edcba.release_disc_number ))

        tag_flags = '--artist "%s" --album "%s" --title "%s" --date "%s" --tracknum "%s" --comment "albumartist=%s" --comment "CDDB=%s"'%(
            edcba.release_artist,
            edcba.release_title_raw,
            track_title_raw,
            edcba.release_date,
            track_number,
            edcba.release_artist,
            edcba.release_id_short,
        )
        if edcba.release_genre:
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

    funcName = __name__

    #Args
    parser = argparse.ArgumentParser(description='CLI Flags or overrides')
    parser.add_argument('-d', '--disc-id', dest='disc_id', help='Override release (cd) id from musicbrainz.', default=None, required=False, type=validate_disc_id)
    parser.add_argument('-n', '--disc-number', dest='release_disc_number', help='Choose CD number in album, multi CD albums get one release-id and return N sets of tracks.', default=1, required=False, type=validate_disc_number)
    parser.add_argument('-r', '--release', dest='release_id', help='Override release (cd) id with a release from musicbrainz.', default=None, required=False, type=validate_release_id)
    parser.add_argument('-g', '--release-group-id', dest='release_group_id', help='Override release (cd) id with a release-group from musicbrainz.', default=None, required=False, type=validate_release_group_id)
    parser.add_argument('-c', '--use-cdtext-tracks', dest='do_cdtext_tracks', help='Pull cdtext from cdtext instead of musicbrains', required=False, action='store_true')
    parser.add_argument('--album', dest='release_album', help='Override the album name.', default=None, required=False, type=str)
    parser.add_argument('--artist', dest='release_artist', help='Override the artist name.', default=None, required=False, type=str)
    parser.add_argument('--year', dest='release_year', help='Override the release year.', default=None, required=False, type=str)
    parser.add_argument('--date', dest='release_date', help='Override the release year.', default=None, required=False, type=str)
    parser.add_argument('--genre', dest='release_genre', help='Override the genre.', default=None, required=False, type=str)
    args = parser.parse_args()

    try: 
        main(args=args)
    except Exception as e:
        logger.critical( "Failed in main: %s"%(e))
        exit( 1 ) 
