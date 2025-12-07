#!/usr/bin/env python3
"""
Tokenize ASCII BASIC to Tandy 200/Model 100 binary format (.BA files).

Converts packed ASCII BASIC (.DO files) to tokenized binary format (.BA files)
compatible with TRS-80 Model 100, Tandy 102, and Tandy 200 computers.

Token table from: http://fileformats.archiveteam.org/wiki/Tandy_200_BASIC_tokenized_file
"""

import sys
import struct
from pathlib import Path

# Token table: maps BASIC keywords to token bytes (0x80-0xFF)
# Note: Token 0xFF (255) is special - represents single quote comment
TOKENS = {
    # 0x80-0x8F
    'END': 0x80,
    'FOR': 0x81,
    'NEXT': 0x82,
    'DATA': 0x83,
    'INPUT': 0x84,
    'DIM': 0x85,
    'READ': 0x86,
    'LET': 0x87,
    'GOTO': 0x88,
    'RUN': 0x89,
    'IF': 0x8A,
    'RESTORE': 0x8B,
    'GOSUB': 0x8C,
    'RETURN': 0x8D,
    'REM': 0x8E,
    'STOP': 0x8F,
    # 0x90-0x9F
    'WIDTH': 0x90,
    'ELSE': 0x91,
    'LINE': 0x92,
    'EDIT': 0x93,
    'ERROR': 0x94,
    'RESUME': 0x95,
    'OUT': 0x96,
    'ON': 0x97,
    'DSKO$': 0x98,
    'OPEN': 0x99,
    'CLOSE': 0x9A,
    'LOAD': 0x9B,
    'MERGE': 0x9C,
    'FILES': 0x9D,
    'SAVE': 0x9E,
    'LFILES': 0x9F,
    # 0xA0-0xAF
    'LPRINT': 0xA0,
    'DEF': 0xA1,
    'POKE': 0xA2,
    'PRINT': 0xA3,
    'CONT': 0xA4,
    'LIST': 0xA5,
    'LLIST': 0xA6,
    'CLEAR': 0xA7,
    'CLOAD': 0xA8,
    'CSAVE': 0xA9,
    'TIME$': 0xAA,
    'DATE$': 0xAB,
    'DAY$': 0xAC,
    'COM': 0xAD,
    'MDM': 0xAE,
    'KEY': 0xAF,
    # 0xB0-0xBF
    'CLS': 0xB0,
    'BEEP': 0xB1,
    'SOUND': 0xB2,
    'LCOPY': 0xB3,
    'PSET': 0xB4,
    'PRESET': 0xB5,
    'MOTOR': 0xB6,
    'MAX': 0xB7,
    'POWER': 0xB8,
    'CALL': 0xB9,
    'MENU': 0xBA,
    'IPL': 0xBB,
    'NAME': 0xBC,
    'KILL': 0xBD,
    'SCREEN': 0xBE,
    'NEW': 0xBF,
    # 0xC0-0xCF
    'TAB(': 0xC0,
    'TO': 0xC1,
    'USING': 0xC2,
    'VARPTR': 0xC3,
    'ERL': 0xC4,
    'ERR': 0xC5,
    'STRING$': 0xC6,
    'INSTR': 0xC7,
    'DSKI$': 0xC8,
    'INKEY$': 0xC9,
    'CSRLIN': 0xCA,
    'OFF': 0xCB,
    'HIMEM': 0xCC,
    'THEN': 0xCD,
    'NOT': 0xCE,
    'STEP': 0xCF,
    # 0xD0-0xDF (Operators)
    '+': 0xD0,
    '-': 0xD1,
    '*': 0xD2,
    '/': 0xD3,
    '^': 0xD4,
    'AND': 0xD5,
    'OR': 0xD6,
    'XOR': 0xD7,
    'EQV': 0xD8,
    'IMP': 0xD9,
    'MOD': 0xDA,
    '\\': 0xDB,
    '>': 0xDC,
    '=': 0xDD,
    '<': 0xDE,
    # 0xDF-0xEF (Functions)
    'SGN': 0xDF,
    'INT': 0xE0,
    'ABS': 0xE1,
    'FRE': 0xE2,
    'INP': 0xE3,
    'LPOS': 0xE4,
    'POS': 0xE5,
    'SQR': 0xE6,
    'RND': 0xE7,
    'LOG': 0xE8,
    'EXP': 0xE9,
    'COS': 0xEA,
    'SIN': 0xEB,
    'TAN': 0xEC,
    'ATN': 0xED,
    'PEEK': 0xEE,
    'EOF': 0xEF,
    # 0xF0-0xFF
    'LOC': 0xF0,
    'LOF': 0xF1,
    'CINT': 0xF2,
    'CSNG': 0xF3,
    'CDBL': 0xF4,
    'FIX': 0xF5,
    'LEN': 0xF6,
    'STR$': 0xF7,
    'VAL': 0xF8,
    'ASC': 0xF9,
    'CHR$': 0xFA,
    'SPACE$': 0xFB,
    'LEFT$': 0xFC,
    'RIGHT$': 0xFD,
    'MID$': 0xFE,
    "'": 0xFF,  # Single quote (special handling)
}


