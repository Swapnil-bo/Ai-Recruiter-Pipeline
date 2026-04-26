import re
import logging
import fitz                              # PyMuPDF
from pathlib import Path
from typing import Optional
from backend.core.schemas import Resume
from backend.utils.ollama_client import OllamaClient
from backend.utils.prompt_templates import (
    resume_parser_system_prompt,
    resume_parser_user_prompt,
)

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class ResumeParseError(Exception):
    """Raised when resume cannot be parsed."""

class EmptyResumeError(ResumeParseError):
    """Raised when extracted text is empty or too short."""

class UnsupportedFileTypeError(ResumeParseError):
    """Raised when file type is not supported."""


# ── Resume Parser ──────────────────────────────────────────────────────────────

class ResumeParser:
    """
    Full resume parsing pipeline:
    1. Extract raw text from PDF or plain text file
    2. Clean and normalize the text
    3. Rule-based fast extraction (skills, experience, education)
    4. LLM-based deep extraction via Ollama for enriched fields
    5. Merge both results — rules fill gaps, LLM enriches
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
    MIN_TEXT_LENGTH = 100

    # Known tech skills for rule-based extraction
    KNOWN_SKILLS = {
        # Languages
        "python", "javascript", "typescript", "java", "kotlin", "swift",
        "golang", "go", "rust", "c++", "c#", "ruby", "php", "scala",
        "r", "matlab", "bash", "shell",
        # Frameworks
        "react", "nextjs", "next.js", "vue", "angular", "svelte",
        "fastapi", "django", "flask", "express", "nestjs", "spring",
        "langchain", "langgraph", "llamaindex",
        # AI/ML
        "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn",
        "huggingface", "transformers", "ollama", "openai", "langchain",
        "rag", "llm", "fine-tuning", "qlora", "lora", "diffusion",
        "computer vision", "nlp", "machine learning", "deep learning",
        # Data
        "pandas", "numpy", "polars", "sql", "postgresql", "mysql",
        "mongodb", "redis", "elasticsearch", "chromadb", "pinecone",
        "weaviate", "sqlite",
        # Infra / DevOps
        "docker", "kubernetes", "terraform", "ansible", "jenkins",
        "github actions", "aws", "gcp", "azure", "vercel", "render",
        "linux", "nginx",
        # Tools
        "git", "graphql", "rest", "websocket", "grpc",
        "vite", "webpack", "tailwind", "figma",
    }

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self._ollama = ollama_client or OllamaClient()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def parse_file(self, file_path: str | Path) -> Resume:
        """
        Parse a resume from a file path.
        Supports: .pdf, .txt, .md
        """
        path = Path(file_path)

        if not path.exists():
            raise ResumeParseError(f"File not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file type: {suffix}. "
                f"Supported: {self.SUPPORTED_EXTENSIONS}"
            )

        logger.info(f"Parsing resume: {path.name}")

        if suffix == ".pdf":
            raw_text = self._extract_pdf(path)
        else:
            raw_text = path.read_text(encoding="utf-8")

        return await self._build_resume(raw_text)

    async def parse_text(self, raw_text: str) -> Resume:
        """Parse a resume from raw text string."""
        return await self._build_resume(raw_text)

    async def parse_bytes(self, file_bytes: bytes, filename: str) -> Resume:
        """
        Parse a resume from raw bytes (e.g. from FastAPI UploadFile).
        Detects type from filename extension.
        """
        suffix = Path(filename).suffix.lower()

        if suffix == ".pdf":
            raw_text = self._extract_pdf_bytes(file_bytes)
        elif suffix in {".txt", ".md"}:
            raw_text = file_bytes.decode("utf-8", errors="ignore")
        else:
            raise UnsupportedFileTypeError(
                f"Unsupported file type: {suffix}"
            )

        return await self._build_resume(raw_text)

    # ── Core Pipeline ──────────────────────────────────────────────────────────

    async def _build_resume(self, raw_text: str) -> Resume:
        """Full parse pipeline: clean → rule-based → LLM → merge."""
        clean_text = self._clean_text(raw_text)

        if len(clean_text) < self.MIN_TEXT_LENGTH:
            raise EmptyResumeError(
                f"Resume text too short ({len(clean_text)} chars). "
                f"Minimum: {self.MIN_TEXT_LENGTH}"
            )

        logger.info(f"Resume text extracted: {len(clean_text)} characters")

        # Step 1: Fast rule-based extraction
        rule_skills = self._extract_skills_rules(clean_text)
        rule_experience = self._extract_experience_rules(clean_text)
        rule_education = self._extract_education_rules(clean_text)
        rule_title = self._extract_title_rules(clean_text)

        logger.info(f"Rule-based: {len(rule_skills)} skills, {rule_experience}yr exp")

        # Step 2: LLM deep extraction
        llm_data = await self._extract_with_llm(clean_text)

        # Step 3: Merge — LLM wins on non-empty fields, rules fill gaps
        final_skills = self._merge_skills(rule_skills, llm_data.get("skills", []))
        final_experience = (
            llm_data.get("experience_years") or rule_experience
        )
        final_education = (
            llm_data.get("education") or rule_education
        )
        final_title = (
            llm_data.get("current_title") or rule_title
        )

        logger.info(
            f"Final parse: {len(final_skills)} skills, "
            f"{final_experience}yr exp, title='{final_title}'"
        )

        return Resume(
            raw_text=clean_text,
            skills=final_skills,
            experience_years=final_experience,
            education=final_education,
            current_title=final_title,
        )

    # ── PDF Extraction ─────────────────────────────────────────────────────────

    def _extract_pdf(self, path: Path) -> str:
        """Extract text from PDF file using PyMuPDF."""
        try:
            doc = fitz.open(str(path))
            return self._extract_fitz_doc(doc)
        except Exception as e:
            raise ResumeParseError(f"Failed to extract PDF text: {e}")

    def _extract_pdf_bytes(self, data: bytes) -> str:
        """Extract text from PDF bytes using PyMuPDF."""
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            return self._extract_fitz_doc(doc)
        except Exception as e:
            raise ResumeParseError(f"Failed to extract PDF bytes: {e}")

    def _extract_fitz_doc(self, doc: fitz.Document) -> str:
        """Extract and concatenate text from all pages."""
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                pages.append(text)
        doc.close()

        if not pages:
            raise EmptyResumeError("PDF contains no extractable text")

        return "\n".join(pages)

    # ── Text Cleaning ──────────────────────────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        """Normalize resume text for LLM consumption."""
        # Remove null bytes and control characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Normalize unicode dashes and bullets
        text = text.replace("\u2022", "-").replace("\u2013", "-").replace("\u2014", "-")
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse excessive spaces
        text = re.sub(r" {2,}", " ", text)
        # Strip lines that are just whitespace
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    # ── Rule-Based Extraction ──────────────────────────────────────────────────

    def _extract_skills_rules(self, text: str) -> list[str]:
        """Fast keyword scan for known tech skills."""
        text_lower = text.lower()
        found = []
        for skill in self.KNOWN_SKILLS:
            # Word boundary match to avoid partial matches
            pattern = rf"\b{re.escape(skill)}\b"
            if re.search(pattern, text_lower):
                found.append(skill)
        return sorted(found)

    def _extract_experience_rules(self, text: str) -> Optional[float]:
        """Extract total years of experience via regex patterns."""
        patterns = [
            r"(\d+\.?\d*)\+?\s*years?\s+of\s+experience",
            r"(\d+\.?\d*)\+?\s*years?\s+experience",
            r"experience\s+of\s+(\d+\.?\d*)\+?\s*years?",
            r"(\d+\.?\d*)\+?\s*yrs?\s+of\s+exp",
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None

    def _extract_education_rules(self, text: str) -> Optional[str]:
        """Extract highest education level via keyword matching."""
        text_lower = text.lower()
        degree_patterns = [
            (r"ph\.?d\.?\b", "PhD"),
            (r"\bm\.?tech\b|\bmaster of technology\b", "M.Tech"),
            (r"\bm\.?s\.?\b|\bmaster of science\b", "M.S."),
            (r"\bmba\b|\bmaster of business\b", "MBA"),
            (r"\bm\.?e\.?\b|\bmaster of engineering\b", "M.E."),
            (r"\bb\.?tech\b|\bbachelor of technology\b", "B.Tech"),
            (r"\bb\.?e\.?\b|\bbachelor of engineering\b", "B.E."),
            (r"\bb\.?s\.?\b|\bbachelor of science\b", "B.S."),
            (r"\bbca\b|\bbachelor of computer application\b", "BCA"),
        ]
        for pattern, label in degree_patterns:
            if re.search(pattern, text_lower):
                # Try to find institution name nearby
                match = re.search(
                    pattern + r"[^.|\n]{0,60}?(university|institute|college|iit|nit|iiit)",
                    text_lower,
                )
                if match:
                    snippet = text[match.start():match.end()].strip()
                    return snippet[:120]
                return label
        return None

    def _extract_title_rules(self, text: str) -> Optional[str]:
        """Extract current job title from common resume patterns."""
        title_patterns = [
            r"(?:current(?:ly)?|present)\s*[-:]?\s*(.{5,60}?)(?:\n|at\s)",
            r"(?:position|role|title)\s*[-:]?\s*(.{5,60}?)(?:\n|,)",
        ]
        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:80]
        return None

    # ── LLM Extraction ─────────────────────────────────────────────────────────

    async def _extract_with_llm(self, text: str) -> dict:
        """Use Ollama to deeply extract structured resume fields."""
        try:
            result = await self._ollama.chat_json(
                prompt=resume_parser_user_prompt(text),
                system=resume_parser_system_prompt(),
                temperature=0.1,         # near-deterministic for parsing
            )
            return result
        except Exception as e:
            logger.warning(f"LLM extraction failed, falling back to rules: {e}")
            return {}

    # ── Merging ────────────────────────────────────────────────────────────────

    def _merge_skills(self, rule_skills: list[str], llm_skills: list[str]) -> list[str]:
        """
        Merge rule-based and LLM-extracted skills.
        - Deduplicate case-insensitively
        - Normalize to lowercase
        - Sort alphabetically
        """
        combined = set()
        for skill in rule_skills + llm_skills:
            if skill and isinstance(skill, str):
                combined.add(skill.lower().strip())
        return sorted(combined)