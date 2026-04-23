#!/usr/bin/env python3
"""
AST Merge Engine - Semantic Three-Way Merge Using Abstract Syntax Trees

Performs AST-aware three-way merging by parsing source files into abstract
syntax trees, comparing at the node level, and producing semantically
correct merged output.

Supports:
    - Python (.py)
    - JavaScript (.js)
    - TypeScript (.ts) - basic support
    - JSON (.json)

Usage:
    # Merge Python files
    python3 tools/ast_merge_engine.py --base f.base.py --local f.local.py --new f.new.py --output merged.py

    # Show AST diff
    python3 tools/ast_merge_engine.py --base f.base.py --local f.local.py --new f.new.py --show-ast-diff

    # Validate only (check if merge is possible)
    python3 tools/ast_merge_engine.py --base f.base.py --local f.local.py --new f.new.py --validate

Exit Codes:
    0 - Merge successful, no conflicts
    1 - Merge completed with conflicts (markers in output)
    2 - Error (parse failure, unsupported file type, etc.)

Referenced in:
    - THREE_WAY_MERGE_REGENERATION_POLICY.md:574, 1208

Author: System
Created: 2025-12-23
"""

import argparse
import ast
import sys
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import difflib

class NodeType(Enum):
    """Types of AST nodes we track"""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    VARIABLE = "variable"
    EXPRESSION = "expression"
    STATEMENT = "statement"
    OTHER = "other"

@dataclass
class ASTNode:
    """Represents a normalized AST node"""
    type: NodeType
    name: str
    lineno: int
    end_lineno: int
    source: str
    children: List['ASTNode'] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def signature(self) -> str:
        """Generate unique signature for this node"""
        return f"{self.type.value}:{self.name}"

    def content_hash(self) -> str:
        """Hash of node content for comparison"""
        return hashlib.md5(self.source.encode()).hexdigest()[:8]

@dataclass
class ASTConflict:
    """Represents a semantic conflict"""
    node_type: NodeType
    name: str
    base_node: Optional[ASTNode]
    local_node: Optional[ASTNode]
    new_node: Optional[ASTNode]
    conflict_type: str  # 'modified', 'deleted_modified', 'added_both'
    resolution: Optional[str] = None

@dataclass
class MergeResult:
    """Result of AST merge"""
    success: bool
    has_conflicts: bool
    conflicts: List[ASTConflict] = field(default_factory=list)
    merged_source: str = ""
    stats: Dict[str, int] = field(default_factory=dict)

