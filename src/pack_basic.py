#!/usr/bin/env python3
"""
BASIC Code Packer for TRS-80 Model 100
Packs BASIC source code by removing comments, whitespace, and renumbering lines
Merges lines that aren't GOTO/GOSUB targets for maximum compression.

Similar to ROM2/Cleuseau but written in Python for modern systems.

Usage:
    python pack_basic.py input.DO output.DO
    python pack_basic.py src/TSWEEP.DO ascii_packed/TSWEEP.DO
"""

import sys
import re
from pathlib import Path


def remove_comment(line):
    """Remove comments from a BASIC line while preserving strings.

    Also removes the colon that precedes a comment, e.g.:
    DATA 1,2,3 : 'comment  ->  DATA 1,2,3
    A=1: B=2 : 'comment    ->  A=1: B=2
    """
    in_string = False
    result = []
    i = 0

    while i < len(line):
        char = line[i]

        # Track string state
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        # Remove comment if not in string
        if char == "'" and not in_string:
            # Remove the colon that precedes this comment (if any)
            # Backtrack to remove `: ` or ` :` or `:` patterns
            while result and (result[-1] == ' ' or result[-1] == ':'):
                if result[-1] == ':':
                    result.pop()
                    break
                result.pop()
            break

        result.append(char)
        i += 1

    return ''.join(result).rstrip()


def pack_spaces(line):
    """Remove unnecessary spaces while preserving strings and required keyword spacing.

    ROM2/Cleuseau rules:
    - Remove spaces except where required (before AND/OR, after DATA)
    - Keep space after DATA keyword
    """
    in_string = False
    result = []
    i = 0
    line_upper = line.upper()

    while i < len(line):
        char = line[i]

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            result.append(char)
            i += 1
            continue

        # Outside strings - handle spaces carefully
        if char == ' ':
            # Look ahead to see what follows the space
            remaining = line[i+1:].lstrip(' ')
            if not remaining:
                i += 1
                continue

            # Check if next word is AND/OR (need space before)
            if remaining.upper().startswith('AND') or remaining.upper().startswith('OR'):
                # Keep ONE space before AND/OR
                if not result or result[-1] != ' ':
                    result.append(' ')
                i += 1
                continue

            # Otherwise skip the space
            i += 1
            continue

        result.append(char)
        i += 1

    packed = ''.join(result)

    # ROM2 keeps space after DATA keyword
    # Check if line starts with DATA and fix the space
    packed_upper = packed.upper()
    if packed_upper.startswith('DATA') and len(packed) > 4 and packed[4] != ' ':
        # Insert space after DATA
        packed = 'DATA ' + packed[4:]

    return packed


def remove_trailing_quote(line):
    """Remove trailing quote from string at end of line (Model 100 BASIC optimization).

    In Model 100 BASIC, closing quotes at end of line are optional.
    ROM2 removes them to save bytes.
    """
    if not line:
        return line

    # Check if line ends with a string (closing quote)
    if not line.rstrip().endswith('"'):
        return line

    # Find the last quote and check if it's a closing quote (even position in pair)
    in_string = False
    last_open_quote = -1

    for i, char in enumerate(line):
        if char == '"':
            if not in_string:
                last_open_quote = i
            in_string = not in_string

    # If we're not in a string at the end (meaning last quote was closing), remove it
    if not in_string and line.rstrip().endswith('"'):
        # Remove the trailing quote
        line = line.rstrip()
        return line[:-1]

    return line


