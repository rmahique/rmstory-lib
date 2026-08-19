# rmstory

Translates and recombines stories authored as tagged `<span>`s in
markdown/HTML files:

```html
<span lang="en" id="ch1.greeting">Hello, traveler.</span>
<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor — <span no id="ch1.hero-name">Aldric</span>'s own uncle — was the villain all along.</span>
```

`lang` marks text as translatable, `no` marks it invariant across
stories, and `hist="<story-id>"` marks which story a piece of text
belongs to. A span can nest inside another (here, the invariant name
`ch1.hero-name` inside the translatable `ch1.reveal`) — each is still a
full span in its own right, with its own rules and its own translation.
Translations are stored via
[multilang-lib](https://github.com/rmahique/multilang-lib); a story is a
lightweight ordered-id index layered on top, not a second content store.

This site is usage examples only. For the full CLI reference, all eleven
translation engines (`gemini`, `deepl`, `google-translate`,
`microsoft-translator`, `libretranslate`, `baidu`, `claude-code`,
`ollama`, `deepseek`, `mistral`, `qwen`), and
install/test instructions, see the [GitHub repo](https://github.com/rmahique/rmstory-lib)
— its `README.md` and `requisites.md` (the spec this implementation
follows).

## The same result, two ways

=== "CLI"

    ```bash
    # optional -- rmstory defaults to a filesystem store at ./rmstory/strings
    # with neither variable set; this picks a different path explicitly
    export MULTILANG_DB_BACKEND=filesystem
    export MULTILANG_DB_PATH=./example-strings

    rmstory extract examples/basic_usage.md --stories-dir ./rmstory-stories
    rmstory story examples/basic_usage.md --story villain-arc --stories-dir ./rmstory-stories
    # -> The mayor — Aldric's own uncle — was the villain all along.
    ```

=== "Python"

    ```python
    from rmstory.run import resolve_run
    from rmstory.storage import stories, translations
    from rmstory import render

    conn = translations.connect("filesystem", path="./example-strings")
    spans = resolve_run(["examples/basic_usage.md"])

    for span in spans:
        if span.translatable and span.language:
            translations.store(conn, span.id, span.language, span.content)

    stories.merge("./rmstory-stories", "villain-arc", ["ch1.reveal"])
    ordered_ids = stories.load("./rmstory-stories", "villain-arc")
    text, _missing = render.assemble_story(spans, ordered_ids)
    print(text)
    # -> The mayor — Aldric's own uncle — was the villain all along.
    ```

See **[CLI](cli.md)** for the full extract → translate → story
walkthrough (including the auto-translation `--engine` flag), and
**[Python](python.md)** for the library API — copied verbatim from a
real, runnable example the site's own build checks before publishing.
