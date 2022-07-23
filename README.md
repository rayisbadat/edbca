edcba
-----

  Will rip and encode a cd.  Right now it can only encode to oggenc, because its hardcoded.  Album and Track info pulled from musicbrainz


INSTALL
=======

    * Install python deps with `pip install -r requirements.txt`
    * Install cdparanoia with your distro's pkg manager.
    * run ./edcba.py
        * Currently you are not prompted for anything
        * Output Folder: ${DATE}_${ALBUM_NAME}
        * Files: ${TRACK_NUM}_${TRACK_NAME}
    * Does not clean up the directory were the wavs are tmp written to yet
    * Does not download album art yet
    * If there are multiple matcehs for a CD it chooses the first track list.  Will eventually ask you to choose.
