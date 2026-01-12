# How to set up Allure Reports for integration tests

This how-to guide describes how to integrate [Allure Reports](https://allurereport.org/) into your code repository's [integration_test.yaml](https://github.com/canonical/operator-workflows?tab=readme-ov-file#integration-test-workflow-canonicaloperator-workflowsgithubworkflowsintegration_testyamlmain).

## Adding allure-pytest and pytest collection plugin

Add the following lines under the dependencies (`deps`) in the integration section inside `tox.ini`:

```
allure-pytest>=2.8.18
git+https://github.com/canonical/data-platform-workflows@v24.0.0\#subdirectory=python/pytest_plugins/allure_pytest_collection_report
```

## Calling the allure-workflow

To call the reusable workflow [allure_report.yaml](https://github.com/canonical/operator-workflows/blob/main/.github/workflows/allure_report.yaml), add the following lines at the end of the workflow that runs the integrations tests:

```
  allure-report:
    if: always() && !cancelled()
    needs:
      - [list of jobs that call integration_test workflow whose tests you would like to visualize]
    uses: canonical/operator-workflows/.github/workflows/allure_report.yaml@main
```

For an example of this implementation, see [the GitHub runner repository](https://github.com/canonical/github-runner-operator/pull/412).

**NOTE:** If the workflow is being called inside a matrix with the same test modules run with different parameters, the Allure Report will only display the results of the last combination.

## Changing branch permissions

**NOTE:** For this step, you need admin access to the repository.

If your repository is configured to have signed commits for all branches by default, you need to create a seperate protection rule for the `gh-pages` branch with the signed commits disabled.

- Go to the repository's **Settings > Branches** and next to Branch protection rules, select **Add rule**
- Enter the branch name **gh-pages** and click **Save changes** (Ensure that "require signed commits" is unchecked)

## Github pages branch

- Create `gh-pages` branch:

```
# For first run, manually create branch with no history 
 # (e.g. 
 # git checkout --orphan gh-pages
 # git rm -rf . 
 # touch .nojekyll 
 # git add .nojekyll 
 # git commit -m "Initial commit" 
 # git push origin gh-pages
 # ) 
 ```

 - Enable GitHub pages publishing at ** Settings > Pages ** and set branch name as `gh-pages`:

<img width="816" alt="image" src="https://github.com/user-attachments/assets/346c04fc-0daa-40bc-92b5-93b0ea639f94">

For an example of the first two steps, see [the GitHub runner repository](https://github.com/canonical/github-runner-operator/pull/412).
