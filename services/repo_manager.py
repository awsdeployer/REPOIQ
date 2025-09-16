import tempfile, shutil, logging
from git import Repo

def clone_repo(repo_url):
    temp_dir = tempfile.mkdtemp()
    Repo.clone_from(repo_url, temp_dir)
    return temp_dir

def git_push(repo_path, repo_url, username, pat):
    repo = Repo(repo_path)
    repo.git.add(A=True)
    repo.index.commit("Automated: Add repo analysis, fixes, UML, and design diagram")

    if repo_url.startswith("https://"):
        push_url = repo_url.replace("https://", f"https://{username}:{pat}@")
    else:
        raise Exception("Only HTTPS GitHub URLs supported")

    origin = repo.remote(name="origin")
    origin.set_url(push_url)
    origin.push()

