"""Console adapter; the legacy modules remain private to this CLI process."""
from pathlib import Path
import runpy
import sys


def main():
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'scripts'))
    if sys.argv[1:] == ['skill-path']:
        print(root / 'skills' / 'research-video-analyzer')
        return
    if sys.argv[1:] == ['doctor']:
        runpy.run_path(str(root / 'scripts' / 'doctor.py'), run_name='__main__')
        return
    import va
    va.main()


if __name__ == '__main__':
    main()
