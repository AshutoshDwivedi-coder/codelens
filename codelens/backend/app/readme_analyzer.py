"""
readme_analyzer.py – Service to read and analyze repository README files,
extracting project insights, features, architecture components, and
generating actionable suggested questions personalized to the chosen repository.

Supports:
- Local folders and custom workspace paths
- Remote Git / GitHub URLs (e.g. https://github.com/owner/repo)
- Built-in demo repositories
- Automatic shallow cloning for search indexing
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import shutil
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger("codelens.readme_analyzer")


def is_remote_git_url(repo_path: str) -> bool:
    """Check if the string is a GitHub URL or Git remote identifier."""
    if not repo_path:
        return False
    path_str = repo_path.strip()
    if path_str.startswith(("http://", "https://", "git@", "ssh://")):
        return True
    # Check owner/repo pattern (e.g. bubksrit/CAPE or facebook/react)
    if re.match(r"^[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+$", path_str):
        # Ignore if it happens to be an existing local relative path
        if not Path(path_str).is_dir():
            return True
    return False


def parse_github_owner_repo(repo_url: str) -> Optional[Tuple[str, str]]:
    """Extract owner and repo name from GitHub URL or owner/repo string."""
    cleaned = repo_url.strip()
    # Match https://github.com/owner/repo or git@github.com:owner/repo
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?/?$", cleaned)
    if m:
        return m.group(1), m.group(2)
    # Match short format: owner/repo
    m_short = re.match(r"^([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)$", cleaned)
    if m_short:
        return m_short.group(1), m_short.group(2)
    return None


def fetch_remote_readme(repo_url: str) -> Optional[Tuple[str, str, Path]]:
    """
    Fetches the README from a remote GitHub repository without requiring full git clone.
    Caches the README locally in cloned_repos/{owner}_{repo}/README.md.
    Returns (readme_content, repo_name, local_cache_dir) or None.
    """
    parsed = parse_github_owner_repo(repo_url)
    if not parsed:
        return None
    owner, repo = parsed
    repo_name = f"{owner}/{repo}"

    try:
        from app.config import settings
        base_dir = settings.base_dir
    except Exception:
        base_dir = Path(__file__).resolve().parent.parent.parent

    cache_dir = base_dir / "cloned_repos" / f"{owner}_{repo}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_readme = cache_dir / "README.md"

    # If already cached and fresh, read it
    if local_readme.exists() and local_readme.stat().st_size > 0:
        try:
            return local_readme.read_text(encoding="utf-8", errors="ignore"), repo_name, cache_dir
        except Exception:
            pass

    # Try fetching raw content across common branch and file names
    branches = ["main", "master", "HEAD", "develop"]
    file_names = ["README.md", "readme.md", "README.rst", "README.txt", "README"]

    for branch in branches:
        for fname in file_names:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{fname}"
            try:
                req = urllib.request.Request(raw_url, headers={"User-Agent": "CodeLens/1.0"})
                with urllib.request.urlopen(req, timeout=6) as response:
                    content = response.read().decode("utf-8", errors="ignore")
                    if content and len(content.strip()) > 10:
                        try:
                            local_readme.write_text(content, encoding="utf-8")
                        except Exception:
                            pass
                        return content, repo_name, cache_dir
            except Exception:
                continue

    return None


def clone_git_repo(repo_url: str) -> Tuple[bool, str, Path]:
    """
    Shallow clones a remote Git repository into cloned_repos/<owner>_<repo>.
    Returns (success, message, local_dir).
    """
    parsed = parse_github_owner_repo(repo_url)
    owner, repo = parsed if parsed else ("repo", "code")

    try:
        from app.config import settings
        base_dir = settings.base_dir
    except Exception:
        base_dir = Path(__file__).resolve().parent.parent.parent

    target_dir = base_dir / "cloned_repos" / f"{owner}_{repo}"
    if (target_dir / ".git").exists():
        return True, f"Repository already cloned at {target_dir}", target_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    clone_url = repo_url
    if not clone_url.startswith(("http://", "https://", "git@")):
        clone_url = f"https://github.com/{owner}/{repo}.git"

    try:
        # README analysis may have already cached a README in target_dir.
        # Clone to a fresh sibling and merge it in so that this cache does not
        # make `git clone` fail with a non-empty destination.
        clone_dir = target_dir.with_name(f".{target_dir.name}-{uuid.uuid4().hex[:8]}")
        cmd = ["git", "clone", "--depth", "1", clone_url, str(clone_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            shutil.copytree(clone_dir, target_dir, dirs_exist_ok=True)
            shutil.rmtree(clone_dir, ignore_errors=True)
            return True, "Repository cloned successfully", target_dir
        else:
            shutil.rmtree(clone_dir, ignore_errors=True)
            return False, f"Git clone failed: {proc.stderr}", target_dir
    except Exception as exc:
        if 'clone_dir' in locals():
            shutil.rmtree(clone_dir, ignore_errors=True)
        return False, f"Error cloning repository: {exc}", target_dir


def resolve_repo_dir(repo_path: Optional[str] = None) -> Tuple[Path, Optional[str], Optional[str]]:
    """
    Resolves repository path to a directory, checking:
    1. Remote Git/GitHub URLs
    2. Local paths (absolute, relative, Windows normalized)
    3. Demo repositories
    4. Codebase root
    Returns (resolved_dir, remote_content_if_any, resolved_repo_name).
    """
    try:
        from app.config import settings
        base_dir = settings.base_dir
    except Exception:
        base_dir = Path(__file__).resolve().parent.parent.parent

    if not repo_path or repo_path.strip() in ("", ".", "all", "all repositories", "default", "codelens"):
        return base_dir, None, "CodeLens"

    clean_path = repo_path.strip().strip("'\"")

    # 1. Check if remote Git/GitHub URL
    if is_remote_git_url(clean_path):
        remote_data = fetch_remote_readme(clean_path)
        if remote_data:
            content, repo_name, local_dir = remote_data
            return local_dir, content, repo_name
        # Fallback if fetch failed: try creating a directory
        parsed = parse_github_owner_repo(clean_path)
        owner, repo = parsed if parsed else ("github", "repo")
        fallback_dir = base_dir / "cloned_repos" / f"{owner}_{repo}"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir, None, f"{owner}/{repo}"

    alias_lower = clean_path.lower()

    # 2. Match demo_repos
    demo_candidate = base_dir / "demo_repos" / clean_path
    if demo_candidate.exists() and demo_candidate.is_dir():
        return demo_candidate.resolve(), None, demo_candidate.name
    demo_candidate_alias = base_dir / "demo_repos" / alias_lower
    if demo_candidate_alias.exists() and demo_candidate_alias.is_dir():
        return demo_candidate_alias.resolve(), None, demo_candidate_alias.name

    # 3. Match known aliases
    if alias_lower in ("codelens-engine", "codelens", "codebase", "default"):
        return base_dir, None, "CodeLens"
    elif alias_lower in ("codelens-backend", "backend"):
        backend_dir = base_dir / "backend"
        if backend_dir.exists() and backend_dir.is_dir():
            return backend_dir, None, "codelens-backend"
    elif alias_lower in ("codelens-frontend", "frontend"):
        frontend_dir = base_dir / "frontend"
        if frontend_dir.exists() and frontend_dir.is_dir():
            return frontend_dir, None, "codelens-frontend"

    # 4. Check direct local path (supports C:\..., relative paths, forward/back slashes)
    try:
        norm_path = os.path.normpath(clean_path)
        candidate = Path(norm_path).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve(), None, candidate.name
        # If path points directly to a README file
        if candidate.exists() and candidate.is_file():
            return candidate.parent.resolve(), None, candidate.parent.name
    except Exception:
        pass

    # 5. Check relative to base_dir
    rel_candidate = base_dir / clean_path
    if rel_candidate.exists() and rel_candidate.is_dir():
        return rel_candidate.resolve(), None, rel_candidate.name

    # 6. Check relative to current working directory
    cwd_candidate = Path.cwd() / clean_path
    if cwd_candidate.exists() and cwd_candidate.is_dir():
        return cwd_candidate.resolve(), None, cwd_candidate.name

    # 7. Check cloned_repos folder
    cloned_candidate = base_dir / "cloned_repos" / clean_path
    if cloned_candidate.exists() and cloned_candidate.is_dir():
        return cloned_candidate.resolve(), None, clean_path

    return base_dir, None, clean_path


def find_readme_file(target_dir: Path) -> Optional[Path]:
    """Find a README in this repository without borrowing one from a parent repo."""
    readme_names = [
        "README.md", "readme.md", "README.markdown", "readme.markdown",
        "README.rst", "readme.rst", "README.txt", "readme.txt",
        "README", "readme"
    ]

    # 1. Check target_dir first
    for name in readme_names:
        candidate = target_dir / name
        if candidate.exists() and candidate.is_file():
            return candidate

    # Some repositories use a descriptive filename such as README_BLOCKING.md.
    # Accept these only after the standard README names have been checked.
    try:
        named_readmes = [
            candidate for candidate in target_dir.iterdir()
            if candidate.is_file() and candidate.name.lower().startswith("readme")
        ]
        if named_readmes:
            extension_priority = {".md": 0, ".markdown": 1, ".rst": 2, ".txt": 3}
            return min(
                named_readmes,
                key=lambda candidate: (
                    extension_priority.get(candidate.suffix.lower(), 4),
                    candidate.name.lower(),
                ),
            )
    except OSError:
        pass

    # 2. Check immediate docs/ or documentation/ subdirectories
    for sub in ["docs", "documentation"]:
        sub_dir = target_dir / sub
        if sub_dir.exists() and sub_dir.is_dir():
            for name in readme_names:
                candidate = sub_dir / name
                if candidate.exists() and candidate.is_file():
                    return candidate

    return None


def clean_markdown_inline(text: str) -> str:
    """Remove markdown bold, code ticks, and links from a string."""
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    cleaned = re.sub(r"[*`_#]", "", cleaned)
    # Strip leading bullet indicators
    cleaned = re.sub(r"^[\s*\->\d.]+", "", cleaned)
    return cleaned.strip()


def analyze_readme(repo_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Reads and analyzes the chosen repository's README file.
    Generates intelligent questions specifically and personally tailored to that repository.
    """
    resolved_dir, remote_content, resolved_repo_name = resolve_repo_dir(repo_path)
    repo_name = resolved_repo_name or resolved_dir.name or "Repository"

    content: str = ""
    filename = "README.md"
    readme_path_str: Optional[str] = None

    if remote_content:
        content = remote_content
        filename = "README.md (Remote GitHub)"
        readme_path_str = f"github.com/{repo_name}"
    else:
        readme_file = find_readme_file(resolved_dir)
        if readme_file:
            filename = readme_file.name
            try:
                content = readme_file.read_text(encoding="utf-8", errors="ignore")
                try:
                    readme_path_str = str(readme_file.relative_to(resolved_dir.parent))
                except Exception:
                    readme_path_str = str(readme_file)
            except Exception as exc:
                logger.warning("Failed to read README file %s: %s", readme_file, exc)

    if not content:
        # Graceful fallback when no README exists
        return {
            "has_readme": False,
            "filename": None,
            "readme_path": None,
            "repo_name": repo_name,
            "title": f"{repo_name} Codebase",
            "summary": f"No README file found for {repo_name}. Connect or index this repository to explore code symbols.",
            "features": [],
            "key_modules": [],
            "suggested_questions": [
                f"Where is the main entry point defined in {repo_name}?",
                f"How is error handling and logging structured?",
                f"Where are the core data models and helper functions located?",
                f"How are configuration settings and dependencies managed?",
            ],
            "categories": {
                "Architecture": [f"Where is the main entry point defined in {repo_name}?"],
                "Logic & Models": [f"Where are the core data models and helper functions located?"],
                "Configuration": [f"How are configuration settings and dependencies managed?"],
            },
        }

    lines = content.splitlines()

    # 1. Extract Project Title
    title = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            t_cand = clean_markdown_inline(stripped)
            # Remove emojis and non-alphanumeric noise at start
            t_cand = re.sub(r"^[^\w\s]+", "", t_cand).strip()
            if len(t_cand) > 3:
                title = t_cand
                break
    if not title:
        title = f"{repo_name} Architecture"

    # 2. Extract Project Summary
    summary = ""
    for line in lines:
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith("-")
            and not stripped.startswith("*")
            and not stripped.startswith("`")
            and len(stripped) > 20
        ):
            summary = clean_markdown_inline(stripped)
            break
    if not summary:
        summary = f"{title} repository documentation and codebase architecture overview."

    # 3. Extract Explicit Questions from README (e.g. ## Questions to Ask this Codebase, FAQ)
    explicit_questions: List[str] = []
    in_question_section = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,3}\s+.*(question|faq|common\s+codebase).*", stripped, re.IGNORECASE):
            in_question_section = True
            continue
        elif in_question_section and stripped.startswith("#"):
            in_question_section = False

        if in_question_section:
            q_clean = clean_markdown_inline(stripped)
            if q_clean and len(q_clean) > 8:
                if not q_clean.endswith("?"):
                    q_clean += "?"
                if q_clean not in explicit_questions:
                    explicit_questions.append(q_clean)
        else:
            # Also catch any line in the README ending with ?
            q_candidate = clean_markdown_inline(stripped)
            if q_candidate.endswith("?") and 15 < len(q_candidate) < 140:
                if q_candidate not in explicit_questions:
                    explicit_questions.append(q_candidate)

    # 4. Extract Features & Capabilities
    features: List[str] = []
    in_feature_section = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,3}\s+.*(feature|highlight|capabilit|overview).*", stripped, re.IGNORECASE):
            in_feature_section = True
            continue
        elif in_feature_section and stripped.startswith("#") and not stripped.startswith("###"):
            in_feature_section = False

        # Bold bullet: - **Feature Name**: description
        bold_bullet = re.match(r"^[\s*\->]+\s+\*\*([^*]+)\*\*[:\s]*(.*)$", stripped)
        if bold_bullet:
            f_name = clean_markdown_inline(bold_bullet.group(1))
            f_desc = clean_markdown_inline(bold_bullet.group(2))
            item = f"{f_name}: {f_desc}" if f_desc else f_name
            if item not in features and len(features) < 8:
                features.append(item)
        # Subheading bold: ### **Feature Name**
        elif re.match(r"^#{2,4}\s+\*\*([^*]+)\*\*$", stripped):
            h_feat = clean_markdown_inline(re.sub(r"^#{2,4}\s+", "", stripped))
            if h_feat and h_feat not in features and len(features) < 8:
                features.append(h_feat)
        elif in_feature_section and (stripped.startswith("-") or stripped.startswith("*")):
            bullet_text = clean_markdown_inline(stripped)
            if bullet_text and len(bullet_text) > 10 and bullet_text not in features and len(features) < 8:
                features.append(bullet_text)

    # 5. Extract Key Modules / Architecture files
    modules: List[str] = []
    for line in lines:
        # Extract file paths or endpoints like `services/payment.py` or `api/checkout.py`
        file_matches = re.findall(
            r"`([a-zA-Z0-9_\-/]+\.(?:py|tsx|ts|jsx|js|json|rs|go|html|css|yaml|yml|kt|java))`",
            line
        )
        for fm in file_matches:
            if fm not in modules and len(modules) < 10:
                modules.append(fm)

    # 6. Generate Questions Specifically Tailored to THIS Repository
    feature_questions: List[str] = []
    arch_questions: List[str] = []
    logic_questions: List[str] = []
    config_questions: List[str] = []

    # A. Questions from detected features
    for f in features:
        f_title = f.split(":")[0].strip()
        # Clean leading numbering or special chars
        f_title = re.sub(r"^[\d\.\-\s]+", "", f_title).strip()
        if len(f_title) > 3:
            feature_questions.append(f"Where is {f_title} implemented in the codebase?")
            logic_questions.append(f"How does {f_title} work step-by-step?")

    # B. Questions from detected module files
    for m in modules[:5]:
        base_name = Path(m).name.lower()
        if "main" in base_name or "app" in base_name:
            arch_questions.append(f"Where is the main application setup defined in `{m}`?")
        elif "auth" in base_name or "jwt" in base_name or "security" in base_name:
            logic_questions.append(f"How is authentication and security handled in `{m}`?")
        elif "pay" in base_name or "checkout" in base_name or "cart" in base_name:
            logic_questions.append(f"How does transaction processing work in `{m}`?")
        elif "fhir" in base_name or "patient" in base_name or "record" in base_name:
            logic_questions.append(f"How are patient health records validated in `{m}`?")
        elif "api" in base_name or "route" in base_name or "controller" in base_name:
            arch_questions.append(f"Where are API endpoints registered in `{m}`?")
        else:
            arch_questions.append(f"What is the primary role of `{m}` in this codebase?")

    # C. Domain-specific synthesized questions based on content keywords
    content_lower = content.lower()

    # Mobile / Android context (e.g. CAPE)
    if "android" in content_lower or "sensor" in content_lower or "biometric" in content_lower:
        arch_questions.append(f"Where are background sensor services initialized in {repo_name}?")
        logic_questions.append(f"How does the policy engine evaluate real-time device context?")
    if "openclaw" in content_lower or "agent" in content_lower:
        feature_questions.append(f"Where is AI agent orchestration and decision-making configured?")
    if "calendar" in content_lower:
        feature_questions.append(f"How does calendar intelligence schedule focus and automate device modes?")

    # E-Commerce domain
    if "stripe" in content_lower or "payment" in content_lower:
        logic_questions.append(f"Where is payment gateway integration and signature verification handled?")
    if "inventory" in content_lower or "cart" in content_lower:
        logic_questions.append(f"How does the cart manage inventory reservations and discount pricing?")

    # Auth & Security domain
    if "oauth" in content_lower or "pkce" in content_lower:
        feature_questions.append(f"How does the OAuth2 PKCE authorization code exchange work?")
    if "jwt" in content_lower or "token" in content_lower:
        logic_questions.append(f"Where is JWT token issuance and cryptographic verification configured?")
    if "argon2" in content_lower or "password" in content_lower:
        logic_questions.append(f"Where is password hashing and credential validation defined?")

    # Healthcare domain
    if "fhir" in content_lower or "hl7" in content_lower:
        logic_questions.append(f"How are FHIR clinical patient records ingested and validated?")
    if "hipaa" in content_lower or "phi" in content_lower:
        config_questions.append(f"Where is HIPAA compliant field-level data encryption enforced?")

    # Code search / CodeLens domain (only if this repository is CodeLens)
    if "bm25" in content_lower:
        logic_questions.append("How does BM25 keyword matching compute scores?")
    if "tree-sitter" in content_lower or "ast chunk" in content_lower:
        logic_questions.append("How does Tree-Sitter AST chunking parse code?")
    if "embedding" in content_lower and "vector" in content_lower:
        logic_questions.append("Where are dense vector embeddings generated?")

    # Configuration questions tailored to repository
    config_questions.append(f"How are environment variables and system settings configured in {repo_name}?")
    config_questions.append(f"Where are project dependencies and build scripts defined?")

    # Assemble top suggestions
    top_suggestions: List[str] = []

    def _add_q(q: str):
        q_norm = q.strip()
        if q_norm and q_norm not in top_suggestions and len(top_suggestions) < 8:
            top_suggestions.append(q_norm)

    # 1. Prioritize explicit questions written in README
    for eq in explicit_questions:
        _add_q(eq)

    # 2. Add domain feature questions
    for fq in feature_questions:
        _add_q(fq)

    # 3. Add architecture & module questions
    for aq in arch_questions:
        _add_q(aq)

    # 4. Add logic & algorithm questions
    for lq in logic_questions:
        _add_q(lq)

    # 5. Add config questions
    for cq in config_questions:
        _add_q(cq)

    # Fallbacks personalized to this exact repository
    fallbacks = [
        f"Where is the main entry point and service layout defined for {title}?",
        f"How does {title} handle request processing and error recovery?",
        f"Where are core data models and business logic located in `{repo_name}`?",
        f"How are configuration settings and secrets managed in {repo_name}?",
    ]
    for fb in fallbacks:
        _add_q(fb)

    all_qs = top_suggestions
    categorized = {
        "Architecture & Structure": [
            q for q in all_qs if any(w in q.lower() for w in ["where", "structure", "setup", "layout", "module", "api", "entry", "service"])
        ][:4],
        "Features & Capabilities": [
            q for q in all_qs if any(w in q.lower() for w in ["how", "feature", "calendar", "sensor", "payment", "token", "patient", "checkout", "cart", "agent", "mode"])
        ][:4],
        "Algorithms & Logic": [
            q for q in all_qs if any(w in q.lower() for w in ["step", "calculate", "flow", "verify", "encrypt", "validate", "rate", "decision", "score", "lock"])
        ][:4],
        "Configuration & Setup": [
            q for q in all_qs if any(w in q.lower() for w in ["config", "env", "setting", "build", "secret", "permission", "depend"])
        ][:3] or [f"How are configuration settings managed in {repo_name}?"],
    }

    return {
        "has_readme": True,
        "filename": filename,
        "readme_path": readme_path_str,
        "repo_name": repo_name,
        "title": title,
        "summary": summary,
        "features": features[:6],
        "key_modules": modules[:8],
        "suggested_questions": top_suggestions[:8],
        "categories": categorized,
    }
