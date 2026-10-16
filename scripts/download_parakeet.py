"""Download the official sherpa-onnx INT8 export into the project."""
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = 'sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8'
destination = ROOT / 'models' / 'parakeet-v3'
destination.mkdir(parents=True, exist_ok=True)
archive = ROOT / 'models' / (NAME + '.tar.bz2')
url = f'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{NAME}.tar.bz2'
if not archive.exists():
    print('Downloading official Parakeet v3 INT8 export...', flush=True)
    partial = archive.with_suffix('.part')
    urllib.request.urlretrieve(url, partial)
    partial.replace(archive)
with tarfile.open(archive) as source:
    for filename in ('encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt'):
        member = source.extractfile(f'{NAME}/{filename}')
        if member is None:
            raise RuntimeError(f'Missing {filename}')
        with member, (destination / filename).open('wb') as target:
            import shutil
            shutil.copyfileobj(member, target)
print(f'Ready: {destination}', flush=True)
