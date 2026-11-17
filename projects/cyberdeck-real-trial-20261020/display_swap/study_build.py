"""Generate Fielddeck 5 for the registered digital study."""
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from build import build, write
from study_contract import BASELINE, PACKAGE, REVISION, engineering_result, evaluator, requirements


def main():
    selected = requirements()
    with TemporaryDirectory(prefix=".fielddeck5-build-", dir=PACKAGE) as temp:
        result = Path(temp) / "output"
        _, power = build(BASELINE, result, evaluator=evaluator(), requirements=selected)
        shutil.copytree(result, REVISION, dirs_exist_ok=True)
    write(REVISION / "engineering.json", engineering_result(power, selected))


if __name__ == "__main__":
    main()
