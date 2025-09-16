from flask import Flask, request, render_template, url_for, jsonify
import logging, re, shutil

from services.repo_manager import clone_repo, git_push
from services.analyzer import analyze_repo
from services.session_store import QA_SESSIONS

# ------------------- Flask Setup -------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
logging.basicConfig(level=logging.INFO)

# ------------------- Routes -------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        repo_url = request.form.get("repo_url")
        try:
            repo_path = clone_repo(repo_url)
            repo_id = repo_path.split("/")[-1]

            summary, techstack, workflow, fixes, design, uml, qa = analyze_repo(repo_path, repo_id)

            QA_SESSIONS[repo_id] = {
                "qa": qa,
                "repo_path": repo_path,
                "repo_url": repo_url,
                "summary": summary,
                "techstack": techstack,
                "workflow": workflow,
                "fixes": fixes,
                "design": design,
                "uml": uml,
                "history": []  # chat history
            }

            return render_template("preview.html", **QA_SESSIONS[repo_id], repo_id=repo_id)
        except Exception as e:
            return f"<h3>❌ Error: {e}</h3><br><a href='{url_for('index')}'>🔄 Try Again</a>"
    return render_template("index.html")

@app.route("/ask_question", methods=["POST"])
def ask_question():
    data = request.get_json()
    repo_id = data.get("repo_id")
    question = data.get("user_question")

    if repo_id not in QA_SESSIONS:
        return jsonify({"error": "Repo context not found"}), 400

    qa_data = QA_SESSIONS[repo_id]
    qa = qa_data["qa"]

    # Run query
    answer = qa.run(question)
    answer = re.sub(r'\n{3,}', '\n\n', str(answer))

    # Save history
    qa_data["history"].append({"question": question, "answer": answer})

    return jsonify({"question": question, "answer": answer})

@app.route("/confirm_push", methods=["POST"])
def confirm_push():
    repo_id = request.form.get("repo_id")
    if repo_id not in QA_SESSIONS:
        return "<h3>❌ Repo context missing.</h3><br><a href='/'>🔄 Start Again</a>"

    qa_data = QA_SESSIONS[repo_id]
    repo_url = qa_data["repo_url"]
    repo_path = qa_data["repo_path"]

    username = request.form.get("username")
    pat = request.form.get("pat")

    git_push(repo_path, repo_url, username, pat)
    shutil.rmtree(repo_path)
    del QA_SESSIONS[repo_id]

    return render_template("push.html", success=True)

@app.route("/cancel", methods=["POST"])
def cancel():
    repo_id = request.form.get("repo_id")
    if repo_id in QA_SESSIONS:
        shutil.rmtree(QA_SESSIONS[repo_id]["repo_path"])
        del QA_SESSIONS[repo_id]
    return render_template("push.html", success=False)

# ------------------- Run -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

