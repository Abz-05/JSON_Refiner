# -*- coding: utf-8 -*-
"""
JSON Refiner
=======================================================
Original Concept  : SmartBridge Use-Case 3 (JSON Refiner Advanced)
By       : Abzana V
"""

# ─────────────────────────────────────────────────────────────
# STEP 0  Fix Windows console encoding (print emojis safely)
# ─────────────────────────────────────────────────────────────
import sys, io as _io
for _s in ("stdout", "stderr"):
    _stream = getattr(sys, _s)
    if hasattr(_stream, "buffer") and getattr(_stream, "encoding", "").lower() not in ("utf-8", "utf8"):
        setattr(sys, _s, _io.TextIOWrapper(_stream.buffer, encoding="utf-8", errors="replace"))

# ─────────────────────────────────────────────────────────────
# STEP 1  Imports
# ─────────────────────────────────────────────────────────────
import gradio as gr
import json
import re
import csv
import io
import ast
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import json5
from jsonschema import validate, ValidationError
from enum import Enum

# ============================================================================
# SECTION A  ENUMS & HELPERS
# ============================================================================

class CaseStyle(Enum):
    SNAKE_CASE  = "snake_case"
    CAMEL_CASE  = "camelCase"
    KEBAB_CASE  = "kebab-case"
    PASCAL_CASE = "PascalCase"


# ── KEY FIX: safe lookup that handles camelCase / PascalCase correctly ──────
_STYLE_MAP: Dict[str, CaseStyle] = {
    "snake_case":  CaseStyle.SNAKE_CASE,
    "camelcase":   CaseStyle.CAMEL_CASE,
    "camelCase":   CaseStyle.CAMEL_CASE,
    "kebab-case":  CaseStyle.KEBAB_CASE,
    "kebab_case":  CaseStyle.KEBAB_CASE,
    "pascalcase":  CaseStyle.PASCAL_CASE,
    "PascalCase":  CaseStyle.PASCAL_CASE,
    # upper variants (enum key names)
    "SNAKE_CASE":  CaseStyle.SNAKE_CASE,
    "CAMEL_CASE":  CaseStyle.CAMEL_CASE,
    "KEBAB_CASE":  CaseStyle.KEBAB_CASE,
    "PASCAL_CASE": CaseStyle.PASCAL_CASE,
}

def parse_case_style(raw: str) -> CaseStyle:
    """Convert any case-style string to CaseStyle enum safely."""
    return (
        _STYLE_MAP.get(raw)
        or _STYLE_MAP.get(raw.lower())
        or _STYLE_MAP.get(raw.upper())
        or _STYLE_MAP.get(raw.upper().replace("-", "_"))
        or CaseStyle.SNAKE_CASE          # safe fallback
    )


# ============================================================================
# SECTION B  CORE ENGINE
# ============================================================================

