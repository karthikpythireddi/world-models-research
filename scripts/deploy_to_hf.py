"""
Deploys the dashboard to HuggingFace Spaces.
Run once: python3 scripts/deploy_to_hf.py --token hf_xxx
"""
import argparse
import pathlib
import tempfile
import shutil

from huggingface_hub import HfApi

REPO_ID   = "karthikpythireddi93/world-models-papers"
REPO_ROOT = pathlib.Path(__file__).parent.parent


def build_space(tmp: pathlib.Path):
    """Assemble all Space files into a temp directory."""

    # app.py — fix DATA_PATH for flat Space layout
    src = (REPO_ROOT / "dashboard" / "app.py").read_text()
    src = src.replace(
        'Path(__file__).parent.parent / "data" / "papers.json"',
        'Path("papers.json")',
    )
    (tmp / "app.py").write_text(src)

    # Dockerfile — all files are at repo root in the Space
    dockerfile = """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY papers.json .
EXPOSE 7860
CMD ["streamlit", "run", "app.py", \
"--server.port=7860", "--server.address=0.0.0.0", \
"--server.headless=true"]
"""
    (tmp / "Dockerfile").write_text(dockerfile)

    # requirements.txt
    shutil.copy(REPO_ROOT / "requirements.txt", tmp / "requirements.txt")

    # papers.json
    shutil.copy(REPO_ROOT / "data" / "papers.json", tmp / "papers.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="HuggingFace API token")
    args = parser.parse_args()

    api = HfApi(token=args.token)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        build_space(tmp)

        print("Files to upload:")
        for f in sorted(tmp.iterdir()):
            print(f"  {f.name} ({f.stat().st_size // 1024}KB)")

        api.upload_folder(
            folder_path=str(tmp),
            repo_id=REPO_ID,
            repo_type="space",
            commit_message="Deploy: fix all paths and Dockerfile",
        )

    print(f"\nDone! https://huggingface.co/spaces/{REPO_ID}")


if __name__ == "__main__":
    main()
