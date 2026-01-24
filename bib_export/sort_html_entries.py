import re
import sys

def sort_html(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        sys.exit(1)

    # markers
    list_start_marker = '<div id="publications-list">'
    # This must match exactly the start of the content from aparefs.end.layout
    # Note: JabRef might change newlines, but usually it concatenates.
    # The end layout starts with "    </div>\n    <footer"
    list_end_marker = '    </div>\n    <footer'

    if list_start_marker not in content:
        print("Error: Could not find start of publications list.")
        return

    # Split header
    header, rest = content.split(list_start_marker, 1)

    # Find the end of the entries block
    # We use rfind to be safe, though there should be only one matches if layout is unique
    end_idx = rest.rfind(list_end_marker)
    if end_idx == -1:
        # Fallback: maybe spacing is different? Try just the footer tag if unique enough
        list_end_marker_alt = '<footer'
        end_idx = rest.rfind(list_end_marker_alt)
        # We need to include the closing div of the list which is BEFORE the footer
        # In aparefs.end.layout, it is "    </div>\n    <footer..."
    # So if we found <footer, we likely missed the div.
    # Let's assume the splitting logic based on exact layout file content is safest.
        if end_idx == -1:
             print("Error: Could not find end of publications list.")
             return 
        
        # If we fell back to '<footer', we assume the "    </div>" is strictly before it.
        # But let's stick to the text we know is in the file.
        print("Warning: Exact end marker not found, trying fuzzy match...")
        
    entries_block = rest[:end_idx]
    footer = rest[end_idx:]

    # Now split entries
    # Each entry starts with <div class="entry">
    # Note: The split will result in an empty first element if the block starts with the delimiter
    entry_delimiter = '<div class="entry">'
    raw_entries = entries_block.split(entry_delimiter)
    
    parsed_entries = []
    
    # Skip the first chunk if it's empty (whitespace before first entry)
    for fragment in raw_entries:
        if not fragment.strip():
            continue
            
        full_entry_html = entry_delimiter + fragment
        
        # Extract Year
        # Pattern: (\year).  -> (2025). 
        # We look for the first occurrence of (dddd). inside the entry.
        # Based on layout: \author (\year).
        match = re.search(r'\(\s*(\d{4})\s*\)\.', fragment)
        year = 0
        if match:
            year = int(match.group(1))
        
        parsed_entries.append({'year': year, 'html': full_entry_html})

    # Sort: Primary key Year (Descending)
    # Secondary key: we can leave it as is (JabRef's default Author sort)
    parsed_entries.sort(key=lambda x: x['year'], reverse=True)
    
    # Reassemble
    sorted_html = "".join([e['html'] for e in parsed_entries])
    
    final_content = header + list_start_marker + "\n" + sorted_html + footer
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    print(f"Successfully sorted {len(parsed_entries)} entries in {filename}.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 sort_html_entries.py <html_file>")
        sys.exit(1)
    
    sort_html(sys.argv[1])
