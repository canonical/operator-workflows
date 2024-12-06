The `allure_add_default_for_missing_results` cli combines the Allure default results & actual results before generating the report. 

Currently, if the result of a test is not available (for reasons such as setup failure), allure omits the test. This CLI ensures that for every test, if actual result is available, it will use that. Otherwise, it uses the default result `unknown`.