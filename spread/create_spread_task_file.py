# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

#!/usr/bin/env python3
"""
Extract commands from markdown and reStructuredText files.

This script reads a markdown or reStructuredText file and extracts all commands from code blocks.

For Markdown:
- Code blocks are defined by triple backticks (```).
- Blocks starting with {note} or {tip} are excluded.
- SPREAD comment blocks (<!-- SPREAD\n...\n-->) are included.
- SPREAD SKIP markers (<!-- SPREAD SKIP --> ... <!-- SPREAD SKIP END -->) mark ranges to exclude.

For reStructuredText:
- Code blocks are defined by .. code-block:: directive.
- SPREAD comment blocks (.. SPREAD\n...\n.. SPREAD END) are included.
- SPREAD SKIP markers (.. SPREAD SKIP\n...\n.. SPREAD SKIP END) mark ranges to exclude.

All command blocks (both code blocks and SPREAD blocks) within SPREAD SKIP ranges are excluded
from the output.
"""

import sys
import re
import os
import argparse
import logging


def extract_markdown_spread_comments(content):
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
    # Pattern that matches <!-- SPREAD but not <!-- SPREAD SKIP
    pattern = r'<!-- SPREAD(?! SKIP)\s*\n(.*?)-->'
    
    # Find all <!-- SPREAD (not SPREAD SKIP) and verify each has a closing -->
    spread_starts = [m.start() for m in re.finditer(r'<!-- SPREAD(?! SKIP)\s*', content)]
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


def extract_markdown_spread_skip_comments(content):
    """
    Extract all SPREAD SKIP comment blocks from markdown content.
    
    Args:
        content: Markdown content as string
        
    Returns:
        List of tuples (start_pos, end_pos) for SPREAD SKIP exclusion ranges
        
    Raises:
        ValueError: If a SPREAD SKIP comment block is not properly closed
    """
    spread_skip_ranges = []
    
    # Find all <!-- SPREAD SKIP --> and <!-- SPREAD SKIP END --> markers for validation
    spread_skip_starts = [m.start() for m in re.finditer(r'<!-- SPREAD SKIP -->', content)]
    spread_skip_ends = [m.start() for m in re.finditer(r'<!-- SPREAD SKIP END -->', content)]
    
    # Validate that all SPREAD SKIP blocks are closed
    if len(spread_skip_starts) != len(spread_skip_ends):
        raise ValueError(f"Mismatched SPREAD SKIP markers: found {len(spread_skip_starts)} '<!-- SPREAD SKIP -->' but {len(spread_skip_ends)} '<!-- SPREAD SKIP END -->'")
    
    # Validate proper ordering and build ranges
    for start_marker_pos, end_marker_pos in zip(spread_skip_starts, spread_skip_ends):
        if start_marker_pos >= end_marker_pos:
            raise ValueError(f"Invalid SPREAD SKIP block: '<!-- SPREAD SKIP END -->' appears before '<!-- SPREAD SKIP -->' at position {start_marker_pos}")
        
        # The range extends from the start marker to the end marker (inclusive of both markers)
        spread_skip_ranges.append((start_marker_pos, end_marker_pos + len('<!-- SPREAD SKIP END -->')))
    
    return spread_skip_ranges


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


