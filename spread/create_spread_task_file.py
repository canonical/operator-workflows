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
import argparse
import logging


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
    pattern = r'<!-- SPREAD\s*\n(.*?)-->'
    
    # First check for unclosed SPREAD blocks
    unclosed_pattern = r'<!-- SPREAD\s*(?!\n.*?-->)'
    unclosed_matches = list(re.finditer(unclosed_pattern, content, re.DOTALL))
    
    # More precise check: find all <!-- SPREAD and verify each has a closing -->
    spread_starts = [m.start() for m in re.finditer(r'<!-- SPREAD\s*', content)]
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


def extract_rst_spread_comments(content):
    """
    Extract all SPREAD comment blocks from reStructuredText content.
    
    Args:
        content: reStructuredText content as string
        
    Returns:
        List of tuples (position, command_string) for SPREAD blocks
        
    Raises:
        ValueError: If a SPREAD block is not properly closed
    """
    spread_blocks = []
    
    # Pattern to match .. SPREAD\n content \n.. SPREAD END
    pattern = r'^\.\. SPREAD\s*\n(.*?)^\.\. SPREAD END\s*$'
    
    # Find all .. SPREAD and .. SPREAD END markers for validation
    spread_starts = [m.start() for m in re.finditer(r'^\.\. SPREAD\s*$', content, re.MULTILINE)]
    spread_ends = [m.start() for m in re.finditer(r'^\.\. SPREAD END\s*$', content, re.MULTILINE)]
    
    # Validate that all SPREAD blocks are closed
    if len(spread_starts) != len(spread_ends):
        raise ValueError(f"Mismatched SPREAD markers: found {len(spread_starts)} '.. SPREAD' but {len(spread_ends)} '.. SPREAD END'")
    
    # Validate proper ordering
    for start_pos, end_pos in zip(spread_starts, spread_ends):
        if start_pos >= end_pos:
            raise ValueError(f"Invalid SPREAD block: '.. SPREAD END' appears before '.. SPREAD' at position {start_pos}")
    
    # Extract content from SPREAD blocks
    for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
        raw_content = match.group(1)
        match_start = match.start()
        
        # Split into lines and strip .. prefix from each line
        lines = raw_content.split('\n')
        stripped_lines = []
        for line in lines:
            # Strip leading .. and optional space
            if line.startswith('.. '):
                stripped_lines.append(line[3:])
            elif line.startswith('..'):
                stripped_lines.append(line[2:])
            else:
                stripped_lines.append(line)
        
        # Dedent the content (remove common leading whitespace)
        non_empty_lines = [line for line in stripped_lines if line.strip()]
        
        if not non_empty_lines:
            continue
        
        # Find minimum indentation
        min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
        
        # Remove the common indentation
        dedented_lines = []
        for line in stripped_lines:
            if line.strip():  # Non-empty line
                dedented_lines.append(line[min_indent:])
            else:  # Empty line
                dedented_lines.append('')
        
        command_content = '\n'.join(dedented_lines).strip()
        
        if command_content:
            spread_blocks.append((match_start, command_content))
    
    return spread_blocks


def parse_rst_headers(content):
    """
    Extract all headers from reStructuredText content using regex.
    
    In RST, headers are text followed by a line of special characters (=, -, ~, etc.)
    of the same length as the header text.
    
    Args:
        content: reStructuredText content as string
        
    Returns:
        List of tuples (position, level, title) for each header
    """
    headers = []
    
    # Pattern: capture title line, newline, and underline
    # The underline must be the same character repeated
    pattern = r'^(?P<title>.+)\n(?P<char>[=\-~^"\':._*+#`])(?P=char)+$'
    
    char_to_level = {}
    current_level = 0
    
    for match in re.finditer(pattern, content, re.MULTILINE):
        title = match.group('title').strip()
        char = match.group('char')
        underline = match.group(0).split('\n')[1]
        
        # Validate that underline length matches title length
        if len(title) != len(underline):
            continue
        
        # Assign level based on first appearance order
        if char not in char_to_level:
            char_to_level[char] = current_level
            current_level += 1
        
        level = char_to_level[char]
        position = match.start()
        headers.append((position, level, title))
    
    return headers


def extract_commands_from_rst(file_path):
    """
    Extract all commands from code blocks and SPREAD comments in a reStructuredText file.
    
    Args:
        file_path: Path to the reStructuredText file
        
    Returns:
        List of command strings found in code blocks and SPREAD comments, in document order
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract SPREAD comment blocks (these are included in output)
    spread_blocks = extract_rst_spread_comments(content)
    
    # Find sections to exclude: "What you'll need", "Requirements", or "Prerequisites"
    excluded_section_ranges = []
    headers = parse_rst_headers(content)
    
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
    
    # Only excluded sections (not SPREAD blocks)
    excluded_ranges = excluded_section_ranges
    
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
    
    # Combine code blocks and SPREAD blocks, then sort by position
    all_blocks = code_blocks + spread_blocks
    all_blocks.sort(key=lambda x: x[0])
    
    # Extract just the command content, maintaining order
    commands = [content for position, content in all_blocks]
    
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
    parser = argparse.ArgumentParser(
        description="Extract commands from markdown and reStructuredText files and generate task.yaml for Spread tests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s docs/tutorial.md
  %(prog)s docs/tutorial.rst
  %(prog)s docs/tutorial.md tests/spread/tutorial/task.yaml
  %(prog)s docs/tutorial.rst tests/spread/tutorial/
        """
    )
    
    parser.add_argument(
        'markdown_file',
        help='Path to the markdown or reStructuredText file to extract commands from'
    )
    
    parser.add_argument(
        'output_path',
        nargs='?',
        default='task.yaml',
        help='Path to the output YAML file or directory (default: task.yaml)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (DEBUG level)'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.WARNING if args.quiet else (logging.DEBUG if args.verbose else logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s'
    )
    
    file_path = args.markdown_file
    output_path = args.output_path
    
    # If output_path is a directory, append task.yaml
    if os.path.isdir(output_path) or output_path.endswith('/'):
        output_file = os.path.join(output_path, "task.yaml")
    else:
        output_file = output_path
    
    # Determine file type based on extension
    _, file_ext = os.path.splitext(file_path)
    file_ext = file_ext.lower()
    
    try:
        # Extract commands based on file type
        if file_ext in ['.rst', '.rest']:
            commands = extract_commands_from_rst(file_path)
        elif file_ext in ['.md', '.markdown']:
            commands = extract_commands_from_markdown(file_path)
        else:
            logging.error(f"Unsupported file type '{file_ext}'. Supported types: .md, .markdown, .rst, .rest")
            sys.exit(1)
        
        logging.info(f"Found {len(commands)} command block(s) in {file_path}")
        
        for i, command in enumerate(commands, 1):
            logging.debug(f"Command block {i}: {command}")
        
        # Write commands to task.yaml
        write_task_yaml(commands, output_file)
        logging.info(f"Commands written to {output_file}")
        
    except FileNotFoundError:
        logging.error(f"File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

