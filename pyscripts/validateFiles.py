#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


@dataclass
class ValidationError:
    line: int
    column: int
    message: str
    error_type: str
    category: str  # "xml" or "tei"
    source_line: str = ""


def get_source_line(path: Path, line_number: int) -> str:
    if line_number <= 0:
        return ""

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for current_line, text in enumerate(f, start=1):
                if current_line == line_number:
                    return text.rstrip("\n\r")
    except OSError:
        pass

    return ""


def error_from_log_entry(
    entry: etree._LogEntry,
    path: Path,
    category: str,
) -> ValidationError:
    return ValidationError(
        line=entry.line or 0,
        column=entry.column or 0,
        message=entry.message.strip(),
        error_type=entry.type_name or "ERROR",
        category=category,
        source_line=get_source_line(path, entry.line or 0),
    )


def load_schema(schema_path: Path):
    schema_doc = etree.parse(str(schema_path))

    suffix = schema_path.suffix.lower()

    if suffix == ".rng":
        return etree.RelaxNG(schema_doc)

    if suffix == ".xsd":
        return etree.XMLSchema(schema_doc)

    raise ValueError(f"Unsupported schema format: {schema_path}. " "Use .rng or .xsd.")


def validate_file(
    xml_path: Path,
    schema=None,
) -> list[ValidationError]:

    errors: list[ValidationError] = []

    parser = etree.XMLParser(
        recover=False,
        resolve_entities=False,
        huge_tree=True,
    )

    # XML validation / well-formedness
    try:
        document = etree.parse(str(xml_path), parser)

    except etree.XMLSyntaxError as exc:
        for entry in exc.error_log:
            errors.append(
                error_from_log_entry(
                    entry,
                    xml_path,
                    category="xml",
                )
            )

        # A malformed XML document cannot meaningfully be
        # validated against the TEI schema.
        return errors

    # TEI schema validation
    if schema is not None and not schema.validate(document):
        for entry in schema.error_log:
            errors.append(
                error_from_log_entry(
                    entry,
                    xml_path,
                    category="tei",
                )
            )

    return errors


def error_html(error: ValidationError) -> str:
    line = error.line if error.line else "?"
    column = error.column if error.column else "?"

    source = html.escape(error.source_line)
    message = html.escape(error.message)
    error_type = html.escape(error.error_type)

    if error.category == "xml":
        label = "XML validation error"
    else:
        label = "TEI validation error"

    source_block = ""

    if error.source_line:
        caret_position = max(error.column - 1, 0)
        caret = " " * caret_position + "^"

        source_block = f"""
        <div class="source">
            <div class="source-line">{source}</div>
            <div class="caret">{html.escape(caret)}</div>
        </div>
        """

    return f"""
    <div class="error {error.category}">
        <div class="error-category">
            {label}
        </div>

        <div class="position">
            Line {line}, column {column}
        </div>

        <div class="message">
            <span class="error-type">{error_type}</span>
            {message}
        </div>

        {source_block}
    </div>
    """


