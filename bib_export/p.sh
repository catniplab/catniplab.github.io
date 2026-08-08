#!/bin/sh
# Regenerate both publications.html (CATNIP table format) and publications_apa.html (APA list).
# Custom export formats 'CATNIP' and 'CATNIP-APA' must be registered in JabRef preferences,
# pointing to tablerefs.layout and aparefs.layout respectively.
#
# IMPORTANT: JabRef's CLI export (-o) does NOT run standalone - it hands the job
# to a RUNNING JabRef desktop instance over its single-instance remote socket
# (default 127.0.0.1:6050). With no GUI instance up, the CLI call HANGS forever
# (0% CPU, blocked on the handshake). So we launch the desktop app first and
# wait for its remote port to accept connections before exporting.

JABREF=/Applications/JabRef.app/Contents/MacOS/JabRef
JABREF_PORT=6050

# A bare GUI instance has no CLI args, so its command line ends in ".../MacOS/JabRef".
# The CLI export jobs below end in "...,CATNIP" and won't match this.
if ! pgrep -f "MacOS/JabRef$" >/dev/null 2>&1; then
    echo "JabRef desktop app not running - launching it..."
    open -a JabRef
    # Wait (up to ~40s) for the single-instance remote server to come up.
    i=0
    while [ "$i" -lt 40 ]; do
        if nc -z 127.0.0.1 "$JABREF_PORT" >/dev/null 2>&1; then
            break
        fi
        i=$((i + 1))
        sleep 1
    done
    if ! nc -z 127.0.0.1 "$JABREF_PORT" >/dev/null 2>&1; then
        echo "WARNING: JabRef remote port $JABREF_PORT not responding after 40s." >&2
        echo "         Make sure JabRef is open and 'Remote operation' is enabled in preferences." >&2
    fi
fi

$JABREF -n -i catniplab.bib -o ../publications.html,CATNIP
$JABREF -n -i catniplab.bib -o ../publications_apa.html,CATNIP-APA

# Sort the APA-generated HTML by Year (reverse chronological).
# JabRef CLI forces a default sort order (usually by Author).
python3 sort_html_entries.py ../publications_apa.html