def tokenize_line(ascii_code: str) -> bytes:
    """
    Convert ASCII BASIC line to tokenized bytes.

    Args:
        ascii_code: ASCII BASIC code line (without line number)

    Returns:
        Tokenized bytes for the line (without line number or line terminator)
    """
    tokenized = bytearray()
    i = 0
    in_string = False

    while i < len(ascii_code):
        # Track string state
        if ascii_code[i] == '"' and (i == 0 or ascii_code[i-1] != '\\'):
            in_string = not in_string
            tokenized.append(ord('"'))
            i += 1
            continue

        # Handle single quotes (comments) - only outside strings
        if ascii_code[i] == "'" and not in_string:
            # Expand single quote to: colon (3A) + REM token (8E) + quote token (FF)
            tokenized.append(0x3A)  # Colon
            tokenized.append(0x8E)  # REM token
            tokenized.append(0xFF)  # Quote token
            # Skip rest of line (it's a comment)
            break

        # If in string, just copy characters as-is
        if in_string:
            tokenized.append(ord(ascii_code[i]))
            i += 1
            continue

        # Try to match a keyword starting at position i
        matched = False

        # Try longer keywords first (multi-character operators and keywords)
        for keyword_len in range(min(10, len(ascii_code) - i), 0, -1):
            candidate = ascii_code[i:i+keyword_len]

            # Check for token match (case-insensitive for keywords)
            upper_candidate = candidate.upper()
            if upper_candidate in TOKENS:
                token = TOKENS[upper_candidate]
                tokenized.append(token)
                i += keyword_len
                matched = True

                # Special handling: ELSE token must be preceded by colon
                if upper_candidate == 'ELSE':
                    # Ensure there's a colon before ELSE
                    if len(tokenized) > 1 and tokenized[-2] != 0x3A:
                        # Insert colon before ELSE token
                        tokenized.insert(-1, 0x3A)

                break

        if not matched:
            # Not a token, copy as ASCII
            tokenized.append(ord(ascii_code[i]))
            i += 1

    return bytes(tokenized)


def parse_line(line: str) -> tuple[int, str]:
    """
    Parse a BASIC source line into line number and code.

    Args:
        line: Full BASIC source line (e.g., "1 PRINT \"Hello\"")

    Returns:
        Tuple of (line_number, code)
    """
    parts = line.split(' ', 1)
    line_number = int(parts[0])
    code = parts[1] if len(parts) > 1 else ""
    return line_number, code


def create_tokenized_file(input_file: str, output_file: str,
                         base_address: int = 0x8001) -> None:
    """
    Convert ASCII BASIC file to tokenized binary format.

    Args:
        input_file: Path to ASCII .DO file
        output_file: Path to binary .BA file to create
        base_address: Starting address in memory (0x8001 for Model 100/102, 0xA001 for Tandy 200)
    """
    # Read ASCII file
    with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Parse and tokenize lines
    tokenized_lines = []
    for line in lines:
        line = line.rstrip('\r\n')
        if not line.strip():
            continue

        try:
            line_number, code = parse_line(line)
            tokenized_code = tokenize_line(code)
            tokenized_lines.append((line_number, tokenized_code))
        except ValueError as e:
            print(f"Warning: Skipping invalid line: {line}")
            print(f"  Error: {e}")
            continue

    # Build tokenized file
    output_data = bytearray()
    current_address = base_address

    # Calculate addresses for all lines first
    line_addresses = []
    temp_address = base_address

    for line_number, tokenized_code in tokenized_lines:
        line_addresses.append(temp_address)
        # Each line: PL+PH(2) + LL+LH(2) + code + null(1)
        line_size = 2 + 2 + len(tokenized_code) + 1
        temp_address += line_size

    # Write lines with calculated addresses
    for i, (line_number, tokenized_code) in enumerate(tokenized_lines):
        # Calculate next line address
        # For last line, point to where the end-of-program marker would be
        if i + 1 < len(tokenized_lines):
            next_address = line_addresses[i + 1]
        else:
            # Last line points to address after end of file
            next_address = temp_address

        # PL PH (next line address, little-endian)
        output_data.append(next_address & 0xFF)
        output_data.append((next_address >> 8) & 0xFF)

        # LL LH (line number, little-endian)
        output_data.append(line_number & 0xFF)
        output_data.append((line_number >> 8) & 0xFF)

        # Tokenized code
        output_data.extend(tokenized_code)

        # NULL terminator
        output_data.append(0x00)

    # Write binary file
    with open(output_file, 'wb') as f:
        f.write(output_data)

    print(f"Tokenized {len(tokenized_lines)} lines")
    print(f"Output: {len(output_data)} bytes")
    print(f"Saved to: {output_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tokenize_basic.py <input.DO> [output.BA] [base_address]")
        print()
        print("Converts ASCII BASIC (.DO) to tokenized binary (.BA) format")
        print()
        print("Arguments:")
        print("  input.DO        - ASCII BASIC source file")
        print("  output.BA       - Binary output file (default: same name with .BA extension)")
        print("  base_address    - Memory base address in hex (default: 0x8001 for Model 100/102)")
        print("                    Use 0xA001 for Tandy 200")
        sys.exit(1)

    input_file = sys.argv[1]

    # Determine output file
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = Path(input_file).with_suffix('.BA')

    # Determine base address
    base_address = 0x8001
    if len(sys.argv) > 3:
        try:
            base_address = int(sys.argv[3], 16 if sys.argv[3].startswith('0x') else 10)
        except ValueError:
            print(f"Invalid base address: {sys.argv[3]}")
            sys.exit(1)

    # Verify input file exists
    if not Path(input_file).exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    print(f"Tokenizing: {input_file}")
    print(f"Base address: 0x{base_address:04X}")

    try:
        create_tokenized_file(input_file, output_file, base_address)
        print("Success!")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
