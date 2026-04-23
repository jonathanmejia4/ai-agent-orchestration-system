#!/usr/bin/env python3
"""
Lisp Syntax Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Syntax Validation

Validates Lisp/S-expression syntax in configuration files.
Used for the system's S-expression based DSL configurations.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

class TokenType(Enum):
    """Token types for Lisp parsing."""
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    QUOTE = "'"
    QUASIQUOTE = "`"
    UNQUOTE = ","
    STRING = "string"
    NUMBER = "number"
    SYMBOL = "symbol"
    KEYWORD = "keyword"
    BOOLEAN = "boolean"
    NIL = "nil"
    COMMENT = "comment"
    WHITESPACE = "whitespace"
    EOF = "eof"

@dataclass
class Token:
    """A lexical token."""
    type: TokenType
    value: str
    line: int
    column: int

@dataclass
class SyntaxError:
    """A syntax error in Lisp code."""
    message: str
    line: int
    column: int
    severity: str = "error"
    code: str = "SYNTAX_ERROR"

@dataclass
class CheckResult:
    """Result of syntax checking."""
    valid: bool
    files_checked: int
    errors: List[SyntaxError] = field(default_factory=list)
    warnings: List[SyntaxError] = field(default_factory=list)

class LispLexer:
    """Tokenizes Lisp/S-expression code."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def _advance(self) -> str:
        """Advance one character."""
        if self.pos >= len(self.source):
            return ''
        char = self.source[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _peek(self, offset: int = 0) -> str:
        """Peek at character without advancing."""
        pos = self.pos + offset
        if pos >= len(self.source):
            return ''
        return self.source[pos]

    def _skip_whitespace(self):
        """Skip whitespace characters."""
        while self._peek() in ' \t\n\r':
            self._advance()

    def _read_string(self) -> Token:
        """Read a string literal."""
        start_line, start_col = self.line, self.column
        self._advance()  # Skip opening quote
        value = ''

        while True:
            char = self._peek()
            if char == '':
                return Token(TokenType.STRING, value, start_line, start_col)
            if char == '"':
                self._advance()
                break
            if char == '\\':
                self._advance()
                escaped = self._advance()
                if escaped == 'n':
                    value += '\n'
                elif escaped == 't':
                    value += '\t'
                elif escaped == '"':
                    value += '"'
                elif escaped == '\\':
                    value += '\\'
                else:
                    value += escaped
            else:
                value += self._advance()

        return Token(TokenType.STRING, value, start_line, start_col)

    def _read_number(self) -> Token:
        """Read a number literal."""
        start_line, start_col = self.line, self.column
        value = ''
        has_dot = False

        if self._peek() == '-':
            value += self._advance()

        while True:
            char = self._peek()
            if char.isdigit():
                value += self._advance()
            elif char == '.' and not has_dot:
                has_dot = True
                value += self._advance()
            else:
                break

        return Token(TokenType.NUMBER, value, start_line, start_col)

    def _read_symbol(self) -> Token:
        """Read a symbol or keyword."""
        start_line, start_col = self.line, self.column
        value = ''

        # Special characters allowed in symbols
        special = set('+-*/<>=!?._')

        while True:
            char = self._peek()
            if char.isalnum() or char in special:
                value += self._advance()
            else:
                break

        # Determine token type
        if value.startswith(':'):
            return Token(TokenType.KEYWORD, value, start_line, start_col)
        elif value.lower() in ('true', '#t'):
            return Token(TokenType.BOOLEAN, 'true', start_line, start_col)
        elif value.lower() in ('false', '#f'):
            return Token(TokenType.BOOLEAN, 'false', start_line, start_col)
        elif value.lower() in ('nil', 'null', '()'):
            return Token(TokenType.NIL, 'nil', start_line, start_col)
        else:
            return Token(TokenType.SYMBOL, value, start_line, start_col)

    def _read_comment(self) -> Token:
        """Read a comment."""
        start_line, start_col = self.line, self.column
        value = ''

        while self._peek() and self._peek() != '\n':
            value += self._advance()

        return Token(TokenType.COMMENT, value, start_line, start_col)

    def tokenize(self) -> List[Token]:
        """Tokenize the source code."""
        while self.pos < len(self.source):
            self._skip_whitespace()

            if self.pos >= len(self.source):
                break

            char = self._peek()
            start_line, start_col = self.line, self.column

            if char == '(':
                self._advance()
                self.tokens.append(Token(TokenType.LPAREN, '(', start_line, start_col))
            elif char == ')':
                self._advance()
                self.tokens.append(Token(TokenType.RPAREN, ')', start_line, start_col))
            elif char == '[':
                self._advance()
                self.tokens.append(Token(TokenType.LBRACKET, '[', start_line, start_col))
            elif char == ']':
                self._advance()
                self.tokens.append(Token(TokenType.RBRACKET, ']', start_line, start_col))
            elif char == "'":
                self._advance()
                self.tokens.append(Token(TokenType.QUOTE, "'", start_line, start_col))
            elif char == '`':
                self._advance()
                self.tokens.append(Token(TokenType.QUASIQUOTE, '`', start_line, start_col))
            elif char == ',':
                self._advance()
                self.tokens.append(Token(TokenType.UNQUOTE, ',', start_line, start_col))
            elif char == '"':
                self.tokens.append(self._read_string())
            elif char == ';':
                self.tokens.append(self._read_comment())
            elif char.isdigit() or (char == '-' and self._peek(1).isdigit()):
                self.tokens.append(self._read_number())
            elif char.isalpha() or char in '+-*/<>=!?._:':
                self.tokens.append(self._read_symbol())
            else:
                self._advance()

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.column))
        return self.tokens

