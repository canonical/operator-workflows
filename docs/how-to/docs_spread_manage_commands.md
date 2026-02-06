# How to manage commands picked up by the automated Spread testing process

`canonical/operator-workflows/.github/workflows/docs_spread.yaml` runs
`create_spread_task_file.py` over a documentation file
to generate the `task.yaml` needed for a Spread test, and then runs Spread over the resulting file.
This workflow supports Markdown and reStructuredText files.

The Python script has the ability to recognize "hidden commands" needed by
the Spread test but not needed by users, and the script also has the abiity to
recognize "skippable commands" that you don't want Spread to run over. This guide provides
instructions on how to implement these features.

## Add hidden commands for Spread

This workflow allows you to add "hidden commands" that aren't rendered in the file but will
appear in the output `task.yaml` file. The functionality is slightly different for
Markdown and reStructuredText files.

### Markdown files

Use one HTML comment block marked with "SPREAD" to contain all the hidden commands that
you want to include. For example:

```
<!-- SPREAD
echo "Here's a command to run"
echo "Here's another command in the same block"
-->
```

### reStructuredText files

Use reST directives marked with "SPREAD" and "SPREAD END" to enclose all
the hidden commands you want to include. For example:

```
.. SPREAD
.. echo "Here's a command to run"
.. echo "Here's another command in the same block"
.. SPREAD END
```

## Exclude commands for Spread

This workflow also allows you to skip over commands so they don't appear in the
output `task.yaml` file. The overall functionality is the same for both Markdown
and reStructuredText: Enclose the command (or an entire section of text) with blocks
marked with "SPREAD SKIP" and "SPREAD SKIP END".

### Markdown example

````
<!-- SPREAD SKIP -->
Now you can enclose text or entire sections that you want Spread to skip.

```
echo "Here's a command block to skip"
```

You can even skip over multiple command blocks!

```
echo "Here's a second command block to skip"
```

<!-- SPREAD SKIP END -->
````

### reStructuredText example

```
.. SPREAD SKIP
Now you can enclose text or entire sections that you want Spread to skip.

.. code-block::

    echo "Here's a command block to skip"

You can even skip over multiple command blocks!

.. code-block::

    echo "Here's a second command block to skip"

.. SPREAD SKIP END
```