def generate_html(
    results: dict[Path, list[ValidationError]],
    directory: Path,
    schema_path: Path | None,
) -> str:

    total_files = len(results)

    all_errors = [error for errors in results.values() for error in errors]

    total_errors = len(all_errors)

    xml_errors = sum(error.category == "xml" for error in all_errors)

    tei_errors = sum(error.category == "tei" for error in all_errors)

    if schema_path:
        validation_description = (
            f"TEI schema: " f"<code>{html.escape(str(schema_path))}</code>"
        )
    else:
        validation_description = "XML well-formedness validation only"

    files_html = []

    for path, errors in sorted(results.items()):
        relative_path = path.relative_to(directory)

        errors_content = "\n".join(error_html(error) for error in errors)

        file_xml_errors = sum(error.category == "xml" for error in errors)

        file_tei_errors = sum(error.category == "tei" for error in errors)

        counts = []

        if file_xml_errors:
            counts.append(
                f'<span class="xml-count">'
                f"{file_xml_errors} XML error"
                f'{"s" if file_xml_errors != 1 else ""}'
                f"</span>"
            )

        if file_tei_errors:
            counts.append(
                f'<span class="tei-count">'
                f"{file_tei_errors} TEI error"
                f'{"s" if file_tei_errors != 1 else ""}'
                f"</span>"
            )

        files_html.append(
            f"""
            <section class="file">
                <h2>{html.escape(str(relative_path))}</h2>

                <div class="error-count">
                    {" · ".join(counts)}
                </div>

                {errors_content}
            </section>
            """
        )

    if not files_html:
        body = """
        <div class="success">
            No validation errors found.
        </div>
        """
    else:
        body = "\n".join(files_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TEI validation report</title>

<style>
    body {{
        max-width: 1200px;
        margin: 2rem auto;
        padding: 0 2rem;
        font-family: system-ui, sans-serif;
        line-height: 1.5;
        color: #222;
    }}

    h1 {{
        margin-bottom: .5rem;
    }}

    .summary {{
        margin-bottom: 2rem;
        padding: 1rem;
        background: #f5f5f5;
        border-radius: .4rem;
    }}

    .summary-row {{
        margin: .2rem 0;
    }}

    .xml-count {{
        color: #b00020;
        font-weight: bold;
    }}

    .tei-count {{
        color: #9a6700;
        font-weight: bold;
    }}

    .file {{
        margin: 2rem 0;
        border: 1px solid #ccc;
        border-radius: .4rem;
        overflow: hidden;
    }}

    .file h2 {{
        margin: 0;
        padding: .8rem 1rem;
        font-family: monospace;
        font-size: 1.1rem;
        background: #eee;
    }}

    .error-count {{
        padding: .5rem 1rem;
    }}

    .error {{
        margin: 1rem;
        padding: 1rem;
    }}

    /*
     * XML syntax / well-formedness errors
     */
    .error.xml {{
        border-left: 5px solid #b00020;
        background: #fff4f4;
    }}

    .error.xml .error-category,
    .error.xml .error-type {{
        color: #b00020;
    }}

    .error.xml .caret {{
        color: #ff6b6b;
    }}

    /*
     * TEI schema validation errors
     */
    .error.tei {{
        border-left: 5px solid #a66a00;
        background: #fff8e6;
    }}

    .error.tei .error-category,
    .error.tei .error-type {{
        color: #8a5700;
    }}

    .error.tei .caret {{
        color: #d18b00;
    }}

    .error-category {{
        font-weight: bold;
        margin-bottom: .25rem;
    }}

    .position {{
        font-family: monospace;
        font-weight: bold;
        margin-bottom: .4rem;
    }}

    .message {{
        margin-bottom: .8rem;
    }}

    .error-type {{
        font-family: monospace;
        font-weight: bold;
        margin-right: .5rem;
    }}

    .source {{
        padding: .7rem;
        overflow-x: auto;
        background: #222;
        color: #eee;
        font-family: monospace;
        white-space: pre;
    }}

    .source-line,
    .caret {{
        white-space: pre;
    }}

    .caret {{
        font-weight: bold;
    }}

    .success {{
        padding: 1rem;
        background: #eef8ee;
        border: 1px solid #8a8;
    }}

    code {{
        font-family: monospace;
    }}
</style>
</head>

<body>

<h1>TEI validation report</h1>

<div class="summary">
    <div class="summary-row">
        {validation_description}
    </div>

    <div class="summary-row">
        Files with errors:
        <strong>{total_files}</strong>
    </div>

    <div class="summary-row">
        XML validation errors:
        <strong class="xml-count">{xml_errors}</strong>
    </div>

    <div class="summary-row">
        TEI validation errors:
        <strong class="tei-count">{tei_errors}</strong>
    </div>

    <div class="summary-row">
        Total errors:
        <strong>{total_errors}</strong>
    </div>
</div>

{body}

</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description=("Validate XML-TEI files and generate an HTML error report.")
    )

    parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing TEI XML files",
    )

    parser.add_argument(
        "-s",
        "--schema",
        type=Path,
        help="TEI Relax NG (.rng) or XSD (.xsd) schema",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("validation-report.html"),
        help="Output HTML file",
    )

    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Search XML files recursively",
    )

    args = parser.parse_args()

    directory = args.directory.resolve()

    if not directory.is_dir():
        parser.error(f"Not a directory: {directory}")

    schema = None

    if args.schema:
        schema_path = args.schema.resolve()

        if not schema_path.is_file():
            parser.error(f"Schema not found: {schema_path}")

        try:
            schema = load_schema(schema_path)

        except (
            etree.XMLSyntaxError,
            etree.RelaxNGParseError,
            etree.XMLSchemaParseError,
            ValueError,
        ) as exc:
            parser.error(f"Cannot load schema: {exc}")

    else:
        schema_path = None

    pattern = "**/*.xml" if args.recursive else "*.xml"

    xml_files = sorted(directory.glob(pattern))

    results: dict[Path, list[ValidationError]] = {}

    for xml_path in xml_files:
        errors = validate_file(xml_path, schema)

        if errors:
            results[xml_path] = errors

    report = generate_html(
        results,
        directory,
        schema_path,
    )

    args.output.write_text(
        report,
        encoding="utf-8",
    )

    all_errors = [error for errors in results.values() for error in errors]

    xml_errors = sum(error.category == "xml" for error in all_errors)

    tei_errors = sum(error.category == "tei" for error in all_errors)

    print(f"Checked: {len(xml_files)} TEI files")
    print(f"Files with errors: {len(results)}")
    print(f"XML errors: {xml_errors}")
    print(f"TEI errors: {tei_errors}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
