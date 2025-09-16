import os, logging
from langchain.schema import Document
from services.rag_pipeline import build_rag

def extract_codebase_text(repo_path):
    docs = []
    allowed_exts = (".py", ".js", ".ts", ".java", ".go", ".html", ".css",
                    ".json", ".yml", ".yaml", ".md", ".txt")

    for root, _, files in os.walk(repo_path):
        for f in files:
            file_path = os.path.join(root, f)
            if f.lower().endswith(allowed_exts) or f.lower().startswith("dockerfile"):
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                        text = file.read().strip()
                        if text:
                            wrapped_text = f"[FILE: {f}]\n{text}"
                            docs.append(Document(page_content=wrapped_text, metadata={"source": file_path}))
                except Exception as e:
                    logging.warning(f"Failed to read {file_path}: {e}")

    logging.info(f"✅ Indexed {len(docs)} files total")
    return docs

def analyze_repo(repo_path, repo_id):
    docs = extract_codebase_text(repo_path)
    qa, vectorstore, retriever = build_rag(docs, repo_id)

    summary = qa.run("Summarize repository purpose and main components.")
    techstack = qa.run("List the main tech stack (frameworks, languages, tools).")
    workflow = qa.run("Write a detailed developer guide for this repo.")
    fixes = qa.run("Suggest improvements for best practices and scalability.")
    design = qa.run("Generate a Mermaid diagram in markdown fenced code block format.")
    uml = qa.run("Generate UML diagrams (class + sequence) in Mermaid markdown format.")

    return summary, techstack, workflow, fixes, design, uml, qa