def remove_print_semicolons(line):
    """Remove semicolons between adjacent expressions in PRINT statements.

    ROM2 removes semicolons between expressions like:
    PRINT CHR$(235);STRING$(38,231);CHR$(236)
    becomes:
    PRINT CHR$(235)STRING$(38,231)CHR$(236)

    This is valid in Model 100 BASIC when expressions are adjacent.
    """
    # This is complex because we need to identify PRINT statements and
    # remove semicolons that are between expressions (not at end or for positioning)

    result = []
    i = 0
    in_string = False
    in_print = False
    line_upper = line.upper()

    while i < len(line):
        char = line[i]

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            result.append(char)
            i += 1
            continue

        # Check for PRINT keyword
        if line_upper[i:].startswith('PRINT'):
            in_print = True
            result.append(line[i:i+5])
            i += 5
            continue

        # Check for end of PRINT (colon or end of line)
        if in_print and char == ':':
            in_print = False
            result.append(char)
            i += 1
            continue

        # In PRINT statement, check if semicolon should be removed
        if in_print and char == ';':
            # Look at what's before and after
            # Remove semicolon if:
            # - After a closing paren (expression end) and before another expression
            # - Not at end of statement

            # Check what comes after (skip spaces)
            j = i + 1
            while j < len(line) and line[j] == ' ':
                j += 1

            # If we're at end of line or next is colon, keep the semicolon
            if j >= len(line) or line[j] == ':':
                result.append(char)
                i += 1
                continue

            # Check what's before (look at result)
            result_str = ''.join(result).rstrip()

            # If previous char is ) or " and next char starts an expression, remove semicolon
            if result_str and result_str[-1] in ')\"':
                # Next char should start an expression (letter, CHR$, STRING$, etc.)
                next_upper = line_upper[j:]
                if (next_upper.startswith('CHR$') or
                    next_upper.startswith('STRING$') or
                    next_upper.startswith('"') or
                    (next_upper[0].isalpha() and not next_upper.startswith('ELSE'))):
                    # Remove this semicolon
                    i += 1
                    continue

            result.append(char)
            i += 1
            continue

        result.append(char)
        i += 1

    return ''.join(result)


def parse_basic_file(filename):
    """Parse BASIC file and return list of (line_number, code) tuples."""
    lines = []

    with open(filename, 'r') as f:
        for line in f:
            line = line.rstrip('\n\r')

            if not line.strip():
                continue

            match = re.match(r'^(\d+)\s+(.*)', line)
            if match:
                line_num = int(match.group(1))
                code = match.group(2)

                # Skip comment-only lines
                code_stripped = code.strip()
                if code_stripped and not code_stripped.startswith("'"):
                    lines.append((line_num, code))

    return lines


def find_line_targets(lines):
    """Find all line numbers that are targets of GOTO/GOSUB/etc."""
    targets = set()

    for line_num, code in lines:
        # Remove comments and strings
        code_clean = remove_comment(code)

        # Find all line number references
        in_string = False
        i = 0

        while i < len(code_clean):
            if code_clean[i] == '"':
                in_string = not in_string
                i += 1
                continue

            if in_string:
                i += 1
                continue

            # Look for keywords
            remaining = code_clean[i:].upper()

            for keyword in ['GOTO', 'GOSUB', 'THEN', 'ELSE']:
                if remaining.startswith(keyword):
                    i += len(keyword)

                    # Extract line numbers (comma-separated for ON...GOTO)
                    while i < len(code_clean):
                        if code_clean[i].isdigit():
                            num_start = i
                            while i < len(code_clean) and code_clean[i].isdigit():
                                i += 1
                            targets.add(int(code_clean[num_start:i]))
                        elif code_clean[i] in (',', ' ', '\t'):
                            i += 1
                        else:
                            break
                    break
            else:
                i += 1

    return targets