class LispParser:
    """Parses Lisp/S-expression tokens."""

    def __init__(self, tokens: List[Token]):
        self.tokens = [t for t in tokens if t.type != TokenType.COMMENT]
        self.pos = 0
        self.errors: List[SyntaxError] = []

    def _current(self) -> Token:
        """Get current token."""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        """Advance to next token."""
        token = self._current()
        self.pos += 1
        return token

    def _error(self, message: str, token: Optional[Token] = None):
        """Record an error."""
        t = token or self._current()
        self.errors.append(SyntaxError(
            message=message,
            line=t.line,
            column=t.column
        ))

    def parse(self) -> Tuple[Any, List[SyntaxError]]:
        """Parse all expressions."""
        expressions = []

        while self._current().type != TokenType.EOF:
            expr = self._parse_expr()
            if expr is not None:
                expressions.append(expr)

        return expressions, self.errors

    def _parse_expr(self) -> Any:
        """Parse a single expression."""
        token = self._current()

        if token.type == TokenType.LPAREN:
            return self._parse_list(')')
        elif token.type == TokenType.LBRACKET:
            return self._parse_list(']')
        elif token.type == TokenType.QUOTE:
            self._advance()
            return ['quote', self._parse_expr()]
        elif token.type == TokenType.QUASIQUOTE:
            self._advance()
            return ['quasiquote', self._parse_expr()]
        elif token.type == TokenType.UNQUOTE:
            self._advance()
            return ['unquote', self._parse_expr()]
        elif token.type in (TokenType.STRING, TokenType.NUMBER,
                           TokenType.SYMBOL, TokenType.KEYWORD,
                           TokenType.BOOLEAN, TokenType.NIL):
            self._advance()
            return token.value
        elif token.type == TokenType.RPAREN:
            self._error("Unexpected ')'")
            self._advance()
            return None
        elif token.type == TokenType.RBRACKET:
            self._error("Unexpected ']'")
            self._advance()
            return None
        else:
            self._advance()
            return None

    def _parse_list(self, end_char: str) -> List[Any]:
        """Parse a list expression."""
        self._advance()  # Skip opening paren/bracket
        elements = []
        end_type = TokenType.RPAREN if end_char == ')' else TokenType.RBRACKET

        while True:
            if self._current().type == TokenType.EOF:
                self._error(f"Unclosed list, expected '{end_char}'")
                break
            if self._current().type == end_type:
                self._advance()
                break

            elem = self._parse_expr()
            if elem is not None:
                elements.append(elem)

        return elements

