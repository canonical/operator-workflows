# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

#!/usr/bin/env python3
"""
Extract commands from markdown and reStructuredText files.

This script reads a markdown or reStructuredText file and extracts all commands from code blocks.
For Markdown: Code blocks are defined by triple backticks (```), and blocks starting with
{note} or {tip} are excluded.
For reStructuredText: Code blocks are defined by .. code-block:: directive.
"""

import sys
import re
import os


def extract_spread_comments(content):
    """
    Extract all SPREAD comment blocks from markdown content.
    
    Args:
        content: Markdown content as string
        
    Returns:
        List of tuples (position, command_string) for SPREAD blocks
        
    Raises:
        ValueError: If a SPREAD comment block is not properly closed
    """
    spread_blocks = []
    pattern = r'<!-- SPREAD\n(.*?)-->'
    
    # First check for unclosed SPREAD blocks
    unclosed_pattern = r'<!-- SPREAD(?!\n.*?-->)'
    unclosed_matches = list(re.finditer(unclosed_pattern, content, re.DOTALL))
    
    # More precise check: find all <!-- SPREAD and verify each has a closing -->
    spread_starts = [m.start() for m in re.finditer(r'<!-- SPREAD', content)]
    for start_pos in spread_starts:
        # Look for --> after this position
        remaining_content = content[start_pos:]
        if '-->' not in remaining_content:
            raise ValueError(f"Unclosed SPREAD comment block found at position {start_pos}")
        # Check if --> appears before the next <!-- SPREAD (if any)
        next_spread = remaining_content.find('<!-- SPREAD', 1)
        closing_pos = remaining_content.find('-->')
        if next_spread != -1 and closing_pos > next_spread:
            raise ValueError(f"Unclosed SPREAD comment block found at position {start_pos}")
    
    for match in re.finditer(pattern, content, re.DOTALL):
        command_content = match.group(1).strip()
        if command_content:
            spread_blocks.append((match.start(), command_content))
    
    return spread_blocks


def extract_spread_comments_rst(content):
    """
    Extract all SPREAD exclusion blocks from reStructuredText content.
    
    Args:
        content: reStructuredText content as string
        
    Returns:
        List of tuples (start_pos, end_pos) for SPREAD exclusion ranges
        
    Raises:
        ValueError: If a SPREAD block is not properly closed
    """
    exclusion_ranges = []
    
    # Find all .. SPREAD and .. SPREAD END markers
    spread_starts = []
    spread_ends = []
    
    for match in re.finditer(r'^\.\. SPREAD\s*$', content, re.MULTILINE):
        spread_starts.append(match.start())
    
    for match in re.finditer(r'^\.\. SPREAD END\s*$', content, re.MULTILINE):
        spread_ends.append(match.start())
    
    # Validate that all SPREAD blocks are closed
    if len(spread_starts) != len(spread_ends):
        raise ValueError(f"Mismatched SPREAD markers: found {len(spread_starts)} '.. SPREAD' but {len(spread_ends)} '.. SPREAD END'")
    
    # Create exclusion ranges
    for start_pos, end_pos in zip(spread_starts, spread_ends):
        if start_pos >= end_pos:
            raise ValueError(f"Invalid SPREAD block: '.. SPREAD END' appears before '.. SPREAD' at position {start_pos}")
        exclusion_ranges.append((start_pos, end_pos))
    
    return exclusion_ranges


def extract_rst_headers(content):
    """
    Extract all headers from reStructuredText content.
    
    In RST, headers are text followed by a line of special characters (=, -, ~, etc.)
    of the same length as the header text.
    
    Args:
        content: reStructuredText content as string
        
    Returns:
        List of tuples (position, level, title) for each header
    """
    headers = []
    lines = content.split('\n')
    
    # Common RST header characters in order of typical hierarchy
    header_chars = ['=', '-', '~', '^', '"', "'", '`', ':', '.', '_', '*', '+', '#']
    char_to_level = {}
    current_level = 0
    
    i = 0
    position = 0
    
    while i < len(lines):
        if i + 1 < len(lines):
            line = lines[i].rstrip()
            next_line = lines[i + 1].rstrip()
            
            # Check if next line is an underline (same length, all same special char)
            if (line and next_line and 
                len(line) == len(next_line) and 
                len(set(next_line)) == 1 and 
                next_line[0] in header_chars):
                
                char = next_line[0]
                
                # Assign level based on first appearance order
                if char not in char_to_level:
                    char_to_level[char] = current_level
                    current_level += 1
                
                level = char_to_level[char]
                title = line.strip()
                headers.append((position, level, title))
                
                i += 2  # Skip the underline
                position += len(lines[i - 2]) + len(lines[i - 1]) + 2  # +2 for newlines
                continue
        
        position += len(lines[i]) + 1  # +1 for newline
        i += 1
    
    return headers


