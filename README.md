# edcba
-----

  Will rip and encode a cd.  Right now it can only encode to oggenc, because its hardcoded.  Album and Track info pulled from musicbrainz or cdtext


## INSTALL

    * Install python deps with `pip install -r requirements.txt`
    * Install cdparanoia with your distro's pkg manager.
    * run ./edcba.py
        * Currently you are not prompted for anything
        * Output Folder: ${DATE}_${ALBUM_NAME}
        * Files: ${TRACK_NUM}_${TRACK_NAME}
    * Does not clean up the directory were the wavs are tmp written to yet



## Tags to add
musicbrainz_artistid: the artist id in the MusicBrainz database.

musicbrainz_albumid: the album id in the MusicBrainz database.

musicbrainz_albumartistid: the album artist id in the MusicBrainz database.

musicbrainz_trackid: the track id in the MusicBrainz database.

musicbrainz_releasetrackid: the release track id in the MusicBrainz database.

musicbrainz_workid: the work id in the MusicBrainz database.

albumartist: on multi-artist albums, this is the artist name which shall be used for the whole album. The exact meaning of this tag is not well-defined.

albumartistsort: same as albumartist, but for sorting.