class LispSyntaxChecker:
    """Checks Lisp syntax in files."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize checker.

        Args:
            config_path: Path to config YAML for custom rules
        """
        self.config: Dict[str, Any] = {}
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Load configuration."""
        try:
            import yaml
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            pass

    def check_file(self, file_path: str) -> CheckResult:
        """
        Check a file for Lisp syntax errors.

        Args:
            file_path: Path to file

        Returns:
            CheckResult
        """
        result = CheckResult(valid=True, files_checked=1)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
        except Exception as e:
            result.errors.append(SyntaxError(
                message=f"Failed to read file: {e}",
                line=0,
                column=0,
                code="READ_ERROR"
            ))
            result.valid = False
            return result

        # Tokenize
        lexer = LispLexer(source)
        try:
            tokens = lexer.tokenize()
        except Exception as e:
            result.errors.append(SyntaxError(
                message=f"Lexer error: {e}",
                line=lexer.line,
                column=lexer.column,
                code="LEXER_ERROR"
            ))
            result.valid = False
            return result

        # Parse
        parser = LispParser(tokens)
        expressions, errors = parser.parse()

        result.errors.extend(errors)
        if errors:
            result.valid = False

        # Additional validation
        self._validate_expressions(expressions, result)

        return result

    def _validate_expressions(self, expressions: List[Any], result: CheckResult):
        """Additional validation of parsed expressions."""
        # Check for common issues
        for expr in expressions:
            self._check_expression(expr, result)

    def _check_expression(self, expr: Any, result: CheckResult, depth: int = 0):
        """Recursively check an expression."""
        if depth > 100:
            result.warnings.append(SyntaxError(
                message="Very deep nesting detected",
                line=0,
                column=0,
                severity="warning",
                code="DEEP_NESTING"
            ))
            return

        if isinstance(expr, list):
            if len(expr) == 0:
                pass  # Empty list is valid
            else:
                for item in expr:
                    self._check_expression(item, result, depth + 1)

    def check_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
        recursive: bool = True
    ) -> CheckResult:
        """Check all Lisp files in a directory."""
        if extensions is None:
            extensions = ['.lisp', '.scm', '.el', '.sexp', '.clj']

        result = CheckResult(valid=True, files_checked=0)
        path = Path(directory)

        pattern = '**/*' if recursive else '*'
        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                file_result = self.check_file(str(file_path))
                result.files_checked += 1
                result.errors.extend(file_result.errors)
                result.warnings.extend(file_result.warnings)
                if not file_result.valid:
                    result.valid = False

        return result

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check Lisp/S-expression syntax"
    )
    parser.add_argument("path", help="File or directory to check")
    parser.add_argument("-c", "--config", help="Configuration file")
    parser.add_argument("-e", "--extensions", nargs="+",
                        help="File extensions to check")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Check directories recursively")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")

    args = parser.parse_args()

    checker = LispSyntaxChecker(config_path=args.config)

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
            "errors": [
                {"message": e.message, "line": e.line, "column": e.column, "code": e.code}
                for e in result.errors
            ],
            "warnings": [
                {"message": w.message, "line": w.line, "column": w.column, "code": w.code}
                for w in result.warnings
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Files checked: {result.files_checked}")
        print(f"Valid: {'Yes' if result.valid else 'No'}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for e in result.errors:
                print(f"  {e.line}:{e.column}: {e.message}")

        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"  {w.line}:{w.column}: {w.message}")

    sys.exit(0 if result.valid else 1)

if __name__ == "__main__":
    main()