def extract_commands_from_rst(file_path):
    """
    Extract all commands from code blocks in a reStructuredText file.
    
    Args:
        file_path: Path to the reStructuredText file
        
    Returns:
        List of command strings found in code blocks, in document order
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract SPREAD exclusion ranges
    spread_exclusion_ranges = extract_spread_comments_rst(content)
    
    # Find sections to exclude: "What you'll need", "Requirements", or "Prerequisites"
    excluded_section_ranges = []
    headers = extract_rst_headers(content)
    
    excluded_section_names = ["what you'll need", "requirements", "prerequisites"]
    for i, (pos, level, title) in enumerate(headers):
        if title.lower() in excluded_section_names:
            start_pos = pos
            # Find the next header at the same or higher level (fewer or equal number)
            end_pos = len(content)
            for j in range(i + 1, len(headers)):
                next_pos, next_level, next_title = headers[j]
                if next_level <= level:
                    end_pos = next_pos
                    break
            excluded_section_ranges.append((start_pos, end_pos))
    
    # Combine all exclusion ranges
    excluded_ranges = spread_exclusion_ranges + excluded_section_ranges
    
    # Find all code blocks: .. code-block:: followed by optional blank line and indented content
    # The pattern matches the directive and captures all consistently indented lines that follow
    pattern = r'^\.\. code-block::[^\n]*\n(?:\n)?((?:[ \t]+.+(?:\n|$))+)'  
    matches = re.finditer(pattern, content, re.MULTILINE)
    
    code_blocks = []
    for match in matches:
        indented_content = match.group(1)
        match_start = match.start()
        match_end = match.end()
        
        # Skip blocks that are within excluded ranges
        is_excluded = any(start <= match_start < end 
                         for start, end in excluded_ranges)
        if is_excluded:
            continue
        
        # Dedent the content (remove common leading whitespace)
        lines = indented_content.split('\n')
        # Filter out empty lines for indentation calculation
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            continue
        
        # Find minimum indentation
        min_indent = min(len(line) - len(line.lstrip()) 
                        for line in non_empty_lines)
        
        # Remove the common indentation
        dedented_lines = []
        for line in lines:
            if line.strip():  # Non-empty line
                dedented_lines.append(line[min_indent:])
            else:  # Empty line
                dedented_lines.append('')
        
        code_content = '\n'.join(dedented_lines).strip()
        
        if code_content:
            code_blocks.append((match_start, code_content))
    
    # Sort by position and extract content
    code_blocks.sort(key=lambda x: x[0])
    commands = [content for position, content in code_blocks]
    
    return commands


def extract_commands_from_markdown(file_path):
    """
    Extract all commands from code blocks and SPREAD comments in a markdown file.
    
    Args:
        file_path: Path to the markdown file
        
    Returns:
        List of command strings found in code blocks and SPREAD comments, in document order
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract SPREAD comment blocks first (these are never excluded)
    spread_blocks = extract_spread_comments(content)
    
    # Find sections to exclude: "What you'll need", "Requirements", or "Prerequisites"
    excluded_section_ranges = []
    header_pattern = r'^(#+)\s+(.+)$'
    
    # Find all headers in the document
    headers = []
    for match in re.finditer(header_pattern, content, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        position = match.start()
        headers.append((position, level, title))
    
    # Find all sections with names: "What you'll need", "Requirements", or "Prerequisites"
    excluded_section_names = ["what you'll need", "requirements", "prerequisites"]
    for i, (pos, level, title) in enumerate(headers):
        if title.lower() in excluded_section_names:
            start_pos = pos
            # Find the next header at the same or higher level (fewer or equal #)
            end_pos = len(content)
            for j in range(i + 1, len(headers)):
                next_pos, next_level, next_title = headers[j]
                if next_level <= level:
                    end_pos = next_pos
                    break
            excluded_section_ranges.append((start_pos, end_pos))
    
    # First, find all blocks with 4+ backticks to identify excluded regions
    excluded_ranges = []
    pattern_4plus = r'````+[^\n]*\n(.*?)````+'
    for match in re.finditer(pattern_4plus, content, re.DOTALL):
        excluded_ranges.append((match.start(), match.end()))
    
    # Add all excluded sections to excluded ranges
    excluded_ranges.extend(excluded_section_ranges)
    
    # Find all code blocks: exactly 3 backticks (not more), optional language, content, then exactly 3 backticks
    # Use negative lookbehind and lookahead to ensure exactly 3 backticks
    pattern = r'(?<!`)```(?!`)([^\n]*)\n(.*?)(?<!`)```(?!`)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    code_blocks = []
    for match in matches:
        lang_identifier = match.group(1)
        code_content = match.group(2)
        match_start = match.start()
        match_end = match.end()
        
        # Skip blocks that start with { (like {note}, {tip}, or {terminal})
        if lang_identifier.strip().startswith('{'):
            continue
        
        # Skip blocks that are nested within 4+ backtick blocks or in excluded sections
        is_nested = any(start <= match_start < match_end <= end 
                       for start, end in excluded_ranges)
        if is_nested:
            continue
        
        # Add non-empty code content with its position
        if code_content.strip():
            code_blocks.append((match_start, code_content.strip()))
    
    # Combine code blocks and SPREAD blocks, then sort by position
    all_blocks = code_blocks + spread_blocks
    all_blocks.sort(key=lambda x: x[0])
    
    # Extract just the command content, maintaining order
    commands = [content for position, content in all_blocks]
    
    return commands

def write_task_yaml(commands, output_path="task.yaml"):
    """
    Write extracted commands to a task.yaml file.
    
    Args:
        commands: List of command strings to write
        output_path: Path to the output YAML file
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Write the header
        f.write("summary: Tutorial test\n")
        f.write("\n")
        f.write("kill-timeout: 30m\n")
        f.write("\n")
        f.write("execute: |\n")
        
        # Write each command with 2-space indentation
        for command in commands:
            # Split multi-line commands and indent each line
            for line in command.split('\n'):
                f.write(f"  {line}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_commands.py <file> [output_path]")
        print("Example: python extract_commands.py docs/tutorial.md")
        print("Example: python extract_commands.py docs/tutorial.rst")
        print("Example: python extract_commands.py docs/tutorial.md tests/spread/tutorial/task.yaml")
        print("Example: python extract_commands.py docs/tutorial.md tests/spread/tutorial/")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Determine file type based on extension
    _, file_ext = os.path.splitext(file_path)
    file_ext = file_ext.lower()
    
    # Get output path from command line or use default
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
        # If output_path is a directory, append task.yaml
        if os.path.isdir(output_path) or output_path.endswith('/'):
            output_file = os.path.join(output_path, "task.yaml")
        else:
            output_file = output_path
    else:
        output_file = "task.yaml"
    
    try:
        # Extract commands based on file type
        if file_ext in ['.rst', '.rest']:
            commands = extract_commands_from_rst(file_path)
        elif file_ext in ['.md', '.markdown']:
            commands = extract_commands_from_markdown(file_path)
        else:
            print(f"Error: Unsupported file type '{file_ext}'. Supported types: .md, .markdown, .rst, .rest")
            sys.exit(1)
        
        print(f"Found {len(commands)} command block(s) in {file_path}:\n")
        
        for i, command in enumerate(commands, 1):
            print(f"Command block {i}:")
            print(command)
            print("-" * 70)
            print()
        
        # Write commands to task.yaml
        write_task_yaml(commands, output_file)
        print(f"\nCommands written to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

