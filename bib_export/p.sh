#!/bin/sh
# Regenerate both publications.html (CATNIP table format) and publications_apa.html (APA list).
# Custom export formats 'CATNIP' and 'CATNIP-APA' must be registered in JabRef preferences,
# pointing to tablerefs.layout and aparefs.layout respectively.

JABREF=/Applications/JabRef.app/Contents/MacOS/JabRef

$JABREF -n -i catniplab.bib -o ../publications.html,CATNIP
$JABREF -n -i catniplab.bib -o ../publications_apa.html,CATNIP-APA

# Sort the APA-generated HTML by Year (reverse chronological).
# JabRef CLI forces a default sort order (usually by Author).
python3 sort_html_entries.py ../publications_apa.html