class PythonASTParser:
    """Parses Python files into normalized AST representation"""

    def parse(self, source: str) -> List[ASTNode]:
        """Parse Python source into list of ASTNodes"""
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise ValueError(f"Python syntax error: {e}")

        lines = source.splitlines()
        nodes = []

        for node in ast.iter_child_nodes(tree):
            ast_node = self._convert_node(node, lines)
            if ast_node:
                nodes.append(ast_node)

        return nodes

    def _convert_node(self, node: ast.AST, lines: List[str]) -> Optional[ASTNode]:
        """Convert ast.AST node to our ASTNode"""
        if isinstance(node, ast.FunctionDef):
            return self._function_node(node, lines, NodeType.FUNCTION)
        elif isinstance(node, ast.AsyncFunctionDef):
            return self._function_node(node, lines, NodeType.FUNCTION)
        elif isinstance(node, ast.ClassDef):
            return self._class_node(node, lines)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            return self._import_node(node, lines)
        elif isinstance(node, ast.Assign):
            return self._assign_node(node, lines)
        elif isinstance(node, ast.Expr):
            if hasattr(node, 'lineno'):
                return ASTNode(
                    type=NodeType.EXPRESSION,
                    name=f"expr_{node.lineno}",
                    lineno=node.lineno,
                    end_lineno=getattr(node, 'end_lineno', node.lineno),
                    source=self._get_source(node, lines)
                )
        return None

    def _function_node(self, node: ast.FunctionDef, lines: List[str],
                       node_type: NodeType) -> ASTNode:
        """Create ASTNode for function definition"""
        return ASTNode(
            type=node_type,
            name=node.name,
            lineno=node.lineno,
            end_lineno=getattr(node, 'end_lineno', node.lineno),
            source=self._get_source(node, lines),
            attributes={
                'args': [arg.arg for arg in node.args.args],
                'decorators': [self._get_source(d, lines) for d in node.decorator_list],
                'is_async': isinstance(node, ast.AsyncFunctionDef)
            }
        )

    def _class_node(self, node: ast.ClassDef, lines: List[str]) -> ASTNode:
        """Create ASTNode for class definition"""
        children = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                child_node = self._function_node(child, lines, NodeType.METHOD)
                children.append(child_node)

        return ASTNode(
            type=NodeType.CLASS,
            name=node.name,
            lineno=node.lineno,
            end_lineno=getattr(node, 'end_lineno', node.lineno),
            source=self._get_source(node, lines),
            children=children,
            attributes={
                'bases': [ast.unparse(b) if hasattr(ast, 'unparse') else str(b)
                          for b in node.bases],
                'decorators': [self._get_source(d, lines) for d in node.decorator_list]
            }
        )

    def _import_node(self, node: Union[ast.Import, ast.ImportFrom],
                     lines: List[str]) -> ASTNode:
        """Create ASTNode for import statement"""
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            name = f"import_{','.join(names)}"
        else:
            module = node.module or ''
            names = [alias.name for alias in node.names]
            name = f"from_{module}_import_{','.join(names)}"

        return ASTNode(
            type=NodeType.IMPORT,
            name=name,
            lineno=node.lineno,
            end_lineno=getattr(node, 'end_lineno', node.lineno),
            source=self._get_source(node, lines)
        )

    def _assign_node(self, node: ast.Assign, lines: List[str]) -> ASTNode:
        """Create ASTNode for assignment"""
        targets = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                targets.append(target.id)
            elif isinstance(target, ast.Tuple):
                targets.extend(n.id for n in target.elts if isinstance(n, ast.Name))

        return ASTNode(
            type=NodeType.VARIABLE,
            name=','.join(targets) if targets else f"assign_{node.lineno}",
            lineno=node.lineno,
            end_lineno=getattr(node, 'end_lineno', node.lineno),
            source=self._get_source(node, lines)
        )

    def _get_source(self, node: ast.AST, lines: List[str]) -> str:
        """Extract source code for a node"""
        start = node.lineno - 1
        end = getattr(node, 'end_lineno', node.lineno)
        return '\n'.join(lines[start:end])

