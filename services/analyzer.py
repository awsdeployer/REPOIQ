import os, logging
from langchain.schema import Document
from services.rag_pipeline import build_rag
from services.graph_rag_pipeline import build_graph_rag

def extract_codebase_text(repo_path):
    docs = []
    allowed_exts = (".py", ".js", ".ts", ".java", ".go", ".html", ".css", ".json", ".yml", ".yaml", ".txt")
    skip_exts = (".md", ".rst", ".csv", ".tsv", ".log", ".env", ".ini", ".cfg", ".db", ".sqlite", ".exe", ".dll", ".so", ".zip", ".tar", ".gz", ".7z", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4", ".mov", ".avi", ".bin")
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", ".env", ".idea", ".vscode", "dist", "build", ".pytest_cache"}

    for root, dirs, files in os.walk(repo_path):
        # Remove unwanted dirs in-place, but keep .github
        dirs[:] = [d for d in dirs if d not in skip_dirs or d == ".github"]
        for f in files:
            file_path = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in skip_exts:
                continue
            if ext not in allowed_exts and not f.lower().startswith("dockerfile"):
                continue
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
    import concurrent.futures
    docs = extract_codebase_text(repo_path)

    # Toggle: use_graph = True to use LangGraph pipeline
    use_graph = True
    if use_graph:
        graph = build_graph_rag(docs, repo_id)
        # Start with state as a dict
        state = {"docs": docs}
        state = graph.invoke(state, config={"run_id": "split"})
        state = graph.invoke(state, config={"run_id": "embed_store"})
        state = graph.invoke(state, config={"run_id": "retriever"})
        retriever = state["retriever"]
        from langchain.prompts import PromptTemplate
        from langchain.chains import RetrievalQA
        from langchain_aws import ChatBedrock
        MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        llm = ChatBedrock(model_id=MODEL_ID)
        qa_prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=(
                "You are an expert developer analyzing a GitHub repository.\n"
                "Use ONLY the repository context below to answer questions.\n"
                "Always cite the file name(s).\n\n"
                "Repository Context:\n{context}\n\n"
                "Question: {question}\n\n"
                "Answer clearly, and reference the file(s)."
            )
        )
        qa = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            chain_type="stuff",
            chain_type_kwargs={"prompt": qa_prompt}
        )
    else:
        qa, vectorstore, retriever = build_rag(docs, repo_id)

    prompts = {
        "summary": "Summarize repository purpose and main components.",
        "techstack": "List the main tech stack (frameworks, languages, tools).",
        "workflow": "Write a detailed developer guide for this repo."
    }

    # Helper: get main/entry files (e.g., app.py, main.py, root .py, .js, .ts, .java, etc.)
    def get_main_files(repo_path):
        main_files = []
        main_names = ["app", "main", "index", "server", "start"]
        main_exts = [".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".cs"]
        for f in os.listdir(repo_path):
            name, ext = os.path.splitext(f.lower())
            if ext in main_exts and os.path.isfile(os.path.join(repo_path, f)):
                if any(n in name for n in main_names) or f.lower() in [n+e for n in main_names for e in main_exts]:
                    main_files.append(os.path.join(repo_path, f))
        return main_files

    # Helper: get content of files as string
    def get_file_content(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f"[FILE: {os.path.basename(file_path)}]\n" + f.read().strip()
        except Exception:
            return ""

    # Patch qa.run to force-include main files for summary and diagram/system prompts
    def run_with_mainfile_boost(prompt, orig_run=qa.run):
        boost_keywords = ["diagram", "uml", "mermaid", "system", "architecture", "summary", "main component"]
        if any(word in prompt.lower() for word in boost_keywords):
            main_files = get_main_files(repo_path)
            main_context = "\n\n".join(get_file_content(f) for f in main_files if get_file_content(f))
            if main_context:
                # Prepend main file content to the prompt
                prompt = f"(Main files for context:)\n{main_context}\n\n{prompt}"
        return orig_run(prompt)

    results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_key = {}
        for key, prompt in prompts.items():
            if key == "summary":
                future = executor.submit(lambda p=prompt: run_with_mainfile_boost(p))
            else:
                future = executor.submit(qa.run, prompt)
            future_to_key[future] = key
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                results[key] = f"Error: {exc}"

    # For diagram/system prompts, force-include main files in context
    fixes = qa.run("Suggest improvements for best practices and scalability.")
    design = run_with_mainfile_boost("Generate a Mermaid diagram in markdown fenced code block format.")
    uml = run_with_mainfile_boost("Generate UML diagrams (class + sequence) in Mermaid markdown format.")

    return results["summary"], results["techstack"], results["workflow"], fixes, design, uml, qa

