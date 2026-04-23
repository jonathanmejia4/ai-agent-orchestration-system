#!/usr/bin/env python3
"""
Markdown Link Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Documentation Validation

Validates links in markdown files - both internal references and external URLs.
Ensures documentation stays consistent and links remain valid.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass
class Link:
    """A link found in markdown."""
    text: str
    url: str
    file_path: str
    line_number: int
    link_type: str  # "internal", "external", "anchor", "mailto"
    is_image: bool = False

@dataclass
class LinkIssue:
    """An issue with a link."""
    link: Link
    issue_type: str
    message: str
    severity: str = "error"

@dataclass
class CheckResult:
    """Result of link checking."""
    valid: bool
    files_checked: int
    links_found: int
    broken_links: int
    issues: List[LinkIssue] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)

class MarkdownLinkChecker:
    """Checks links in markdown files."""

    # Patterns for finding links
    LINK_PATTERN = re.compile(
        r'!?\[([^\]]*)\]\(([^)]+)\)'  # [text](url) or ![alt](url)
    )
    REF_LINK_PATTERN = re.compile(
        r'\[([^\]]+)\]:\s*(\S+)'  # [ref]: url
    )
    ANCHOR_PATTERN = re.compile(
        r'^#{1,6}\s+(.+)$', re.MULTILINE  # # Heading
    )

    def __init__(
        self,
        check_external: bool = False,
        config_path: Optional[str] = None
    ):
        """
        Initialize checker.

        Args:
            check_external: Whether to check external URLs
            config_path: Path to config file
        """
        self.check_external = check_external
        self.config: Dict[str, Any] = {
            "ignore_patterns": [],
            "timeout": 10,
            "allowed_schemes": ["http", "https", "mailto"],
        }
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Load configuration."""
        try:
            import yaml
            with open(config_path, 'r') as f:
                loaded = yaml.safe_load(f) or {}
                self.config.update(loaded)
        except Exception:
            pass

    def _slugify(self, text: str) -> str:
        """Convert heading text to anchor slug."""
        # Remove markdown formatting
        text = re.sub(r'[*_`\[\]()]', '', text)
        # Convert to lowercase
        text = text.lower()
        # Replace spaces with hyphens
        text = re.sub(r'\s+', '-', text)
        # Remove special characters
        text = re.sub(r'[^\w\-]', '', text)
        return text

    def _classify_link(self, url: str) -> str:
        """Classify the type of link."""
        if url.startswith('#'):
            return "anchor"
        if url.startswith('mailto:'):
            return "mailto"
        if url.startswith(('http://', 'https://', '//')):
            return "external"
        return "internal"

    def _should_ignore(self, url: str) -> bool:
        """Check if URL should be ignored."""
        for pattern in self.config.get("ignore_patterns", []):
            if re.search(pattern, url):
                return True
        return False

    def extract_links(self, file_path: str) -> Tuple[List[Link], Set[str]]:
        """
        Extract all links from a markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            Tuple of (links, anchors in file)
        """
        links = []
        anchors = set()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
        except Exception:
            return links, anchors

        # Extract anchors from headings
        for match in self.ANCHOR_PATTERN.finditer(content):
            anchor = self._slugify(match.group(1))
            anchors.add(anchor)

        # Extract inline links
        for line_num, line in enumerate(lines, 1):
            for match in self.LINK_PATTERN.finditer(line):
                text = match.group(1)
                url = match.group(2).strip()
                is_image = match.group(0).startswith('!')

                if self._should_ignore(url):
                    continue

                links.append(Link(
                    text=text,
                    url=url,
                    file_path=file_path,
                    line_number=line_num,
                    link_type=self._classify_link(url),
                    is_image=is_image
                ))

            # Reference-style links
            for match in self.REF_LINK_PATTERN.finditer(line):
                ref_id = match.group(1)
                url = match.group(2).strip()

                if self._should_ignore(url):
                    continue

                links.append(Link(
                    text=ref_id,
                    url=url,
                    file_path=file_path,
                    line_number=line_num,
                    link_type=self._classify_link(url)
                ))

        return links, anchors

    def check_internal_link(
        self,
        link: Link,
        base_dir: str,
        all_files: Set[str],
        file_anchors: Dict[str, Set[str]]
    ) -> Optional[LinkIssue]:
        """Check an internal link."""
        url = link.url

        # Handle anchor-only links
        if url.startswith('#'):
            anchor = url[1:]
            file_path = link.file_path
            if file_path in file_anchors:
                if anchor not in file_anchors[file_path]:
                    return LinkIssue(
                        link=link,
                        issue_type="BROKEN_ANCHOR",
                        message=f"Anchor '#{anchor}' not found in file"
                    )
            return None

        # Parse URL for path and anchor
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        anchor = parsed.fragment

        # Resolve relative path
        link_dir = os.path.dirname(link.file_path)
        resolved = os.path.normpath(os.path.join(link_dir, path))

        # Check if file exists
        if not os.path.exists(resolved):
            # Try with .md extension
            if not resolved.endswith('.md'):
                resolved_md = resolved + '.md'
                if os.path.exists(resolved_md):
                    resolved = resolved_md
                else:
                    return LinkIssue(
                        link=link,
                        issue_type="BROKEN_LINK",
                        message=f"File not found: {path}"
                    )
            else:
                return LinkIssue(
                    link=link,
                    issue_type="BROKEN_LINK",
                    message=f"File not found: {path}"
                )

        # Check anchor if present
        if anchor and resolved in file_anchors:
            if anchor not in file_anchors[resolved]:
                return LinkIssue(
                    link=link,
                    issue_type="BROKEN_ANCHOR",
                    message=f"Anchor '#{anchor}' not found in {path}",
                    severity="warning"
                )

        return None

    def check_external_link(self, link: Link) -> Optional[LinkIssue]:
        """Check an external link."""
        if not self.check_external:
            return None

        try:
            import urllib.request
            url = link.url
            if url.startswith('//'):
                url = 'https:' + url

            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 the system Link Checker'}
            )
            timeout = self.config.get("timeout", 10)

            try:
                response = urllib.request.urlopen(request, timeout=timeout)
                if response.status >= 400:
                    return LinkIssue(
                        link=link,
                        issue_type="HTTP_ERROR",
                        message=f"HTTP {response.status}"
                    )
            except urllib.error.HTTPError as e:
                return LinkIssue(
                    link=link,
                    issue_type="HTTP_ERROR",
                    message=f"HTTP {e.code}"
                )
            except urllib.error.URLError as e:
                return LinkIssue(
                    link=link,
                    issue_type="URL_ERROR",
                    message=str(e.reason)
                )
            except Exception as e:
                return LinkIssue(
                    link=link,
                    issue_type="CONNECTION_ERROR",
                    message=str(e),
                    severity="warning"
                )
        except ImportError:
            pass

        return None

    def check_file(
        self,
        file_path: str,
        all_files: Optional[Set[str]] = None,
        file_anchors: Optional[Dict[str, Set[str]]] = None
    ) -> CheckResult:
        """Check a single markdown file."""
        result = CheckResult(
            valid=True,
            files_checked=1,
            links_found=0,
            broken_links=0
        )

        links, anchors = self.extract_links(file_path)
        result.links_found = len(links)
        result.links = links

        if all_files is None:
            all_files = set()
        if file_anchors is None:
            file_anchors = {file_path: anchors}

        base_dir = os.path.dirname(file_path)

        for link in links:
            issue = None

            if link.link_type == "internal" or link.link_type == "anchor":
                issue = self.check_internal_link(
                    link, base_dir, all_files, file_anchors
                )
            elif link.link_type == "external":
                issue = self.check_external_link(link)

            if issue:
                result.issues.append(issue)
                if issue.severity == "error":
                    result.broken_links += 1
                    result.valid = False

        return result

    def check_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
        recursive: bool = True
    ) -> CheckResult:
        """Check all markdown files in a directory."""
        if extensions is None:
            extensions = ['.md', '.markdown', '.mdx']

        result = CheckResult(
            valid=True,
            files_checked=0,
            links_found=0,
            broken_links=0
        )

        path = Path(directory)
        pattern = '**/*' if recursive else '*'

        # First pass: collect all files and their anchors
        all_files: Set[str] = set()
        file_anchors: Dict[str, Set[str]] = {}

        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                str_path = str(file_path)
                all_files.add(str_path)
                _, anchors = self.extract_links(str_path)
                file_anchors[str_path] = anchors

        # Second pass: check links
        for file_path in all_files:
            file_result = self.check_file(file_path, all_files, file_anchors)
            result.files_checked += 1
            result.links_found += file_result.links_found
            result.broken_links += file_result.broken_links
            result.issues.extend(file_result.issues)
            result.links.extend(file_result.links)
            if not file_result.valid:
                result.valid = False

        return result

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check links in markdown files"
    )
    parser.add_argument("path", help="File or directory to check")
    parser.add_argument("-c", "--config", help="Configuration file")
    parser.add_argument("-e", "--extensions", nargs="+",
                        help="File extensions to check")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Check directories recursively")
    parser.add_argument("--external", action="store_true",
                        help="Also check external URLs")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    checker = MarkdownLinkChecker(
        check_external=args.external,
        config_path=args.config
    )

    if os.path.isdir(args.path):
        result = checker.check_directory(
            args.path,
            extensions=args.extensions,
            recursive=args.recursive
        )
    else:
        result = checker.check_file(args.path)

    if args.json:
        output = {
            "valid": result.valid,
            "files_checked": result.files_checked,
            "links_found": result.links_found,
            "broken_links": result.broken_links,
            "issues": [
                {
                    "file": i.link.file_path,
                    "line": i.link.line_number,
                    "url": i.link.url,
                    "type": i.issue_type,
                    "message": i.message,
                    "severity": i.severity
                }
                for i in result.issues
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Files checked: {result.files_checked}")
        print(f"Links found: {result.links_found}")
        print(f"Broken links: {result.broken_links}")
        print(f"Valid: {'Yes' if result.valid else 'No'}")

        if result.issues:
            print(f"\nIssues ({len(result.issues)}):")
            for issue in result.issues:
                symbol = "!" if issue.severity == "error" else "?"
                print(f"  [{symbol}] {issue.link.file_path}:{issue.link.line_number}")
                print(f"      {issue.link.url}")
                print(f"      {issue.message}")

    sys.exit(0 if result.valid else 1)

if __name__ == "__main__":
    main()
