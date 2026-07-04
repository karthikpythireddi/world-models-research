"""
Deploy the custom FastAPI dashboard to HuggingFace Spaces.
Usage: python3 scripts/deploy_to_hf.py --token hf_xxx
"""
import argparse
import pathlib
import shutil
import tempfile

from huggingface_hub import HfApi

REPO_ID   = "karthikpythireddi93/world-models-papers"
REPO_ROOT = pathlib.Path(__file__).parent.parent


def build_space(tmp: pathlib.Path):
    shutil.copy(REPO_ROOT / "server.py",       tmp / "server.py")
    shutil.copy(REPO_ROOT / "requirements.txt", tmp / "requirements.txt")
    shutil.copy(REPO_ROOT / "Dockerfile",       tmp / "Dockerfile")

    papers_src = REPO_ROOT / "data" / "papers.json"
    if papers_src.exists():
        shutil.copy(papers_src, tmp / "papers.json")
    else:
        (tmp / "papers.json").write_text('{"papers":[],"last_updated":null}')

    static_dst = tmp / "static"
    shutil.copytree(REPO_ROOT / "static", static_dst)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="HuggingFace write token")
    args = parser.parse_args()

    api = HfApi(token=args.token)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        build_space(tmp)

        print("Files to upload:")
        for f in sorted(tmp.rglob("*")):
            if f.is_file():
                print(f"  {f.relative_to(tmp)}  ({f.stat().st_size // 1024}KB)")

        api.upload_folder(
            folder_path=str(tmp),
            repo_id=REPO_ID,
            repo_type="space",
            commit_message="Deploy: custom FastAPI + vanilla JS dashboard",
        )

    print(f"\nDone! https://huggingface.co/spaces/{REPO_ID}")


if __name__ == "__main__":
    main()
