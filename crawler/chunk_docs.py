import json
import re
from pathlib import Path
from typing import List, Dict

RAW_DIR = Path("data/raw")
CHUNKED_DIR = Path("data/chunked")
CHUNKED_DIR.mkdir(parents=True, exist_ok=True)

# Chunk sizes in words
CHUNK_SIZE_HIGH = 300   # for H1/H2
CHUNK_SIZE_LOW = 500    # for H3/H4

def load_pages(raw_dir: Path) -> List[Dict]:
    pages = []
    for file_path in raw_dir.glob("*.md"):
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()
        # Extract metadata
        try:
            meta_str = content.split("---")[1].strip()
            meta = json.loads(meta_str)
        except Exception:
            meta = {"url": file_path.stem, "title": file_path.stem}
        md_content = content.split("---")[-1].strip()
        if md_content:
            pages.append({"url": meta.get("url", file_path.stem),
                          "title": meta.get("title", file_path.stem),
                          "content": md_content})
    return pages

def clean_text(text: str) -> str:
    lines = text.split("\n")
    filtered = []
    for line in lines:
        line = line.strip()
        if len(line) > 20 and not re.match(r"(Back to Top|Table of Contents|^\*+)", line, re.I):
            filtered.append(line)
    return "\n".join(filtered)

def chunk_text(text: str, size: int) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), size):
        chunk = " ".join(words[i:i+size])
        chunks.append(chunk)
    return chunks

def extract_sections(md: str) -> List[Dict]:
    # Split by headings, keep heading level
    pattern = re.compile(r"^(#+)\s+(.*)", re.MULTILINE)
    sections = []
    last_idx = 0
    matches = list(pattern.finditer(md))
    if not matches:
        return [{"level": 0, "text": clean_text(md)}]

    for i, match in enumerate(matches):
        level = len(match.group(1))
        start = match.start()
        if i > 0:
            prev = matches[i-1]
            sections.append({
                "level": len(prev.group(1)),
                "text": clean_text(md[prev.start():start])
            })
        if i == len(matches) - 1:
            sections.append({
                "level": level,
                "text": clean_text(md[start:])
            })
    return [sec for sec in sections if sec["text"]]

def main():
    pages = load_pages(RAW_DIR)
    all_chunks = []

    for page in pages:
        sections = extract_sections(page["content"])
        for section_idx, section in enumerate(sections):
            # choose chunk size based on heading level
            size = CHUNK_SIZE_HIGH if section["level"] <= 2 else CHUNK_SIZE_LOW
            chunks = chunk_text(section["text"], size)
            for chunk_idx, chunk in enumerate(chunks):
                all_chunks.append({
                    "url": page["url"],
                    "title": page["title"],
                    "section_index": section_idx,
                    "chunk_index": chunk_idx,
                    "heading_level": section["level"],
                    "content": chunk
                })

    out_file = CHUNKED_DIR / "chunked_pages_hierarchy.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"Processed {len(pages)} pages into {len(all_chunks)} hierarchical chunks.")
    print(f"Saved to {out_file}")

if __name__ == "__main__":
    main()
