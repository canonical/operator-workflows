# OWASP ZAP

[OWASP ZAP](https://www.zaproxy.org/) is an open-source web application security scanner.

## Description

By enabling ZAP in the integration test, the [ZAP full scan GitHub action](https://github.com/marketplace/actions/owasp-zap-full-scan) will run a ZAP full scan that attacks the web application to find additional vulnerabilities.

The alerts will be maintained as a GitHub issue in the corresponding repository as well as an artifact in the Integration Test workflow.

## Warnings

- The script can potentially run for a long period. The default value for ``zap-cmd-options`` prevents that by setting a max time of 60 minutes. Mind that when changing this parameter.
- By deciding to run against an external target, since it simulates an attack, you should only use the full scan against targets that you have permission to test.

## How to use

If there is no need for customization, the test can be enabled by setting the parameter ``zap-enabled`` to true.

Then, after the integration tests, the ZAP full scan will run against the Charm unit IP address (port 80) and the logs can be viewed in the Job output, the artifact, or if vulnerabilities are found, in an issue entitled 'OWASP ZAP report'.

If future scans identify a fixed issue or new alerts the action will update the issue with the required information.

## Examples

### Default

```yaml
jobs:
  integration-tests:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    secrets: inherit
    with:
      zap-enabled: true
```

Since zap-target is not set, the unit IP address will be used as the target.

### Custom target port and run command before the test

A ``ZAP_TARGET`` environment variable is available with the ``zap_target`` parameter value or if is not set, with the unit IP address.

```yaml
jobs:
  integration-tests:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    secrets: inherit
    with:
      zap-enabled: true
      zap-target: localhost
      zap-target-port: 80
      zap-before-command: "curl -H \"Host: indico.local\" $ZAP_TARGET/bootstrap --data-raw 'csrf_token=00000000-0000-0000-0000-000000000000&first_name=admin&last_name=admin&email=admin%40admin.com&username=admin&password=lunarlobster&confirm_password=lunarlobster&affiliation=Canonical'"
```

### Authorization Header

See more information about authorization headers in [Authentication Env Vars](https://www.zaproxy.org/docs/authentication/handling-auth-yourself/#authentication-env-vars).

```yaml
jobs:
  integration-tests:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    secrets: inherit
    with:
      zap-enabled: true
      zap-auth-header: Auth
      zap-auth-value: SomeValue
```

### Custom Header (except Host)

It's possible to override or modify the behavior of the script components by using a [Scan Hook](https://www.zaproxy.org/docs/docker/scan-hooks/). Within the hook, a script can be loaded to change the request and add a new header.

First, create a ```hook.py``` file with the following content:

```python
# pylint: disable=missing-module-docstring,invalid-name,unused-argument
import logging


def zap_started(zap, target):
    """Actions when starts

    Args:
        zap (ZAPv2): ZAPv2 instance
        target (string): Target being scanned
    """
    logging.info(
        zap.script.load(
            "Add Header Script",
            "httpsender",
            "python : jython",
            "/zap/wrk/tests/zap/add_header_request.py",
        )
    )
    logging.info(zap.script.enable("Add Header Script"))


def zap_pre_shutdown(zap):
    """Actions before shutdown

    Args:
        zap (ZAPv2): ZAPv2 instance
    Returns:
        None
    """
    logging.info("script.listEngines: %s", zap.script.list_engines)
    logging.info("script.listScripts: %s", zap.script.list_scripts)
```

Note: The ```zap_pre_shutdown``` was altered just to show the script list and confirm if it was loaded as expected.

Then, create a ```add_header_request.py``` file with the following content:

```python
# pylint: disable=missing-module-docstring,invalid-name,unused-argument
def sendingRequest(msg, initiator, helper):  # noqa: N802
    """sendingRequest is a name defined and expected by ZAP tool
    Args:
        msg (HttpMessage): all requests/responses sent/received by ZAP
        initiator (int): the component that initiated the request
        helper (HttpSender): returns the HttpSender instance used to send the request
    Returns:
        HttpMessage: returns HttpMessage updated
    """
    msg.getRequestHeader().setHeader("Some-Header", "Some-Value")
    return msg


def responseReceived(msg, initiator, helper):  # noqa: N802
    """responseReceived is a name defined and expected by ZAP tool
    Args:
        msg (HttpMessage): all requests/responses sent/received by ZAP
        initiator (int): the component that initiated the request
        helper (HttpSender): returns the HttpSender instance used to send the request
    Returns:
        None
    """
```

This will add every header defined in ```headers``` to every request made by ZAP.

The workflow should look like this:

```yaml
jobs:
  integration-tests:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    secrets: inherit
    with:
      zap-enabled: true
      zap-cmd-options: '-T 60 -z "-addoninstall jython" --hook "/zap/wrk/tests/zap/hook.py"'
```

1. Install the ```jython``` addon. See [addons](https://www.zaproxy.org/addons/) for a complete list.
2. Set the hook parameter to the ```hook.py``` file inside the repository.
3. The ```hook.py``` should be updated accordingly to the ```add_header_request.py``` path in the repository as well.

## Custom Host Header

The ```add_header_request.py``` file should have the following content:

For more information, see this [ZAP Proxy issue](https://github.com/zaproxy/zaproxy/issues/1318).

```python
# pylint: disable=missing-module-docstring,invalid-name,unused-argument
def sendingRequest(msg, initiator, helper):  # noqa: N802
    """sendingRequest is a name defined and expected by ZAP tool
    Args:
        msg (HttpMessage): all requests/responses sent/received by ZAP
        initiator (int): the component that initiated the request
        helper (HttpSender): returns the HttpSender instance used to send the request
    Returns:
        HttpMessage: returns HttpMessage updated
    """
    msg.setUserObject({"host": "indico.local"})
    return msg


def responseReceived(msg, initiator, helper):  # noqa: N802
    """responseReceived is a name defined and expected by ZAP tool
    Args:
        msg (HttpMessage): all requests/responses sent/received by ZAP
        initiator (int): the component that initiated the request
        helper (HttpSender): returns the HttpSender instance used to send the request
    Returns:
        None
    """
```

### Bonus: Rewrite the URL and log the requests

Same procedure as the previous item but with the ```rewrite_and_log_request.py``` file.

```python
# pylint: disable=missing-module-docstring,invalid-name,unused-argument
import os

log_filename = r'/zap/wrk/requests.log'
target = os.getenv('ZAP_TARGET')

def sendingRequest(msg, initiator, helper):  # noqa: N802
    """sendingRequest is a name defined and expected by ZAP tool
    Args:
        msg (HttpMessage): all requests/responses sent/received by ZAP
        initiator (int): the component that initiated the request
        helper (HttpSender): returns the HttpSender instance used to send the request
    Returns:
        HttpMessage: returns HttpMessage updated
    """
    host = msg.getRequestHeader().getURI().getHost()

    if "indico.local" in host:
        uri = msg.getRequestHeader().getURI()
        uri.setEscapedAuthority(target)
        msg.getRequestHeader().setURI(uri);

    with open(log_filename, 'a') as f:
      f.write(msg.getRequestHeader().toString())
    return msg


def responseReceived(msg, initiator, helper):  # noqa: N802
    """responseReceived is a name defined and expected by ZAP tool
    Args:
        msg (HttpMessage): all requests/responses sent/received by ZAP
        initiator (int): the component that initiated the request
        helper (HttpSender): returns the HttpSender instance used to send the request
    Returns:
        None
    """
```
