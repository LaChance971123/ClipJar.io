# ClipJar
CLI pipeline to generate short vertical videos from text scripts.

## Installation
```bash
git clone <repo-url>
cd ClipJar.io
pip install -r requirements.txt
```

## Usage
```bash
python cli.py --script-file my_story.txt --output result.mp4
```

## Configuration
Edit `config/config.json` or copy `config/config.example.json`.
Set API keys in `.env` and place background videos in `assets/backgrounds`.

## Contributing
Fork the repository and submit pull requests. Run `pytest` before committing.