def ends_with_control_flow(code):
    """Check if code ends with unconditional control flow (GOTO, RETURN, etc.).

    This determines if subsequent statements would be dead code OR if the
    next source line should only execute under certain conditions.

    Returns True if code ends in a way that prevents merging with next line.

    ROM2/Cleuseau rules (based on observed behavior):
    1. GOTO/GOSUB followed by line number - next line unreachable
    2. RETURN/END/STOP - next line unreachable
    3. THEN/ELSE followed by line number - next line unreachable
    4. Any line containing IF...THEN - ROM2 doesn't merge after these
       (even with complete ELSE coverage, as merging would alter the visual
       structure that ROM2 preserves)
    """
    # Remove trailing whitespace
    code = code.rstrip()
    if not code:
        return False

    code_upper = code.upper()

    # Parse to find the last statement (after last colon outside strings)
    in_string = False
    last_colon = -1
    for i, char in enumerate(code):
        if char == '"':
            in_string = not in_string
        elif char == ':' and not in_string:
            last_colon = i

    last_stmt = code[last_colon + 1:].strip() if last_colon >= 0 else code.strip()
    last_stmt_upper = last_stmt.upper()

    # Check for simple control flow keywords at start
    if last_stmt_upper in ('RETURN', 'END', 'STOP'):
        return True

    # Check if last statement is GOTO followed by a line number
    # (GOSUB returns, so it doesn't end control flow - can merge after)
    if last_stmt_upper.startswith('GOTO'):
        rest = last_stmt[4:].strip()
        # Check if it's followed by a number (simple GOTO n)
        if rest and rest[0].isdigit():
            return True

    # ROM2 rule: If the line contains IF...THEN, don't merge after it
    # This preserves the structure of conditional statements
    # Check if line contains IF (outside strings)
    in_string = False
    i = 0
    while i < len(code):
        if code[i] == '"':
            in_string = not in_string
            i += 1
            continue
        if not in_string:
            remaining = code_upper[i:]
            if remaining.startswith('IF'):
                # Found IF - check if there's also a THEN (confirms it's a conditional)
                j = i + 2
                while j < len(code):
                    if code[j] == '"':
                        in_string = not in_string
                        j += 1
                        continue
                    if not in_string and code_upper[j:].startswith('THEN'):
                        # This line has IF...THEN - don't merge after it
                        return True
                    j += 1
        i += 1

    return False


def merge_lines(lines, targets, max_line_length=255):
    """Merge consecutive lines that aren't GOTO/GOSUB targets.

    Lines are NOT merged after a line that ends with unconditional control flow,
    because any merged code would be unreachable (dead code).

    Important: The control flow check is on each SOURCE line, not the merged result.
    Each source line is evaluated independently before deciding to merge.
    """
    merged = []
    current_start_line = None
    current_code = []
    prevent_merge = False  # Set when previous SOURCE line ends with control flow

    def flush_current(start_line):
        """Flush accumulated code, respecting max line length."""
        nonlocal current_start_line

        if not current_code:
            return

        # Join segments with proper separators
        # ROM2 uses ' :' after DATA statements, ':' otherwise
        combined_parts = []
        for idx, seg in enumerate(current_code):
            if idx == 0:
                combined_parts.append(seg)
            else:
                # Check if previous segment ends with DATA values
                prev_seg = current_code[idx - 1]
                if prev_seg.upper().startswith('DATA'):
                    combined_parts.append(' :')
                    combined_parts.append(seg)
                else:
                    combined_parts.append(':')
                    combined_parts.append(seg)
        combined = ''.join(combined_parts)

        # Check if combined line exceeds max length
        # Account for line number + space (e.g., "123 ")
        max_code_length = max_line_length - len(str(start_line)) - 1

        if len(combined) <= max_code_length:
            # Fits in one line
            merged.append((start_line, combined))
        else:
            # Too long - need to split it
            # Add first segment with the target line number
            merged.append((start_line, current_code[0]))

            # Add remaining segments with None (will get renumbered)
            for seg in current_code[1:]:
                merged.append((None, seg))

    for line_num, code in lines:
        # Start new line if: it's a target, OR previous SOURCE line ended with control flow
        if line_num in targets or prevent_merge:
            # Must start a new merged line
            if current_start_line is not None:
                flush_current(current_start_line)

            current_start_line = line_num
            current_code = [code]
        else:
            # Not a target and can potentially merge
            if current_start_line is None:
                current_start_line = line_num

            # Check if adding this would exceed max length
            # Use ' :' separator after DATA statements, ':' otherwise
            if current_code and current_code[-1].upper().startswith('DATA'):
                separator = ' :'
            else:
                separator = ':'
            test_combined_len = sum(len(s) for s in current_code) + len(separator) * len(current_code) + len(code)
            max_code_length = max_line_length - len(str(current_start_line)) - 1

            if test_combined_len <= max_code_length:
                # Fits - add it
                current_code.append(code)
            else:
                # Doesn't fit - flush current and start new
                flush_current(current_start_line)
                current_start_line = line_num
                current_code = [code]

        # IMPORTANT: Check THIS source line for control flow (prevents merging NEXT line)
        # This must be checked on the original source line, NOT the merged result
        prevent_merge = ends_with_control_flow(code)

    # Flush final accumulated code
    if current_start_line is not None:
        flush_current(current_start_line)

    return merged


