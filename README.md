# JSON Refiner — Enhanced Edition

> **Intelligent JSON Processing & Transformation Platform**  
> Built with Python + Gradio | Production-Grade | 11 Features

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Quick Start](#quick-start)
4. [Installation](#installation)
5. [Running the App](#running-the-app)
6. [Feature Guide](#feature-guide)
   - [Core Refining](#1-core-refining)
   - [Validation](#2-validation)
   - [Case Conversion](#3-case-conversion)
   - [Merge JSON](#4-merge-json)
   - [Flatten / Unflatten](#5-flatten--unflatten)
   - [JSON Diff](#6-json-diff)
   - [Export CSV](#7-export-csv)
   - [Minify](#8-minify)
   - [History](#9-history)
   - [Quick Templates](#10-quick-templates)
7. [Type Inference Table](#type-inference-table)
8. [Case Style Reference](#case-style-reference)
9. [Project Architecture](#project-architecture)
10. [Use Case Scenarios](#use-case-scenarios)
11. [Requirements](#requirements)
12. [Troubleshooting](#troubleshooting)
13. [Future Enhancements](#future-enhancements)

---

## Overview

**JSON Refiner** is an intelligent, web-based JSON processing platform that transforms raw key-value text into clean, typed, and validated JSON — with a single click.

It was built as part of the **SmartBridge Use-Case 3** project and enhanced to production-grade by **Abzana V**, featuring an interactive Gradio interface with a premium Teal/Amber dark theme, automatic type inference, schema validation, case normalization, structural transformations, and comprehensive history tracking.

```
name: Alice Sharma
age: 29
is_active: true
balance: 2099.50
email: alice@example.com
tags: ["developer", "oss"]
```
One click:
```json
{
  "name": "Alice Sharma",
  "age": 29,
  "isActive": true,
  "balance": 2099.5,
  "email": "alice@example.com",
  "tags": ["developer", "oss"]
}
```

---

## Features

| # | Feature | Description |
|---|---|---|
| 1 | **Core Refining** | Convert key-value text to typed JSON with automatic type inference |
| 2 | **Validation** | Check required fields and validate against JSON Schema (Draft 7) |
| 3 | **Case Conversion** | Convert JSON keys between snake_case, camelCase, kebab-case, PascalCase |
| 4 | **Merge JSON** | Deep-merge up to 3 JSON objects with conflict resolution |
| 5 | **Flatten / Unflatten** | Convert nested JSON to dot-notation and back |
| 6 | **JSON Diff** | Compare two JSON objects — see added, removed, and changed keys |
| 7 | **Export CSV** | Export JSON arrays or dicts directly to CSV format |
| 8 | **Minify** | Strip whitespace from JSON, shows byte/character savings |
| 9 | **History** | Log and export all transformations from the current session |
| 10 | **Quick Templates** | Pre-built examples: User Profile, API Config, Product Record, DB Connection |
| 11 | **Sort Keys** | Recursively alphabetically sort all JSON keys |

---

## Quick Start

```powershell
# 1. Install dependencies
python -m pip install gradio json5 jsonschema python-dotenv pydantic deepdiff

# 2. Run the app
$env:PYTHONIOENCODING="utf-8"
python "granite_3_3_2b_instruct (1).py"

# 3. Open in your browser
#    Local:  http://127.0.0.1:7860
#    Public: The terminal will print a public gradio.live URL
```

---

## Installation

### Prerequisites

| Requirement | Minimum Version |
|---|---|
| Python | 3.8+ (3.12+ recommended) |
| pip | Latest |
| Internet | Required for Google Fonts and Gradio share link |

### Install Dependencies

```powershell
python -m pip install gradio json5 jsonschema python-dotenv pydantic deepdiff transformers
```

Or using the `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

### requirements.txt

```
gradio>=6.0.0
json5>=0.9.6
jsonschema>=4.17.0
python-dotenv>=0.19.0
pydantic>=2.0.0
deepdiff>=6.0.0
transformers>=4.0.0
```

> **Note for Windows users:** Always run with `$env:PYTHONIOENCODING="utf-8"` before launching to ensure emoji and Unicode characters render correctly in the terminal.

---

## Running the App

### Windows (PowerShell)

```powershell
$env:PYTHONIOENCODING="utf-8"
python "granite_3_3_2b_instruct (1).py"
```

### After Launch

The terminal will display:

```
Loading JSON Refiner Enhanced Edition...
JSON Refiner Enhanced Edition ready!
* Running on local URL:  http://127.0.0.1:7860
* Running on public URL: https://xxxxxxxxxxxxxxxx.gradio.live
```

- **Local URL** — available only on your machine
- **Public URL** — shareable with anyone, expires in 1 week

To stop the app, press `Ctrl + C` in the terminal.

---

## Feature Guide

### 1. Core Refining

The main feature. Paste any key-value text and get clean, typed JSON output.

**Input format:**
```
key: value
```
One pair per line. Use `#` to write comments.

**Options:**

| Option | Description |
|---|---|
| Key Case Style | Choose snake_case / camelCase / kebab-case / PascalCase for all keys |
| Remove Nulls | Strip keys whose value is null/None |
| Flatten | Convert nested values to dot-notation flat structure |
| Pretty Print | Format output with 2-space indentation (off = minified) |
| Sort Keys | Alphabetically sort all keys in the output |
| Allow Multivalue | When duplicate keys exist, collect values into an array |

**Example:**
```
name: Alice
age: 29
is_active: yes
balance: 1500.50
joined: 2024-01-15
```
Output (camelCase):
```json
{
  "name": "Alice",
  "age": 29,
  "isActive": true,
  "balance": 1500.5,
  "joined": "2024-01-15"
}
```

---

### 2. Validation

Validate any JSON string against:
- A **comma-separated list of required fields**
- A **JSON Schema** (Draft 7 standard)

**Example required fields check:**
```
Input fields: name, age, email
Result: Missing required field(s): email
```

**Example schema:**
```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "age":  { "type": "integer", "minimum": 0 }
  },
  "required": ["name", "age"]
}
```

---

### 3. Case Conversion

Re-key any existing JSON object to a different naming convention. Works recursively on nested objects and arrays.

**Example input:**
```json
{ "firstName": "Alice", "lastName": "Sharma", "isActive": true }
```

**snake_case output:**
```json
{ "first_name": "Alice", "last_name": "Sharma", "is_active": true }
```

**PascalCase output:**
```json
{ "FirstName": "Alice", "LastName": "Sharma", "IsActive": true }
```

---

### 4. Merge JSON

Deep-merge up to **3 JSON objects**. When the same key exists in multiple objects, the **last value wins** (unless both values are objects, in which case they are recursively merged).

**Example:**
```
JSON #1: {"user": {"name": "Alice"}}
JSON #2: {"user": {"age": 29}, "active": true}
```
**Result:**
```json
{
  "user": { "name": "Alice", "age": 29 },
  "active": true
}
```

---

### 5. Flatten / Unflatten

**Flatten** — convert a nested JSON object into a single-level object using dot-notation keys:
```json
Input:  { "user": { "name": "Alice", "age": 29 } }
Output: { "user.name": "Alice", "user.age": 29 }
```

**Unflatten** — reverse the operation:
```json
Input:  { "user.name": "Alice", "user.age": 29 }
Output: { "user": { "name": "Alice", "age": 29 } }
```

---

### 6. JSON Diff

Compare two JSON objects and get a human-readable report of every change.

**Report format:**
```
Found 3 difference(s):

ADDED    [email] = "alice@example.com"
REMOVED  [active]
CHANGED  [age]
         Before : 29
         After  : 30
```

---

### 7. Export CSV

Convert JSON data directly to CSV format:
- **Array of objects** — headers are all unique keys; each object becomes a row
- **Flat or nested dict** — auto-flattens first, then outputs Key / Value columns

---

### 8. Minify

Strip all formatting whitespace from a JSON string. Displays the exact number of characters and bytes saved.

```
Before: 52 chars
After:  31 chars
Saved:  21 characters (40.4%)
```

---

### 9. History

Every use of Core Refining is automatically logged. From the History tab you can:
- **Export Log** — view the full transformation history as a text report
- **Clear Log** — reset the session history

---

### 10. Quick Templates

Load pre-built example inputs into the Core Refining tab to explore the tool instantly:

| Template | Contents |
|---|---|
| User Profile | name, age, email, role, score, tags, address |
| API Config | base_url, timeout, retry_count, ssl_verify, api_version |
| Product Record | product_id, name, price, in_stock, quantity, rating |
| DB Connection | host, port, database, username, ssl_enabled, pool_size |

---

## Type Inference Table

The engine automatically detects and converts values to the correct JSON type:

| Input String | Inferred JSON Type | Example |
|---|---|---|
| `true`, `yes`, `on` | boolean (true) | `active: yes` → `"active": true` |
| `false`, `no`, `off` | boolean (false) | `active: no` → `"active": false` |
| `null`, `none`, `nil`, `undefined`, `n/a` | null | `score: null` → `"score": null` |
| Pure integer string | integer | `age: 29` → `"age": 29` |
| Decimal number | float | `rate: 3.14` → `"rate": 3.14` |
| Ends with `%` | float (divided by 100) | `tax: 18%` → `"tax": 0.18` |
| Starts with `#` (3–8 hex chars) | string (hex color) | `color: #00c9a7` |
| Matches ISO 8601 date | string (date) | `joined: 2024-01-15` |
| Valid JSON array `[...]` | array | `tags: ["a","b"]` |
| Valid JSON object `{...}` | object | `meta: {"k":1}` |
| Anything else | string | `city: Chennai` |

---

## Case Style Reference

| Style | Rule | Example Output |
|---|---|---|
| **snake_case** | All lowercase, words separated by `_` | `user_name`, `is_active` |
| **camelCase** | First word lowercase, subsequent words capitalized | `userName`, `isActive` |
| **kebab-case** | All lowercase, words separated by `-` | `user-name`, `is-active` |
| **PascalCase** | Every word capitalized, no separator | `UserName`, `IsActive` |

The normalizer handles any input convention — `firstName`, `first_name`, `First Name`, `FIRST-NAME` — all correctly converted.

---

## Project Architecture

```
granite_3_3_2b_instruct (1).py
│
├── Section A  ─  Enums & Helpers
│     └── CaseStyle enum, parse_case_style() safe lookup
│
├── Section B  ─  JSONRefinerCore  (engine class)
│     ├── B1.  Case converters     (snake, camel, kebab, pascal)
│     ├── B2.  Type inference
│     ├── B3.  Key-value parser
│     ├── B4.  JSON Schema validation
│     ├── B5.  Transformations     (flatten, unflatten, merge, remove nulls, sort)
│     ├── B6.  Statistics
│     ├── B7.  JSON Diff
│     ├── B8.  CSV export
│     └── B9.  Minify
│
├── Section C  ─  Session State   (history list, templates dict)
│
├── Section D  ─  Handler Functions  (wired to Gradio buttons)
│     └── refine_json, validate_json, convert_case,
│         merge_multiple_json, flatten_json_func, unflatten_json_func,
│         diff_json_func, export_csv, minify_json,
│         download_history, clear_history, load_template
│
└── Section E  ─  Gradio UI
      ├── CUSTOM_CSS    (Teal/Amber dark theme, DM Sans + Space Mono)
      ├── HEADER_HTML   (animated gradient banner)
      └── 10 Tabs       (wired to Section D handlers)
```

---

## Use Case Scenarios

### Scenario 1: Data Migration from CSV to JSON
A data analyst converts flat CSV rows with mixed types into structured JSON. The engine auto-detects types, applies consistent naming, and validates against a schema before database migration.

### Scenario 2: API Response Normalization
A backend developer standardizes keys from multiple third-party APIs (using different naming conventions) into a single consistent format, merges responses, removes nulls, and validates against a master schema.

### Scenario 3: Configuration File Management
A DevOps engineer maintains human-readable config files in Key: Value format and converts them to JSON for infrastructure-as-code tools, with required-field validation to catch errors early.

### Scenario 4: Flattening for Analytics
An analytics team flattens deeply nested JSON structures to dot-notation for spreadsheet analysis, uses CSV export, and can unflatten back when needed.

### Scenario 5: Schema-Based Quality Assurance
A QA team validates incoming JSON against company JSON Schemas and uses the Diff engine to audit changes between environment configurations.

---

## Requirements

### Software

| Package | Purpose |
|---|---|
| `gradio >= 6.0` | Web UI framework |
| `json5` | Flexible JSON parsing |
| `jsonschema` | JSON Schema validation (Draft 7) |
| `python-dotenv` | Environment variable management |
| `pydantic` | Data validation |
| `deepdiff` | Deep comparison utilities |
| `transformers` | IBM Granite model integration (optional) |

### Hardware

| Component | Minimum |
|---|---|
| Processor | Any modern CPU |
| RAM | 2 GB (local) |
| Storage | 500 MB |
| Display | 1024 x 768 |

---

## Troubleshooting

### ModuleNotFoundError: No module named 'gradio'
```powershell
python -m pip install gradio json5 jsonschema python-dotenv pydantic
```

### UnicodeEncodeError (emojis in terminal on Windows)
```powershell
$env:PYTHONIOENCODING="utf-8"
python "granite_3_3_2b_instruct (1).py"
```

### TypeError: Blocks.launch() got an unexpected keyword argument 'show_api'
The script requires **Gradio 6+**. Upgrade:
```powershell
python -m pip install --upgrade gradio
```

### camelCase or PascalCase produces an error
This was a bug in earlier versions (fixed). The current version uses the `parse_case_style()` safe lookup that handles all four styles correctly without a `KeyError`.

### Port already in use
```powershell
Get-Process -Name python* | Stop-Process -Force
```

---

## Future Enhancements

- Custom transformation rules (user-defined regex pipelines)
- Batch file processing (upload multiple JSON files)
- Integration with IBM Granite LLM for AI-powered JSON generation
- JSONPath query engine (`user.scores[0]`)
- Data anonymization / PII masking
- Cloud storage integration (upload to S3 / GCS)
- REST API endpoint generation from JSON schema
- Machine learning-based type inference for ambiguous values
- Custom case style definitions
- Import directly from CSV / YAML / TOML

---

## Author

**Abzana V**
SmartBridge Use-Case 3 — JSON Refiner Advanced
Enhancement Level: Production-Grade | Teal/Amber Theme | 11 Features

---

## License

This project was developed as part of an academic/training use case under SmartBridge.
For educational and non-commercial use.