class JSONRefinerCore:
    """Advanced JSON parsing and refinement engine — all methods are static."""

    def __init__(self):
        self.conversion_log         = []
        self.validation_errors      = []
        self.transformation_history = []

    # ── B1. Case converters ──────────────────────────────────────────────

    @staticmethod
    def to_snake_case(text: str) -> str:
        text = re.sub(r"[\s\-]+", "_", text)
        text = re.sub(r"([a-z])([A-Z])", r"\1_\2", text)
        text = re.sub(r"[^a-zA-Z0-9_]", "", text)
        return text.lower()

    @staticmethod
    def to_camel_case(text: str) -> str:
        parts = JSONRefinerCore.to_snake_case(text).split("_")
        return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])

    @staticmethod
    def to_kebab_case(text: str) -> str:
        return JSONRefinerCore.to_snake_case(text).replace("_", "-")

    @staticmethod
    def to_pascal_case(text: str) -> str:
        c = JSONRefinerCore.to_camel_case(text)
        return c[0].upper() + c[1:] if c else ""

    @staticmethod
    def normalize_key(key: str, style: CaseStyle = CaseStyle.SNAKE_CASE) -> str:
        key = key.strip()
        dispatch = {
            CaseStyle.SNAKE_CASE:  JSONRefinerCore.to_snake_case,
            CaseStyle.CAMEL_CASE:  JSONRefinerCore.to_camel_case,
            CaseStyle.KEBAB_CASE:  JSONRefinerCore.to_kebab_case,
            CaseStyle.PASCAL_CASE: JSONRefinerCore.to_pascal_case,
        }
        return dispatch[style](key)

    # ── B2. Type inference ───────────────────────────────────────────────

    @staticmethod
    def infer_type(value: str) -> Any:
        v = value.strip()

        if v.lower() in {"null", "none", "nil", "undefined", "n/a", "na", ""}:
            return None
        if v.lower() in {"true", "yes", "on"}:
            return True
        if v.lower() in {"false", "no", "off"}:
            return False

        # Integer (avoid treating '1'/'0' as bool — handled above)
        try:
            if "." not in v and "e" not in v.lower():
                return int(v)
        except ValueError:
            pass

        # Float
        try:
            return float(v)
        except ValueError:
            pass

        # Percentage
        if v.endswith("%"):
            try:
                return float(v[:-1]) / 100
            except ValueError:
                pass

        # Hex colour
        if re.fullmatch(r"#[0-9a-fA-F]{3,8}", v):
            return v

        # ISO date
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z?)?", v):
            return v

        # JSON literal
        for l, r in (("[", "]"), ("{", "}")):
            if v.startswith(l) and v.endswith(r):
                try:
                    return json.loads(v)
                except Exception:
                    pass

        return v

    # ── B3. Key-value parser ─────────────────────────────────────────────

    @staticmethod
    def parse_key_value_text(
        text: str,
        style: CaseStyle = CaseStyle.SNAKE_CASE,
        allow_multivalue: bool = False,
    ) -> Tuple[Dict, List[str]]:
        result:     Dict       = {}
        errors:     List[str]  = []
        duplicates: List[str]  = []

        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                errors.append(f"Line {lineno}: No colon separator — skipped: '{line}'")
                continue

            try:
                key_raw, _, val_raw = line.partition(":")
                key_raw = key_raw.strip()
                val_raw = val_raw.strip()

                if not key_raw:
                    errors.append(f"Line {lineno}: Empty key — skipped")
                    continue

                nk = JSONRefinerCore.normalize_key(key_raw, style)

                if nk in result:
                    if allow_multivalue:
                        ex = result[nk]
                        if not isinstance(ex, list):
                            result[nk] = [ex]
                        result[nk].append(JSONRefinerCore.infer_type(val_raw))
                    else:
                        duplicates.append(
                            f"Line {lineno}: Duplicate key '{nk}' (orig: '{key_raw}') — skipped"
                        )
                    continue

                result[nk] = JSONRefinerCore.infer_type(val_raw)

            except Exception as exc:
                errors.append(f"Line {lineno}: Parse error — {exc}")

        return result, errors + duplicates

    # ── B4. Validation ───────────────────────────────────────────────────

    @staticmethod
    def validate_json_schema(data: Dict, schema: Dict) -> Tuple[bool, List[str]]:
        try:
            validate(instance=data, schema=schema)
            return True, []
        except ValidationError as exc:
            return False, [str(exc.message)]
        except Exception as exc:
            return False, [f"Schema error: {exc}"]

    @staticmethod
    def check_required_fields(data: Dict, fields: List[str]) -> Tuple[bool, List[str]]:
        missing = [f for f in fields if f not in data]
        if missing:
            return False, [f"Missing required field(s): {', '.join(missing)}"]
        return True, []

    # ── B5. Transformations ──────────────────────────────────────────────

    @staticmethod
    def flatten_json(data: Dict, parent_key: str = "", sep: str = ".") -> Dict:
        items: List = []
        for k, v in data.items():
            nk = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(JSONRefinerCore.flatten_json(v, nk, sep).items())
            else:
                items.append((nk, v))
        return dict(items)

    @staticmethod
    def unflatten_json(data: Dict, sep: str = ".") -> Dict:
        result: Dict = {}
        for key, value in data.items():
            parts = key.split(sep)
            cur = result
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
            cur[parts[-1]] = value
        return result

    @staticmethod
    def merge_json_objects(*objects: Dict) -> Dict:
        result: Dict = {}
        for obj in objects:
            for k, v in obj.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = JSONRefinerCore.merge_json_objects(result[k], v)
                else:
                    result[k] = deepcopy(v)
        return result

    @staticmethod
    def remove_null_values(data: Any, recursive: bool = True) -> Any:
        if isinstance(data, dict):
            return {
                k: JSONRefinerCore.remove_null_values(v, recursive)
                for k, v in data.items() if v is not None
            }
        if isinstance(data, list):
            return [JSONRefinerCore.remove_null_values(i, recursive) for i in data if i is not None]
        return data

    @staticmethod
    def sort_keys_recursive(data: Any) -> Any:
        """Sort all dict keys recursively (alphabetical)."""
        if isinstance(data, dict):
            return {k: JSONRefinerCore.sort_keys_recursive(data[k]) for k in sorted(data)}
        if isinstance(data, list):
            return [JSONRefinerCore.sort_keys_recursive(i) for i in data]
        return data

    # ── B6. Statistics ───────────────────────────────────────────────────

    @staticmethod
    def get_json_stats(data: Dict) -> Dict[str, Any]:
        all_vals = list(data.values())
        type_counts: Dict[str, int] = {}
        for v in all_vals:
            t = type(v).__name__
            type_counts[t] = type_counts.get(t, 0) + 1

        def count_items(obj):
            if isinstance(obj, dict):
                return len(obj), sum(count_items(v)[0] for v in obj.values())
            if isinstance(obj, list):
                return len(obj), sum(count_items(i)[0] if isinstance(i, (dict, list)) else 0 for i in obj)
            return 0, 0

        top, total = count_items(data)
        serialized = json.dumps(data, ensure_ascii=False)
        return {
            "top_level_keys":    top,
            "total_keys":        total,
            "type_breakdown":    type_counts,
            "null_count":        sum(1 for v in all_vals if v is None),
            "nested_objects":    sum(1 for v in all_vals if isinstance(v, dict)),
            "arrays":            sum(1 for v in all_vals if isinstance(v, list)),
            "has_nested_objects":any(isinstance(v, dict) for v in all_vals),
            "has_arrays":        any(isinstance(v, list) for v in all_vals),
            "has_null_values":   any(v is None for v in all_vals),
            "value_types":       list(set(type(v).__name__ for v in all_vals)),
            "byte_size":         len(serialized.encode("utf-8")),
            "char_count":        len(serialized),
            "detected_hex":      [k for k, v in data.items() if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{3,8}", v)],
            "detected_dates":    [k for k, v in data.items() if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", v)],
            "detected_urls":     [k for k, v in data.items() if isinstance(v, str) and v.startswith(("http://", "https://"))],
            "detected_emails":   [k for k, v in data.items() if isinstance(v, str) and re.fullmatch(r"[^@]+@[^@]+\.[^@]+", v)],
        }

    # ── B7. Diff ─────────────────────────────────────────────────────────

    @staticmethod
    def diff_json(a: Dict, b: Dict, path: str = "") -> List[str]:
        """Human-readable diff lines."""
        diffs: List[str] = []
        for k in sorted(set(a) | set(b)):
            full = f"{path}.{k}" if path else k
            if k not in a:
                diffs.append(f"ADDED    [{full}] = {json.dumps(b[k])}")
            elif k not in b:
                diffs.append(f"REMOVED  [{full}] = {json.dumps(a[k])}")
            elif isinstance(a[k], dict) and isinstance(b[k], dict):
                diffs.extend(JSONRefinerCore.diff_json(a[k], b[k], full))
            elif a[k] != b[k]:
                diffs.append(
                    f"CHANGED  [{full}]\n"
                    f"         Before : {json.dumps(a[k])}\n"
                    f"         After  : {json.dumps(b[k])}"
                )
        return diffs

    # ── B8. CSV export ───────────────────────────────────────────────────

    @staticmethod
    def json_to_csv(data: Any) -> str:
        buf = io.StringIO()
        if isinstance(data, list) and all(isinstance(r, dict) for r in data):
            headers = list({k for row in data for k in row})
            writer  = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)
        elif isinstance(data, dict):
            flat   = JSONRefinerCore.flatten_json(data)
            writer = csv.writer(buf)
            writer.writerow(["Key", "Value"])
            for k, v in flat.items():
                writer.writerow([k, v])
        else:
            return "Input must be a JSON array-of-objects or a flat/nested object."
        return buf.getvalue()

    # ── B9. Minify ───────────────────────────────────────────────────────

    @staticmethod
    def minify(data: Dict) -> str:
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


# ============================================================================
# SECTION C  SESSION STATE
# ============================================================================

refiner = JSONRefinerCore()
transformation_history: List[Dict] = []

TEMPLATES = {
    "User Profile": (
        "name: Jane Smith\n"
        "age: 32\n"
        "email: jane@example.com\n"
        "is_active: true\n"
        "role: admin\n"
        "score: 98.7\n"
        'tags: ["vip", "beta-tester"]\n'
        'address: {"city": "Hyderabad", "pin": 500001}'
    ),
    "API Config": (
        "base_url: https://api.example.com\n"
        "timeout: 30\n"
        "retry_count: 3\n"
        "ssl_verify: true\n"
        "api_version: v2\n"
        "rate_limit: 1000"
    ),
    "Product Record": (
        "product_id: PRD-001\n"
        "name: Wireless Headphones\n"
        "price: 2499.00\n"
        "in_stock: true\n"
        "quantity: 150\n"
        "discount_percent: 15.5\n"
        'tags: ["electronics", "audio"]\n'
        "rating: 4.8"
    ),
    "DB Connection": (
        "host: localhost\n"
        "port: 5432\n"
        "database: mydb\n"
        "username: admin\n"
        "ssl_enabled: true\n"
        "pool_size: 10\n"
        "timeout: 5000"
    ),
}


# ============================================================================
# SECTION D  HANDLER FUNCTIONS
# ============================================================================

def load_template(template_name: str) -> str:
    return TEMPLATES.get(template_name, "")


def _fmt_stats(stats: Dict) -> str:
    td = "\n".join(f"  * {t}: {c}" for t, c in stats["type_breakdown"].items())
    detected = []
    for label, fields in [
        ("Hex Colors", stats.get("detected_hex",    [])),
        ("Dates",      stats.get("detected_dates",  [])),
        ("URLs",       stats.get("detected_urls",   [])),
        ("Emails",     stats.get("detected_emails", [])),
    ]:
        if fields:
            detected.append(f"  * {label}: {', '.join(fields)}")
    detected_block = "\n".join(detected) if detected else "  * None"

    return (
        f"**Output Statistics**\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Top-level keys | `{stats['top_level_keys']}` |\n"
        f"| Total keys | `{stats['total_keys']}` |\n"
        f"| Null values | `{stats['null_count']}` |\n"
        f"| Nested objects | `{stats['nested_objects']}` |\n"
        f"| Arrays | `{stats['arrays']}` |\n"
        f"| Byte size | `{stats['byte_size']} B` |\n"
        f"| Value types | `{', '.join(stats['value_types'])}` |\n\n"
        f"**Auto-Detected Fields:**\n{detected_block}"
    )


# ── D1. Core Refine ──────────────────────────────────────────────────────────

def refine_json(
    text_input:   str,
    case_style:   str  = "snake_case",
    remove_nulls: bool = False,
    flatten:      bool = False,
    pretty_print: bool = True,
    sort_keys:    bool = False,
    allow_multi:  bool = False,
) -> Tuple[str, str, str]:
    global transformation_history

    if not text_input.strip():
        return "", "Empty input — please enter some key-value pairs.", ""

    try:
        style  = parse_case_style(case_style)   # BUG-FIX: safe lookup
        parsed, errors = refiner.parse_key_value_text(text_input, style, allow_multi)

        if remove_nulls: parsed = refiner.remove_null_values(parsed)
        if flatten:      parsed = refiner.flatten_json(parsed)
        if sort_keys:    parsed = refiner.sort_keys_recursive(parsed)

        json_out = (
            json.dumps(parsed, indent=2, ensure_ascii=False)
            if pretty_print
            else refiner.minify(parsed)
        )

        stats  = refiner.get_json_stats(parsed)
        status = "Conversion successful!"
        if errors:
            status += f"\n\n**{len(errors)} warning(s):**\n" + "\n".join(f"* {e}" for e in errors[:6])
            if len(errors) > 6:
                status += f"\n* ...and {len(errors)-6} more"

        transformation_history.append({
            "timestamp": datetime.now().isoformat(),
            "input":     text_input,
            "output":    json_out,
            "errors":    errors,
            "stats":     stats,
        })
        return json_out, status, _fmt_stats(stats)

    except Exception as exc:
        return "", f"Error: {exc}", ""


# ── D2. Validate ─────────────────────────────────────────────────────────────

def validate_json(json_text: str, schema_text: str = "", required_fields: str = "") -> Tuple[str, str]:
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}", "JSON parse error"

    results: List[str] = []

    if required_fields.strip():
        fields = [f.strip() for f in required_fields.split(",") if f.strip()]
        ok, errs = refiner.check_required_fields(data, fields)
        results += errs if not ok else ["All required fields present"]

    if schema_text.strip():
        try:
            schema = json.loads(schema_text)
        except json.JSONDecodeError as exc:
            return f"Invalid schema JSON: {exc}", "Schema parse error"
        ok, errs = refiner.validate_json_schema(data, schema)
        results += errs if not ok else ["Schema validation passed"]

    if not results:
        results.append("Valid JSON structure")

    return "\n".join(f"* {r}" for r in results), "Validation complete!"


