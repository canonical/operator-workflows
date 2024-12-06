import argparse
import dataclasses
import json
import pathlib


@dataclasses.dataclass(frozen=True)
class Result:
    test_case_id: str
    path: pathlib.Path

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.test_case_id == other.test_case_id


def main():
    """Combine Allure default results & actual results

    For every test: if actual result available, use that. Otherwise, use default result

    So that, if actual result not available, Allure report will show "unknown"/"failed" test result
    instead of omitting the test
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--allure-results-dir", required=True)
    parser.add_argument("--allure-collection-default-results-dir", required=True)
    args = parser.parse_args()

    actual_results = pathlib.Path(args.allure_results_dir)
    default_results = pathlib.Path(args.allure_collection_default_results_dir)

    results: dict[pathlib.Path, set[Result]] = {
        actual_results: set(),
        default_results: set(),
    }
    for directory, results_ in results.items():
        for path in directory.glob("*-result.json"):
            with path.open("r") as file:
                id_ = json.load(file)["testCaseId"]
            results_.add(Result(id_, path))

    actual_results.mkdir(exist_ok=True)

    missing_results = results[default_results] - results[actual_results]
    for default_result in missing_results:
        # Move to `actual_results` directory
        default_result.path.rename(actual_results / default_result.path.name)