def extract_rst_spread_skip_comments(content):
    """
    Extract all SPREAD SKIP comment blocks from reStructuredText content.
    
    Args:
        content: reStructuredText content as string
        
    Returns:
        List of tuples (start_pos, end_pos) for SPREAD SKIP exclusion ranges
        
    Raises:
        ValueError: If a SPREAD SKIP block is not properly closed
    """
    spread_skip_ranges = []
    
    # Pattern to match .. SPREAD SKIP\n content \n.. SPREAD SKIP END
    pattern = r'^\.\. SPREAD SKIP\s*\n(.*?)^\.\. SPREAD SKIP END\s*$'
    
    # Find all .. SPREAD SKIP and .. SPREAD SKIP END markers for validation
    spread_skip_starts = [m.start() for m in re.finditer(r'^\.\. SPREAD SKIP\s*$', content, re.MULTILINE)]
    spread_skip_ends = [m.start() for m in re.finditer(r'^\.\. SPREAD SKIP END\s*$', content, re.MULTILINE)]
    
    # Validate that all SPREAD SKIP blocks are closed
    if len(spread_skip_starts) != len(spread_skip_ends):
        raise ValueError(f"Mismatched SPREAD SKIP markers: found {len(spread_skip_starts)} '.. SPREAD SKIP' but {len(spread_skip_ends)} '.. SPREAD SKIP END'")
    
    # Validate proper ordering
    for start_pos, end_pos in zip(spread_skip_starts, spread_skip_ends):
        if start_pos >= end_pos:
            raise ValueError(f"Invalid SPREAD SKIP block: '.. SPREAD SKIP END' appears before '.. SPREAD SKIP' at position {start_pos}")
    
    # Extract ranges from SPREAD SKIP blocks
    for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
        start_pos = match.start()
        end_pos = match.end()
        spread_skip_ranges.append((start_pos, end_pos))
    
    return spread_skip_ranges


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
    
    # Extract SPREAD comment blocks
    spread_blocks = extract_rst_spread_comments(content)
    
    # Extract SPREAD SKIP ranges
    spread_skip_ranges = extract_rst_spread_skip_comments(content)
    
    # Set excluded ranges to SPREAD SKIP ranges
    excluded_ranges = spread_skip_ranges
    
    # Find all code blocks in RST:
    # - Match a ".. code-block::" directive line (with any trailing options),
    # - Allow a single optional blank line immediately after the directive,
    # - Then capture (in group 1) all subsequent indented content lines as the code block body.
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
    
    # Filter SPREAD blocks to exclude those within SPREAD SKIP ranges
    filtered_spread_blocks = []
    for pos, content in spread_blocks:
        is_excluded = any(start <= pos < end for start, end in spread_skip_ranges)
        if not is_excluded:
            filtered_spread_blocks.append((pos, content))
    
    # Combine code blocks and filtered SPREAD blocks, then sort by position
    all_blocks = code_blocks + filtered_spread_blocks
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
    
    # Extract SPREAD comment blocks
    spread_blocks = extract_markdown_spread_comments(content)
    
    # Extract SPREAD SKIP ranges
    spread_skip_ranges = extract_markdown_spread_skip_comments(content)
    
    # First, find all blocks with 4+ backticks to identify excluded regions
    excluded_ranges = []
    pattern_4plus = r'````+[^\n]*\n(.*?)````+'
    for match in re.finditer(pattern_4plus, content, re.DOTALL):
        excluded_ranges.append((match.start(), match.end()))
    
    # Add SPREAD SKIP ranges to excluded ranges
    excluded_ranges.extend(spread_skip_ranges)
    
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
    
    # Filter SPREAD blocks to exclude those within SPREAD SKIP ranges
    filtered_spread_blocks = []
    for pos, content in spread_blocks:
        is_excluded = any(start <= pos < end for start, end in spread_skip_ranges)
        if not is_excluded:
            filtered_spread_blocks.append((pos, content))
    
    # Combine code blocks and filtered SPREAD blocks, then sort by position
    all_blocks = code_blocks + filtered_spread_blocks
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

Special Markers:
  SPREAD blocks (always included):
    Markdown: <!-- SPREAD
              command content
              -->
    RST:      .. SPREAD
              .. command content
              .. SPREAD END
  
  SPREAD SKIP markers (exclude all commands in range):
    Markdown: <!-- SPREAD SKIP -->
              Content to skip (code blocks and SPREAD blocks)
              <!-- SPREAD SKIP END -->
    RST:      .. SPREAD SKIP
              .. Content to skip
              .. SPREAD SKIP END
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