# ── D3. Case Conversion ───────────────────────────────────────────────────────

def convert_case(json_text: str, target_case: str) -> Tuple[str, str]:
    try:
        data  = json.loads(json_text)
        style = parse_case_style(target_case)   # BUG-FIX: safe lookup

        def recurse(obj):
            if isinstance(obj, dict):
                return {refiner.normalize_key(k, style): recurse(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [recurse(i) for i in obj]
            return obj

        return json.dumps(recurse(data), indent=2, ensure_ascii=False), f"Converted to {target_case}!"
    except Exception as exc:
        return "", f"Error: {exc}"


# ── D4. Merge ─────────────────────────────────────────────────────────────────

def merge_multiple_json(j1: str, j2: str, j3: str = "") -> Tuple[str, str]:
    try:
        objects = []
        for t in [j1, j2, j3]:
            t = t.strip()
            if t:
                objects.append(json.loads(t))
        if not objects:
            return "", "No JSON objects provided"
        merged = refiner.merge_json_objects(*objects)
        return json.dumps(merged, indent=2, ensure_ascii=False), f"Merged {len(objects)} object(s)!"
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON: {exc}"
    except Exception as exc:
        return "", f"Error: {exc}"


# ── D5. Flatten / Unflatten ───────────────────────────────────────────────────

def flatten_json_func(json_text: str) -> Tuple[str, str]:
    try:
        data = json.loads(json_text)
        return json.dumps(refiner.flatten_json(data), indent=2, ensure_ascii=False), "JSON flattened!"
    except Exception as exc:
        return "", f"Error: {exc}"


def unflatten_json_func(json_text: str) -> Tuple[str, str]:
    try:
        data = json.loads(json_text)
        return json.dumps(refiner.unflatten_json(data), indent=2, ensure_ascii=False), "JSON unflattened!"
    except Exception as exc:
        return "", f"Error: {exc}"


# ── D6. JSON Diff ─────────────────────────────────────────────────────────────

def diff_json_func(json_a: str, json_b: str) -> Tuple[str, str]:
    try:
        a = json.loads(json_a)
        b = json.loads(json_b)
        diffs = refiner.diff_json(a, b)
        if not diffs:
            return "No differences — the two JSON objects are identical.", "Identical"
        report = f"Found {len(diffs)} difference(s):\n\n" + "\n\n".join(diffs)
        return report, f"{len(diffs)} difference(s) found"
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}", "Parse error"
    except Exception as exc:
        return f"Error: {exc}", "Error"


# ── D7. CSV Export ────────────────────────────────────────────────────────────

def export_csv(json_text: str) -> Tuple[str, str]:
    try:
        data = json.loads(json_text)
        return refiner.json_to_csv(data), "Converted to CSV!"
    except Exception as exc:
        return "", f"Error: {exc}"


# ── D8. Minify ────────────────────────────────────────────────────────────────

def minify_json(json_text: str) -> Tuple[str, str]:
    try:
        data     = json.loads(json_text)
        minified = refiner.minify(data)
        saved    = len(json_text) - len(minified)
        pct      = round(saved / len(json_text) * 100, 1) if json_text else 0
        return minified, f"Minified! Saved {saved} character(s) ({pct}%)."
    except Exception as exc:
        return "", f"Error: {exc}"


# ── D9. History ───────────────────────────────────────────────────────────────

def download_history() -> str:
    if not transformation_history:
        return "No transformations recorded yet."
    lines = [
        "JSON REFINER ENHANCED  TRANSFORMATION LOG",
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 70, "",
    ]
    for i, item in enumerate(transformation_history, 1):
        lines += [
            f"[#{i}]  {item['timestamp']}",
            f"Input:\n{item['input']}", "",
            f"Output:\n{item['output']}", "",
        ]
        if item["errors"]:
            lines.append(f"Warnings: {'; '.join(item['errors'])}")
        lines += ["-" * 70, ""]
    return "\n".join(lines)


def clear_history() -> str:
    global transformation_history
    transformation_history.clear()
    return "History cleared!"


# ============================================================================
# SECTION E  PREMIUM UI  (Teal / Amber theme — Gradio 6 compatible)
# ============================================================================

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600;700;800&display=swap');

/* ── Design tokens ── */
:root {
  --bg-deep   : #070d14;
  --bg-mid    : #0d1b2a;
  --bg-card   : #111f2f;
  --bg-input  : #0a1825;
  --accent    : #00c9a7;
  --accent2   : #f59e0b;
  --accent3   : #38bdf8;
  --text      : #e2eaf4;
  --muted     : #7a98b8;
  --border    : rgba(0,201,167,.20);
  --radius    : 12px;
  --mono      : 'Space Mono', 'JetBrains Mono', monospace;
  --body      : 'DM Sans', 'Segoe UI', sans-serif;
  --glow      : 0 0 22px rgba(0,201,167,.30);
  --glow-amber: 0 0 18px rgba(245,158,11,.25);
}

/* ── Base ── */
body, .gradio-container {
  background : var(--bg-deep) !important;
  font-family: var(--body) !important;
  color      : var(--text)  !important;
}
.gradio-container { max-width: 1380px !important; padding: 0 24px !important; }

/* ── Banner ── */
.banner-wrap {
  background: linear-gradient(135deg, #061520 0%, #0d2a20 50%, #0d1b2a 100%);
  border    : 1px solid var(--border);
  border-radius: var(--radius);
  padding   : 34px 40px 28px;
  margin-bottom: 18px;
  box-shadow: var(--glow), inset 0 1px 0 rgba(0,201,167,.08);
  position  : relative;
  overflow  : hidden;
}
.banner-wrap::before {
  content: '';
  position: absolute; top:-80px; right:-80px;
  width:320px; height:320px;
  background: radial-gradient(circle, rgba(0,201,167,.12) 0%, transparent 70%);
  pointer-events: none;
}
.banner-wrap::after {
  content: '';
  position: absolute; bottom:-60px; left:-40px;
  width:220px; height:220px;
  background: radial-gradient(circle, rgba(245,158,11,.07) 0%, transparent 70%);
  pointer-events: none;
}
.banner-wrap h1 {
  font-size:2.3rem; font-weight:800; margin:0; letter-spacing:-.5px;
  background: linear-gradient(90deg, #00c9a7, #38bdf8, #f59e0b);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.banner-wrap p {
  color:#7a98b8; margin:8px 0 12px; font-size:.94rem; line-height:1.65; max-width:680px;
}
.banner-badge {
  display:inline-block;
  background: rgba(0,201,167,.15);
  border    : 1px solid rgba(0,201,167,.35);
  color     : #00c9a7;
  font-size :.70rem; font-weight:700; padding:2px 10px;
  border-radius:99px; margin:0 4px 0 0; letter-spacing:.05em;
}
.banner-badge.amber {
  background: rgba(245,158,11,.12);
  border-color: rgba(245,158,11,.35);
  color:#f59e0b;
}

/* ── Tab strip ── */
.tab-nav button {
  font-family:var(--body) !important; font-weight:600 !important;
  font-size:.80rem !important; letter-spacing:.05em !important;
  text-transform:uppercase !important; color:var(--muted) !important;
  background:transparent !important; border-bottom:2px solid transparent !important;
  border-radius:0 !important; padding:10px 16px !important;
  transition:all .2s !important;
}
.tab-nav button.selected, .tab-nav button:hover {
  color: var(--accent) !important;
  border-bottom-color: var(--accent) !important;
}

/* ── Primary button ── */
button.primary, .gr-button-primary {
  background   : linear-gradient(135deg, #00c9a7 0%, #009e83 100%) !important;
  color        : #000 !important;
  font-family  : var(--body) !important;
  font-weight  : 700 !important;
  border       : none !important;
  border-radius: var(--radius) !important;
  letter-spacing: .03em !important;
  box-shadow   : var(--glow) !important;
  transition   : transform .15s, box-shadow .15s !important;
}
button.primary:hover, .gr-button-primary:hover {
  transform : translateY(-2px) !important;
  box-shadow: 0 0 32px rgba(0,201,167,.55) !important;
}

/* ── Secondary ── */
button.secondary, .gr-button-secondary {
  background   : rgba(56,189,248,.12) !important;
  color        : var(--accent3) !important;
  border       : 1px solid rgba(56,189,248,.30) !important;
  border-radius: var(--radius) !important;
  font-weight  : 600 !important;
  transition   : all .2s !important;
}
button.secondary:hover { background: rgba(56,189,248,.22) !important; }

/* ── Stop / danger ── */
button.stop, .gr-button-stop {
  background   : rgba(245,158,11,.13) !important;
  color        : var(--accent2) !important;
  border       : 1px solid rgba(245,158,11,.32) !important;
  border-radius: var(--radius) !important;
  font-weight  : 600 !important;
}

/* ── Textboxes & Code ── */
textarea, .codemirror-wrapper, .code-wrap, input[type="text"] {
  background   : var(--bg-input) !important;
  border       : 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  font-family  : var(--mono) !important;
  font-size    : .81rem !important;
  color        : var(--text) !important;
  transition   : border-color .2s !important;
}
textarea:focus, input[type="text"]:focus {
  border-color: var(--accent) !important;
  box-shadow  : 0 0 0 3px rgba(0,201,167,.14) !important;
  outline: none !important;
}

/* ── Labels ── */
label > span, .block > label > span {
  font-family   : var(--body) !important; font-weight:600 !important;
  font-size     : .78rem !important; letter-spacing:.06em !important;
  text-transform: uppercase !important; color:var(--muted) !important;
}

/* ── Radio ── */
input[type="radio"]:checked + span { color: var(--accent) !important; }

/* ── Checkbox ── */
input[type="checkbox"]:checked { accent-color: var(--accent) !important; }

/* ── Markdown prose tables ── */
.prose table, .gr-markdown table {
  width:100%; border-collapse:collapse; font-size:.85rem;
}
.prose th, .gr-markdown th {
  background   : rgba(0,201,167,.10);
  color        : var(--accent);
  padding      : 7px 12px;
  font-size    : .78rem;
  text-transform: uppercase;
  text-align   : left;
}
.prose td, .gr-markdown td {
  padding: 6px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
}
.prose tr:hover td, .gr-markdown tr:hover td {
  background: rgba(0,201,167,.05);
}

/* ── Scrollbars ── */
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background: var(--bg-mid); }
::-webkit-scrollbar-thumb { background:rgba(0,201,167,.45); border-radius:99px; }
::-webkit-scrollbar-thumb:hover { background:var(--accent); }
"""

HEADER_HTML = """
<div class="banner-wrap">
  <h1>JSON Refiner &mdash; Enhanced Edition</h1>
  <p>Intelligent JSON Processing &amp; Transformation Platform &bull;
     Type Inference &bull; Schema Validation &bull; Case Conversion
     &bull; Flattening &bull; Merge &bull; Diff &bull; CSV Export
     &bull; Minify &bull; History &bull; Quick Templates
  </p>
  <div>
    <span class="banner-badge">Gradio 6</span>
    <span class="banner-badge">Python 3.12+</span>
    <span class="banner-badge amber">11 Features</span>
    <span class="banner-badge amber">Teal / Amber</span>
  </div>
</div>
"""

print("Loading JSON Refiner Enhanced Edition...")

# ── Gradio 6: css goes to launch(), NOT to Blocks() ─────────────────────────
_THEME = gr.themes.Base(
    primary_hue = "teal",
    neutral_hue = "slate",
    font        = [gr.themes.GoogleFont("DM Sans"), "sans-serif"],
)

with gr.Blocks(title="JSON Refiner Enhanced Edition") as demo:

    demo.load(None, js="""
    () => {
        document.body.style.background =
            'radial-gradient(ellipse at 20% 10%, rgba(0,201,167,0.07) 0%, transparent 55%),' +
            'radial-gradient(ellipse at 80% 90%, rgba(245,158,11,0.05) 0%, transparent 50%),' +
            'linear-gradient(180deg, #070d14 0%, #0a1223 100%)';
        document.body.style.minHeight = '100vh';
    }
    """)

    gr.HTML(HEADER_HTML)

    with gr.Tabs():

        # ═══════════════════════════════════════════════════════════════
        # TAB 1  Core Refining  (+ Quick Templates + Sort Keys)
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Core Refining"):
            gr.Markdown("### Parse & Convert Key-Value Text to JSON")

            with gr.Row():
                template_dd  = gr.Dropdown(
                    label="Quick Templates",
                    choices=list(TEMPLATES.keys()),
                    value=None,
                    info="Load a pre-built example",
                )
                load_tpl_btn = gr.Button("Load Template", size="sm", variant="secondary")

            gr.Markdown("---")

            with gr.Row():
                with gr.Column(scale=1):
                    text_input = gr.Textbox(
                        label="Key-Value Input",
                        lines=12,
                        placeholder="name: Alice\nage: 29\nis_active: true\nbalance: 2099.50",
                        value=(
                            "name: Alice Sharma\n"
                            "age: 29\n"
                            "is_active: true\n"
                            "balance: 2099.50\n"
                            "email: alice@example.com\n"
                            'tags: ["developer", "oss"]\n'
                            'meta: {"level": 7}'
                        ),
                    )
                    case_style_radio = gr.Radio(
                        ["snake_case", "camelCase", "kebab-case", "PascalCase"],
                        value="snake_case",
                        label="Key Case Style",
                    )
                    with gr.Row():
                        chk_nulls  = gr.Checkbox(label="Remove Nulls",    value=False)
                        chk_flat   = gr.Checkbox(label="Flatten",         value=False)
                        chk_pretty = gr.Checkbox(label="Pretty Print",    value=True)
                        chk_sort   = gr.Checkbox(label="Sort Keys",       value=False)
                        chk_multi  = gr.Checkbox(label="Allow Multivalue",value=False)
                    btn_refine = gr.Button("Generate JSON", size="lg", variant="primary")

                with gr.Column(scale=1):
                    json_output  = gr.Code(language="json", label="Refined JSON Output", lines=12)
                    status_text  = gr.Markdown()
                    stats_text   = gr.Markdown()

            load_tpl_btn.click(load_template, inputs=[template_dd], outputs=[text_input])
            btn_refine.click(
                refine_json,
                inputs=[text_input, case_style_radio, chk_nulls, chk_flat, chk_pretty, chk_sort, chk_multi],
                outputs=[json_output, status_text, stats_text],
            )

        # ═══════════════════════════════════════════════════════════════
        # TAB 2  Validation
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Validation"):
            gr.Markdown("### Validate JSON Against Schema or Required Fields")
            with gr.Row():
                with gr.Column(scale=1):
                    val_json   = gr.Code(language="json", label="JSON to Validate", lines=10,
                                         value='{"name": "Alice", "age": 29}')
                    val_fields = gr.Textbox(label="Required Fields (comma-separated)",
                                            value="name, age, email")
                with gr.Column(scale=1):
                    val_schema = gr.Code(language="json", label="JSON Schema (optional)", lines=10,
                                         value='{"type":"object","properties":{"name":{"type":"string"}}}')
                    btn_validate = gr.Button("Validate", size="lg", variant="primary")
            val_result = gr.Markdown()
            val_status = gr.Markdown()
            btn_validate.click(validate_json,
                               inputs=[val_json, val_schema, val_fields],
                               outputs=[val_result, val_status])

        # ═══════════════════════════════════════════════════════════════
        # TAB 3  Case Conversion
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Case Conversion"):
            gr.Markdown("### Convert JSON Key Naming Convention")
            with gr.Row():
                with gr.Column(scale=1):
                    cc_input  = gr.Code(language="json", label="Input JSON", lines=10,
                                        value='{"firstName": "Alice", "lastName": "Sharma", "isActive": true}')
                    cc_target = gr.Radio(
                        ["snake_case", "camelCase", "kebab-case", "PascalCase"],
                        value="snake_case", label="Target Case Style",
                    )
                    btn_cc = gr.Button("Convert Keys", size="lg", variant="primary")
                with gr.Column(scale=1):
                    cc_output = gr.Code(language="json", label="Converted JSON", lines=10)
                    cc_status = gr.Markdown()
            btn_cc.click(convert_case, inputs=[cc_input, cc_target], outputs=[cc_output, cc_status])

        # ═══════════════════════════════════════════════════════════════
        # TAB 4  Merge JSON
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Merge JSON"):
            gr.Markdown("### Deep-Merge Multiple JSON Objects")
            with gr.Row():
                with gr.Column(scale=1):
                    j1 = gr.Code(language="json", label="JSON #1", lines=8,
                                 value='{"name": "Alice"}')
                    j2 = gr.Code(language="json", label="JSON #2", lines=8,
                                 value='{"age": 29, "active": true}')
                    j3 = gr.Code(language="json", label="JSON #3 (optional)", lines=8,
                                 value='{"email": "alice@example.com"}')
                    btn_merge = gr.Button("Merge Objects", size="lg", variant="primary")
                with gr.Column(scale=1):
                    merge_output = gr.Code(language="json", label="Merged Result", lines=14)
                    merge_status = gr.Markdown()
            btn_merge.click(merge_multiple_json,
                            inputs=[j1, j2, j3],
                            outputs=[merge_output, merge_status])

        # ═══════════════════════════════════════════════════════════════
        # TAB 5  Flatten / Unflatten
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Flatten / Unflatten"):
            with gr.Tabs():
                with gr.TabItem("Flatten"):
                    gr.Markdown("### Nested JSON to Dot-Notation")
                    with gr.Row():
                        fi = gr.Code(language="json", label="Nested JSON", lines=10,
                                     value='{"user":{"name":"Alice","profile":{"age":29}}}')
                        fb = gr.Button("Flatten", size="lg", variant="primary")
                    fo = gr.Code(language="json", label="Flattened", lines=10)
                    fs = gr.Markdown()
                    fb.click(flatten_json_func, inputs=[fi], outputs=[fo, fs])

                with gr.TabItem("Unflatten"):
                    gr.Markdown("### Dot-Notation to Nested JSON")
                    with gr.Row():
                        ufi = gr.Code(language="json", label="Flattened JSON", lines=10,
                                      value='{"user.name":"Alice","user.profile.age":29}')
                        ufb = gr.Button("Unflatten", size="lg", variant="primary")
                    ufo = gr.Code(language="json", label="Nested Result", lines=10)
                    ufs = gr.Markdown()
                    ufb.click(unflatten_json_func, inputs=[ufi], outputs=[ufo, ufs])

        # ═══════════════════════════════════════════════════════════════
        # TAB 6  JSON Diff
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("JSON Diff"):
            gr.Markdown(
                "### Compare Two JSON Objects\n"
                "Highlights **added**, **removed**, and **changed** keys."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    diff_a = gr.Code(language="json", label="JSON A (Before / Original)", lines=12,
                                     value='{"name":"Alice","age":29,"role":"user","active":true}')
                with gr.Column(scale=1):
                    diff_b = gr.Code(language="json", label="JSON B (After / Modified)", lines=12,
                                     value='{"name":"Alice","age":30,"role":"admin","city":"Hyderabad"}')
            btn_diff   = gr.Button("Run Diff", size="lg", variant="primary")
            diff_out   = gr.Textbox(label="Diff Report", lines=14, interactive=False)
            diff_status= gr.Markdown()
            btn_diff.click(diff_json_func, inputs=[diff_a, diff_b], outputs=[diff_out, diff_status])

        # ═══════════════════════════════════════════════════════════════
        # TAB 7  Export CSV
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Export CSV"):
            gr.Markdown(
                "### Convert JSON to CSV\n"
                "Accepts an **array of objects** or a **flat/nested dict**."
            )
            csv_json = gr.Code(language="json", label="JSON Input", lines=10,
                               value='[{"name":"Alice","age":29},{"name":"Bob","age":34}]')
            btn_csv  = gr.Button("Export to CSV", size="lg", variant="primary")
            csv_out  = gr.Textbox(label="CSV Output", lines=10)
            csv_stat = gr.Markdown()
            btn_csv.click(export_csv, inputs=[csv_json], outputs=[csv_out, csv_stat])

        # ═══════════════════════════════════════════════════════════════
        # TAB 8  Minify
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Minify"):
            gr.Markdown("### Strip Whitespace from JSON\nShows byte/character savings.")
            mn_in  = gr.Code(language="json", label="Pretty JSON", lines=10,
                             value='{\n  "name": "Alice",\n  "age": 29,\n  "active": true\n}')
            btn_mn = gr.Button("Minify", size="lg", variant="primary")
            mn_out = gr.Textbox(label="Minified JSON", lines=4)
            mn_stat= gr.Markdown()
            btn_mn.click(minify_json, inputs=[mn_in], outputs=[mn_out, mn_stat])

        # ═══════════════════════════════════════════════════════════════
        # TAB 9  History
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("History"):
            gr.Markdown("### Transformation Log")
            with gr.Row():
                btn_dl_hist  = gr.Button("Export Log",   size="lg", variant="secondary")
                btn_clr_hist = gr.Button("Clear Log",    size="lg", variant="stop")
            hist_out    = gr.Textbox(label="Transformation History", lines=15)
            hist_status = gr.Markdown()
            btn_dl_hist.click(download_history, outputs=[hist_out])
            btn_clr_hist.click(clear_history,   outputs=[hist_status])

        # ═══════════════════════════════════════════════════════════════
        # TAB 10  Guide
        # ═══════════════════════════════════════════════════════════════
        with gr.TabItem("Guide"):
            gr.Markdown("""
# JSON Refiner Enhanced Edition

## Input Format
Use simple **Key: Value** pairs (one per line):
```
name: Alice Sharma
age: 29
is_active: true
balance: 2099.50
color: #00c9a7
joined: 2024-01-15
tags: ["developer", "oss"]
meta: {"level": 7}
```

## Type Inference Table
| Input Value | Inferred Type |
|---|---|
| `true / yes / on` | Boolean |
| `false / no / off` | Boolean |
| `null / none / nil` | Null |
| `123` | Integer |
| `3.14` | Float |
| `45%` | Float (0.45) |
| `#00c9a7` | String (hex color) |
| `2024-01-15` | String (ISO date) |
| `["a","b"]` | Array |
| `{"k":"v"}` | Object |
| anything else | String |

## Key Case Styles
| Style | Example |
|---|---|
| snake_case | `user_name`, `is_active` |
| camelCase | `userName`, `isActive` |
| kebab-case | `user-name`, `is-active` |
| PascalCase | `UserName`, `IsActive` |

## Features
- **Quick Templates** — Load pre-built examples instantly
- **Sort Keys** — Alphabetically sort all JSON keys (recursive)
- **Allow Multivalue** — Collect duplicate keys into arrays
- **JSON Diff** — Compare two JSONs side-by-side
- **Export CSV** — Export JSON array-of-objects to CSV
- **Minify** — Strip whitespace, shows savings
- **History** — Log all transformations, downloadable

## Tips
* Use `#` at start of a line for comments in Key-Value input
* Combine **Flatten + Remove Nulls** for analytics-ready output
* Use **Sort Keys** for deterministic, version-control-friendly JSON
* Use **JSON Diff** to audit config changes between environments
            """)

    gr.HTML("""
<div style="text-align:center;padding:20px 0 8px;color:#3d5a73;
            font-size:0.73rem;font-family:'Space Mono',monospace">
  JSON Refiner Enhanced Edition &nbsp;&bull;&nbsp;
  Built with Gradio &amp; Python &nbsp;&bull;&nbsp;
  IBM Granite Integration Ready
</div>
""")

print("JSON Refiner Enhanced Edition ready!")

# ── Gradio 6: css parameter belongs here, NOT in Blocks() constructor ────────
demo.launch(
    share      = True,
    show_error = True,
    css        = CUSTOM_CSS,
    theme      = _THEME,
)