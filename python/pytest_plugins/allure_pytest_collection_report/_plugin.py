# Upstream feature request to replace this plugin:
# https://github.com/allure-framework/allure-python/issues/821

import allure_commons.logger
import allure_commons.model2
import allure_commons.types
import allure_commons.utils
import allure_pytest.listener
import allure_pytest.utils


def pytest_addoption(parser):
    parser.addoption(
        "--allure-collection-dir",
        help="Generate default Allure results (used by GitHub Actions) in \
            this directory for tests that are missing Allure results",
    )


def pytest_configure(config):
    if config.option.allure_collection_dir:
        config.option.collectonly = True


def pytest_collection_finish(session):
    report_dir = session.config.option.allure_collection_dir
    if not report_dir:
        return

    # Copied from `allure_pytest.listener.AllureListener._cache`
    _cache = allure_pytest.listener.ItemCache()
    # Modified from `allure_pytest.plugin.pytest_configure`
    file_logger = allure_commons.logger.AllureFileLogger(report_dir)

    for item in session.items:
        # Modified from
        # `allure_pytest.listener.AllureListener.pytest_runtest_protocol`
        uuid = _cache.push(item.nodeid)
        test_result = allure_commons.model2.TestResult(name=item.name, uuid=uuid)

        # Copied from `allure_pytest.listener.AllureListener.pytest_runtest_setup`
        params = (
            allure_pytest.listener.AllureListener._AllureListener__get_pytest_params(
                item
            )
        )
        test_result.name = allure_pytest.utils.allure_name(item, params)
        full_name = allure_pytest.utils.allure_full_name(item)
        test_result.fullName = full_name
        test_result.testCaseId = allure_commons.utils.md5(full_name)
        test_result.description = allure_pytest.utils.allure_description(item)
        test_result.descriptionHtml = allure_pytest.utils.allure_description_html(item)
        current_param_names = [param.name for param in test_result.parameters]
        test_result.parameters.extend(
            [
                allure_commons.model2.Parameter(
                    name=name, value=allure_commons.utils.represent(value)
                )
                for name, value in params.items()
                if name not in current_param_names
            ]
        )

        # Copied from `allure_pytest.listener.AllureListener.pytest_runtest_teardown`
        listener = allure_pytest.listener.AllureListener
        test_result.historyId = allure_pytest.utils.get_history_id(
            test_result.fullName,
            test_result.parameters,
            original_values=listener._AllureListener__get_pytest_params(item),
        )
        test_result.labels.extend(
            [
                allure_commons.model2.Label(name=name, value=value)
                for name, value in allure_pytest.utils.allure_labels(item)
            ]
        )
        test_result.labels.extend(
            [
                allure_commons.model2.Label(
                    name=allure_commons.types.LabelType.TAG, value=value
                )
                for value in allure_pytest.utils.pytest_markers(item)
            ]
        )
        allure_pytest.listener.AllureListener._AllureListener__apply_default_suites(
            None, item, test_result
        )
        test_result.labels.append(
            allure_commons.model2.Label(
                name=allure_commons.types.LabelType.HOST,
                value=allure_commons.utils.host_tag(),
            )
        )
        test_result.labels.append(
            allure_commons.model2.Label(
                name=allure_commons.types.LabelType.FRAMEWORK, value="pytest"
            )
        )
        test_result.labels.append(
            allure_commons.model2.Label(
                name=allure_commons.types.LabelType.LANGUAGE,
                value=allure_commons.utils.platform_label(),
            )
        )
        test_result.labels.append(
            allure_commons.model2.Label(
                name="package", value=allure_pytest.utils.allure_package(item)
            )
        )
        test_result.links.extend(
            [
                allure_commons.model2.Link(link_type, url, name)
                for link_type, url, name in allure_pytest.utils.allure_links(item)
            ]
        )

        # Modified from `allure_pytest.listener.AllureListener.pytest_runtest_protocol`
        test_result.status = allure_commons.model2.Status.UNKNOWN
        # Modified from `allure_commons.reporter.AllureReporter.close_test`
        file_logger.report_result(test_result)
