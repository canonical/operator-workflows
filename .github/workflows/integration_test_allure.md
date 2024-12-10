# Allure Report Integration

[Allure Report](https://allurereport.org/) for [integration_test_run.yaml](https://github.com/canonical/operator-workflows?tab=readme-ov-file#integration-test-workflow-canonicaloperator-workflowsgithubworkflowsintegration_testyamlmain)

In order to integrate Allure with your repository, perform the following actions:

## 1. Adding allure-pytest and pytest collection plugin

Please add the following into the `requirements.txt` that is called by the integration test -

```
allure-pytest>=2.8.18
```

Add the following line under the dependencies (`deps`) in the integration section inside `tox.ini` -

```
git+https://github.com/canonical/operator-workflows@main\#subdirectory=python/pytest_plugins/allure_pytest_collection_report
```

## 2. Calling the allure-workflow

Add the following lines at the end of the workflow that runs the integrations tests by calling the reuable workflow [integration-test.yaml](https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml):

```
  allure-report:
    if: always() && !cancelled()
    needs:
      - [list of jobs with tests you would like to visualize]
    uses: canonical/operator-workflows/.github/workflows/allure_report.yaml@main
```

Here's an [example for the above](https://github.com/canonical/github-runner-operator/pull/412).

**NOTE:** If the workflow is being called inside a matrix with the same test modules run with different parameters, the allure report will only display the results of the last combination.

## 3. Changing branch permissions

**NOTE:** For this, you would require admin access to the repository.

- Go to the repository's **Settings > Branches** and next to Branch protection rules, select **Add rule**
- Enter the branch name **gh-pages** and select **Allow force pushes** and click **Save changes**

## 4. Github pages branch

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

 - Enable gh pages publishing at ** Settings > Pages ** and set branch name as `gh-pages`:

<img width="816" alt="image" src="https://github.com/user-attachments/assets/346c04fc-0daa-40bc-92b5-93b0ea639f94">

 [Example PR for steps 1 & 2](https://github.com/canonical/github-runner-operator/pull/412/files#)
