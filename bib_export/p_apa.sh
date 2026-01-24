#!/bin/sh

# Generate the new APA list using JabRef
# Note: You must register the 'CATNIP-APA' custom export format in JabRef preferences
# pointing to the 'aparefs.layout' file in this directory.
/Applications/JabRef.app/Contents/MacOS/JabRef -n -i catniplab.bib -o ../publications_apa.html,CATNIP-APA

# Sort the generated HTML file by Year (Reverse Chronological)
# This is necessary because JabRef CLI forces a default sort order (usually Author).
python3 sort_html_entries.py ../publications_apa.html