def update_line_references(code, line_map):
    """Update all line number references to new line numbers."""
    in_string = False
    result = []
    i = 0

    while i < len(code):
        char = code[i]

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            result.append(char)
            i += 1
            continue

        remaining = code[i:].upper()
        keyword_found = False

        for keyword in ['GOTO', 'GOSUB', 'THEN', 'ELSE']:
            if remaining.startswith(keyword):
                result.extend(code[i:i+len(keyword)])
                i += len(keyword)
                keyword_found = True

                while i < len(code):
                    if code[i].isdigit():
                        num_start = i
                        while i < len(code) and code[i].isdigit():
                            i += 1

                        old_line = int(code[num_start:i])
                        new_line = line_map.get(old_line, old_line)
                        result.append(str(new_line))
                    elif code[i] in (',', ' ', '\t'):
                        result.append(code[i])
                        i += 1
                    else:
                        break
                break

        if not keyword_found:
            result.append(char)
            i += 1

    return ''.join(result)


def pack_basic_file(input_file, output_file):
    """Pack BASIC file with full ROM2/Cleuseau-style compression."""
    # Parse input
    lines = parse_basic_file(input_file)
    print(f"Parsed {len(lines)} non-comment lines")

    # Pack each line (remove spaces/comments, remove PRINT semicolons)
    packed = []
    for num, code in lines:
        code = remove_comment(code)
        code = pack_spaces(code)
        code = remove_print_semicolons(code)
        packed.append((num, code))

    # Find GOTO/GOSUB targets
    targets = find_line_targets(packed)
    print(f"Found {len(targets)} line number targets")

    # Merge non-target lines
    merged = merge_lines(packed, targets)
    print(f"Merged into {len(merged)} lines")

    # Build line number mapping (handle None for split lines)
    line_map = {}
    new_line_num = 1

    for old_line_num, code in merged:
        if old_line_num is not None and old_line_num not in line_map:
            line_map[old_line_num] = new_line_num
        new_line_num += 1

    # Update line references and assign new numbers
    final_lines = []
    current_new_num = 1
    for old_line_num, code in merged:
        updated_code = update_line_references(code, line_map)

        if old_line_num is not None:
            new_line_num = line_map[old_line_num]
        else:
            new_line_num = current_new_num

        final_lines.append((new_line_num, updated_code))
        current_new_num = new_line_num + 1

    # Write output with ROM2-style formatting
    with open(output_file, 'w') as f:
        for line_num, code in final_lines:
            # Remove trailing quotes from strings at end of line (ROM2 optimization)
            code = remove_trailing_quote(code)
            f.write(f"{line_num} {code}\n")

    print(f"\nLine number range: {lines[0][0]}-{lines[-1][0]} -> 1-{len(final_lines)}")

    # Calculate space savings
    old_line_num_chars = sum(len(str(old)) for old, _ in lines)
    new_line_num_chars = sum(len(str(new)) for new, _ in final_lines)
    print(f"Line number bytes saved: {old_line_num_chars} -> {new_line_num_chars} ({old_line_num_chars - new_line_num_chars} bytes)")

    print(f"\nPacked: {input_file} -> {output_file}")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return 1

    try:
        pack_basic_file(input_file, output_file)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
