# Sample file to test the automated Spread test workflow

Hello this is a tutorial for testing purposes only.

## Requirements

In this section, any command blocks should be ignored.

```
echo "Hello I should be ignored"
```

This command block should also be ignored

```
echo "Hello I should also be ignored"
```

## Commands that should be picked up

Once you're outside of the Requirements section, command blocks should be picked up.

```
echo "First command block that should be picked up"
```

Another command block:

```
echo "Second command block"
```

Command blocks formatted as admonitions or terminal output should be ignored.

```{note}
echo "A note admonition that should not be picked up"
```

```{terminal}
echo "A terminal block that should not be picked up"
```

We can also grab hidden command blocks using HTML comment syntax.

<!-- SPREAD 
echo "Hidden command block that should be picked up"
-->

