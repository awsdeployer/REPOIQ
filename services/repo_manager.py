import tempfile, shutil, logging
from git import Repo

def clone_repo(repo_url):
    temp_dir = tempfile.mkdtemp()
    Repo.clone_from(repo_url, temp_dir)
    return temp_dir

def git_push(repo_path, repo_url, username, pat):
    import sys
    try:
        logging.info(f"[git_push] repo_path={repo_path}")
        repo = Repo(repo_path)
        logging.info("[git_push] git add .")
        repo.git.add(A=True)
        logging.info("[git_push] git commit")
        try:
            repo.index.commit("Automated: Add repo analysis, fixes, UML, and design diagram")
        except Exception as ce:
            logging.warning(f"[git_push] Commit warning: {ce}")
        if repo_url.startswith("https://"):
            push_url = repo_url.replace("https://", f"https://{username}:{pat}@")
        else:
            raise Exception("Only HTTPS GitHub URLs supported")
        logging.info(f"[git_push] push_url={push_url}")
        origin = repo.remote(name="origin")
        origin.set_url(push_url)
        logging.info("[git_push] pushing...")
        result = origin.push()
        logging.info(f"[git_push] push result: {result}")
        if result and hasattr(result[0], 'summary'):
            logging.info(f"[git_push] push summary: {result[0].summary}")
        if result and hasattr(result[0], 'flags') and result[0].flags & result[0].ERROR:
            return f"Push failed: {result[0].summary}"
        return None
    except Exception as e:
        logging.error(f"[git_push] Exception: {e}")
        return str(e)

