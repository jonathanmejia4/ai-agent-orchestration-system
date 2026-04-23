#!/usr/bin/env python3
"""
Build Embeddings Generator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Search Infrastructure

Generates embeddings for codebase search and semantic analysis.
Creates vector representations of code and documentation.
"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class Document:
    """A document to be embedded."""
    id: str
    content: str
    file_path: str
    doc_type: str  # "code", "documentation", "config"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Embedding:
    """An embedding vector."""
    document_id: str
    vector: List[float]
    model: str
    created_at: str

@dataclass
class BuildResult:
    """Result of building embeddings."""
    documents_processed: int
    embeddings_generated: int
    errors: List[str] = field(default_factory=list)
    output_path: Optional[str] = None

class SimpleEmbedder:
    """Simple TF-IDF based embedder (no external dependencies)."""

    def __init__(self, dimension: int = 256):
        self.dimension = dimension
        self.vocabulary: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        import re
        # Convert to lowercase and split on non-alphanumeric
        tokens = re.findall(r'\b[a-z_][a-z0-9_]*\b', text.lower())
        return tokens

    def _hash_token(self, token: str) -> int:
        """Hash a token to a dimension index."""
        return int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dimension

    def embed(self, text: str) -> List[float]:
        """Generate a simple embedding vector."""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimension

        # Create sparse vector using hashing trick
        vector = [0.0] * self.dimension
        token_counts: Dict[str, int] = {}

        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

        for token, count in token_counts.items():
            idx = self._hash_token(token)
            # TF component
            tf = count / len(tokens)
            vector[idx] += tf

        # Normalize
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

class EmbeddingBuilder:
    """Builds embeddings for a codebase."""

    SUPPORTED_EXTENSIONS = {
        "code": [".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"],
        "documentation": [".md", ".rst", ".txt"],
        "config": [".yaml", ".yml", ".json", ".toml"],
    }

    def __init__(
        self,
        embedder: Optional[SimpleEmbedder] = None,
        chunk_size: int = 1000
    ):
        """
        Initialize builder.

        Args:
            embedder: Embedder to use (default: SimpleEmbedder)
            chunk_size: Maximum characters per chunk
        """
        self.embedder = embedder or SimpleEmbedder()
        self.chunk_size = chunk_size

    def _get_doc_type(self, file_path: str) -> Optional[str]:
        """Determine document type from file path."""
        ext = Path(file_path).suffix.lower()
        for doc_type, extensions in self.SUPPORTED_EXTENSIONS.items():
            if ext in extensions:
                return doc_type
        return None

    def _chunk_content(self, content: str) -> List[str]:
        """Split content into chunks."""
        if len(content) <= self.chunk_size:
            return [content]

        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1
            if current_size + line_size > self.chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0

            current_chunk.append(line)
            current_size += line_size

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def _create_document_id(self, file_path: str, chunk_index: int = 0) -> str:
        """Create a unique document ID."""
        path_hash = hashlib.sha256(file_path.encode()).hexdigest()[:12]
        return f"{path_hash}_{chunk_index}"

    def extract_documents(
        self,
        directory: str,
        doc_types: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None
    ) -> List[Document]:
        """
        Extract documents from a directory.

        Args:
            directory: Directory to scan
            doc_types: Document types to include
            exclude_dirs: Directories to exclude

        Returns:
            List of Documents
        """
        if doc_types is None:
            doc_types = ["code", "documentation", "config"]
        if exclude_dirs is None:
            exclude_dirs = ["node_modules", ".git", "__pycache__", "venv", ".venv"]

        documents = []
        path = Path(directory)

        for file_path in path.rglob("*"):
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            if not file_path.is_file():
                continue

            doc_type = self._get_doc_type(str(file_path))
            if doc_type is None or doc_type not in doc_types:
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue

            # Chunk large files
            chunks = self._chunk_content(content)

            for i, chunk in enumerate(chunks):
                doc_id = self._create_document_id(str(file_path), i)
                documents.append(Document(
                    id=doc_id,
                    content=chunk,
                    file_path=str(file_path),
                    doc_type=doc_type,
                    metadata={
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "file_size": len(content)
                    }
                ))

        return documents

    def build_embeddings(
        self,
        documents: List[Document]
    ) -> Tuple[List[Embedding], List[str]]:
        """
        Build embeddings for documents.

        Args:
            documents: Documents to embed

        Returns:
            Tuple of (embeddings, errors)
        """
        embeddings = []
        errors = []

        for doc in documents:
            try:
                vector = self.embedder.embed(doc.content)
                embeddings.append(Embedding(
                    document_id=doc.id,
                    vector=vector,
                    model="simple-tfidf",
                    created_at=datetime.now().isoformat()
                ))
            except Exception as e:
                errors.append(f"Failed to embed {doc.file_path}: {e}")

        return embeddings, errors

    def save_embeddings(
        self,
        documents: List[Document],
        embeddings: List[Embedding],
        output_path: str
    ):
        """Save embeddings to a file."""
        # Create document index
        doc_index = {
            doc.id: {
                "file_path": doc.file_path,
                "doc_type": doc.doc_type,
                "metadata": doc.metadata
            }
            for doc in documents
        }

        # Create embedding data
        embedding_data = {
            emb.document_id: {
                "vector": emb.vector,
                "model": emb.model,
                "created_at": emb.created_at
            }
            for emb in embeddings
        }

        output = {
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "documents": doc_index,
            "embeddings": embedding_data,
            "metadata": {
                "total_documents": len(documents),
                "total_embeddings": len(embeddings),
                "dimension": len(embeddings[0].vector) if embeddings else 0
            }
        }

        with open(output_path, 'w') as f:
            json.dump(output, f)

    def build(
        self,
        directory: str,
        output_path: str,
        doc_types: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None
    ) -> BuildResult:
        """
        Build embeddings for a directory.

        Args:
            directory: Directory to process
            output_path: Output file path
            doc_types: Document types to include
            exclude_dirs: Directories to exclude

        Returns:
            BuildResult
        """
        result = BuildResult(
            documents_processed=0,
            embeddings_generated=0,
            output_path=output_path
        )

        # Extract documents
        documents = self.extract_documents(directory, doc_types, exclude_dirs)
        result.documents_processed = len(documents)

        if not documents:
            result.errors.append("No documents found")
            return result

        # Build embeddings
        embeddings, errors = self.build_embeddings(documents)
        result.embeddings_generated = len(embeddings)
        result.errors.extend(errors)

        # Save
        if embeddings:
            self.save_embeddings(documents, embeddings, output_path)

        return result

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build embeddings for codebase search"
    )
    parser.add_argument("directory", nargs="?", default=".",
                        help="Directory to process")
    parser.add_argument("-o", "--output", default="embeddings.json",
                        help="Output file path")
    parser.add_argument("-t", "--types", nargs="+",
                        choices=["code", "documentation", "config"],
                        help="Document types to include")
    parser.add_argument("--exclude", nargs="+",
                        help="Directories to exclude")
    parser.add_argument("--chunk-size", type=int, default=1000,
                        help="Maximum chunk size in characters")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON result")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    builder = EmbeddingBuilder(chunk_size=args.chunk_size)
    result = builder.build(
        args.directory,
        args.output,
        doc_types=args.types,
        exclude_dirs=args.exclude
    )

    if args.json:
        print(json.dumps({
            "documents_processed": result.documents_processed,
            "embeddings_generated": result.embeddings_generated,
            "output_path": result.output_path,
            "errors": result.errors
        }, indent=2))
    else:
        print(f"Documents processed: {result.documents_processed}")
        print(f"Embeddings generated: {result.embeddings_generated}")
        print(f"Output: {result.output_path}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:10]:
                print(f"  - {error}")

    sys.exit(0 if result.embeddings_generated > 0 else 1)

if __name__ == "__main__":
    main()