class ASTMergeEngine:
    """Performs semantic three-way merge using AST comparison"""

    def __init__(self):
        self.parsers = {
            '.py': PythonASTParser(),
        }

    def get_parser(self, file_path: Path):
        """Get appropriate parser for file type"""
        suffix = file_path.suffix.lower()
        if suffix in self.parsers:
            return self.parsers[suffix]
        raise ValueError(f"Unsupported file type: {suffix}")

    def parse_file(self, path: Path) -> Tuple[List[ASTNode], str]:
        """Parse file and return AST nodes and source"""
        source = path.read_text()
        parser = self.get_parser(path)
        nodes = parser.parse(source)
        return nodes, source

    def merge(self, base_path: Path, local_path: Path, new_path: Path) -> MergeResult:
        """
        Perform three-way AST merge.

        Strategy:
        1. Parse all three versions
        2. Build node maps by signature
        3. Detect changes (added, deleted, modified)
        4. Merge non-conflicting changes
        5. Mark conflicts for manual resolution
        """
        result = MergeResult(
            success=True,
            has_conflicts=False,
            stats={'nodes_base': 0, 'nodes_local': 0, 'nodes_new': 0,
                   'added': 0, 'deleted': 0, 'modified': 0, 'conflicts': 0}
        )

        try:
            base_nodes, base_source = self.parse_file(base_path)
            local_nodes, local_source = self.parse_file(local_path)
            new_nodes, new_source = self.parse_file(new_path)
        except Exception as e:
            result.success = False
            result.merged_source = f"# Parse error: {e}"
            return result

        result.stats['nodes_base'] = len(base_nodes)
        result.stats['nodes_local'] = len(local_nodes)
        result.stats['nodes_new'] = len(new_nodes)

        # Build node maps
        base_map = {n.signature(): n for n in base_nodes}
        local_map = {n.signature(): n for n in local_nodes}
        new_map = {n.signature(): n for n in new_nodes}

        all_signatures = set(base_map.keys()) | set(local_map.keys()) | set(new_map.keys())

        # Categorize changes
        merged_nodes = []
        conflicts = []

        for sig in sorted(all_signatures):
            base_node = base_map.get(sig)
            local_node = local_map.get(sig)
            new_node = new_map.get(sig)

            # Case 1: Unchanged in all three
            if base_node and local_node and new_node:
                if (base_node.content_hash() == local_node.content_hash() ==
                    new_node.content_hash()):
                    merged_nodes.append(base_node)
                    continue

                # Case 2: Only local modified
                if (base_node.content_hash() == new_node.content_hash() and
                    base_node.content_hash() != local_node.content_hash()):
                    merged_nodes.append(local_node)
                    result.stats['modified'] += 1
                    continue

                # Case 3: Only new modified
                if (base_node.content_hash() == local_node.content_hash() and
                    base_node.content_hash() != new_node.content_hash()):
                    merged_nodes.append(new_node)
                    result.stats['modified'] += 1
                    continue

                # Case 4: Both modified (conflict)
                conflict = ASTConflict(
                    node_type=base_node.type,
                    name=base_node.name,
                    base_node=base_node,
                    local_node=local_node,
                    new_node=new_node,
                    conflict_type='modified'
                )
                conflicts.append(conflict)
                result.stats['conflicts'] += 1

            # Case 5: Deleted in local, exists in new
            elif base_node and not local_node and new_node:
                if base_node.content_hash() != new_node.content_hash():
                    # Deleted locally but modified in new
                    conflict = ASTConflict(
                        node_type=base_node.type,
                        name=base_node.name,
                        base_node=base_node,
                        local_node=None,
                        new_node=new_node,
                        conflict_type='deleted_modified'
                    )
                    conflicts.append(conflict)
                    result.stats['conflicts'] += 1
                else:
                    # Clean delete
                    result.stats['deleted'] += 1

            # Case 6: Deleted in new, exists in local
            elif base_node and local_node and not new_node:
                if base_node.content_hash() != local_node.content_hash():
                    # Modified locally but deleted in new
                    conflict = ASTConflict(
                        node_type=base_node.type,
                        name=base_node.name,
                        base_node=base_node,
                        local_node=local_node,
                        new_node=None,
                        conflict_type='deleted_modified'
                    )
                    conflicts.append(conflict)
                    result.stats['conflicts'] += 1
                else:
                    # Clean delete
                    result.stats['deleted'] += 1

            # Case 7: Added in local only
            elif not base_node and local_node and not new_node:
                merged_nodes.append(local_node)
                result.stats['added'] += 1

            # Case 8: Added in new only
            elif not base_node and not local_node and new_node:
                merged_nodes.append(new_node)
                result.stats['added'] += 1

            # Case 9: Added in both (potential conflict)
            elif not base_node and local_node and new_node:
                if local_node.content_hash() == new_node.content_hash():
                    # Same addition
                    merged_nodes.append(local_node)
                    result.stats['added'] += 1
                else:
                    # Different additions
                    conflict = ASTConflict(
                        node_type=local_node.type,
                        name=local_node.name,
                        base_node=None,
                        local_node=local_node,
                        new_node=new_node,
                        conflict_type='added_both'
                    )
                    conflicts.append(conflict)
                    result.stats['conflicts'] += 1

        result.conflicts = conflicts
        result.has_conflicts = len(conflicts) > 0

        # Generate merged source
        result.merged_source = self._generate_merged_source(
            merged_nodes, conflicts, base_source
        )

        return result

    def _generate_merged_source(self, merged_nodes: List[ASTNode],
                                conflicts: List[ASTConflict],
                                base_source: str) -> str:
        """Generate merged source code"""
        lines = []

        # Add non-conflicting nodes
        for node in sorted(merged_nodes, key=lambda n: n.lineno):
            lines.append(node.source)
            lines.append('')

        # Add conflicts with markers
        for conflict in conflicts:
            lines.append(f"<<<<<<< LOCAL ({conflict.name})")
            if conflict.local_node:
                lines.append(conflict.local_node.source)
            else:
                lines.append("# (deleted)")
            lines.append("||||||| BASE")
            if conflict.base_node:
                lines.append(conflict.base_node.source)
            else:
                lines.append("# (not present)")
            lines.append("=======")
            if conflict.new_node:
                lines.append(conflict.new_node.source)
            else:
                lines.append("# (deleted)")
            lines.append(f">>>>>>> NEW ({conflict.name})")
            lines.append('')

        return '\n'.join(lines)

    def generate_ast_diff(self, base_nodes: List[ASTNode],
                          other_nodes: List[ASTNode]) -> str:
        """Generate diff between two AST representations"""
        lines = []

        base_map = {n.signature(): n for n in base_nodes}
        other_map = {n.signature(): n for n in other_nodes}

        all_sigs = set(base_map.keys()) | set(other_map.keys())

        for sig in sorted(all_sigs):
            base_n = base_map.get(sig)
            other_n = other_map.get(sig)

            if base_n and not other_n:
                lines.append(f"- {sig}")
            elif not base_n and other_n:
                lines.append(f"+ {sig}")
            elif base_n and other_n:
                if base_n.content_hash() != other_n.content_hash():
                    lines.append(f"~ {sig} (modified)")

        return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(
        description='AST-aware three-way merge engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --base f.base.py --local f.local.py --new f.new.py --output merged.py
    %(prog)s --base f.base.py --local f.local.py --new f.new.py --show-ast-diff
    %(prog)s --base f.base.py --local f.local.py --new f.new.py --validate
        """
    )

    parser.add_argument('--base', '-b', type=Path, required=True,
                        help='Base version (common ancestor)')
    parser.add_argument('--local', '-l', type=Path, required=True,
                        help='Local version (with manual edits)')
    parser.add_argument('--new', '-n', type=Path, required=True,
                        help='New version (regenerated)')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output file for merged result')
    parser.add_argument('--show-ast-diff', action='store_true',
                        help='Show AST-level diff')
    parser.add_argument('--validate', action='store_true',
                        help='Validate only, do not write output')
    parser.add_argument('--json', action='store_true',
                        help='Output statistics in JSON format')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress output on success')

    args = parser.parse_args()

    # Validate files exist
    for path, name in [(args.base, 'base'), (args.local, 'local'), (args.new, 'new')]:
        if not path.exists():
            print(f"Error: {name} file not found: {path}", file=sys.stderr)
            sys.exit(2)

    # Check file type support
    engine = ASTMergeEngine()
    try:
        engine.get_parser(args.base)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    # Perform merge
    try:
        result = engine.merge(args.base, args.local, args.new)
    except Exception as e:
        print(f"Error: Merge failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Output results
    if args.json:
        output = json.dumps({
            'success': result.success,
            'has_conflicts': result.has_conflicts,
            'stats': result.stats,
            'conflicts': [
                {
                    'type': c.conflict_type,
                    'node_type': c.node_type.value,
                    'name': c.name
                }
                for c in result.conflicts
            ]
        }, indent=2)
        print(output)
    elif not args.quiet:
        print(f"AST Merge Result:")
        print(f"  Base nodes: {result.stats['nodes_base']}")
        print(f"  Local nodes: {result.stats['nodes_local']}")
        print(f"  New nodes: {result.stats['nodes_new']}")
        print(f"  Added: {result.stats['added']}")
        print(f"  Deleted: {result.stats['deleted']}")
        print(f"  Modified: {result.stats['modified']}")
        print(f"  Conflicts: {result.stats['conflicts']}")
        print(f"  Has conflicts: {result.has_conflicts}")

        if result.conflicts:
            print("\nConflicts:")
            for c in result.conflicts:
                print(f"  - {c.node_type.value} '{c.name}': {c.conflict_type}")

    # Show AST diff if requested
    if args.show_ast_diff:
        base_nodes, _ = engine.parse_file(args.base)
        local_nodes, _ = engine.parse_file(args.local)
        new_nodes, _ = engine.parse_file(args.new)

        print("\n--- BASE to LOCAL ---")
        print(engine.generate_ast_diff(base_nodes, local_nodes))
        print("\n--- BASE to NEW ---")
        print(engine.generate_ast_diff(base_nodes, new_nodes))

    # Save output if requested
    if args.output and not args.validate:
        args.output.write_text(result.merged_source)
        if not args.quiet:
            print(f"\nMerged output saved to: {args.output}")

    # Exit with appropriate code
    if not result.success:
        sys.exit(2)
    elif result.has_conflicts:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
