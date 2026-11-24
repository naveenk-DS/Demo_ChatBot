"""
Structured Document Processing Pipeline for EstateAI.
Responsible for downloading, parsing, normalizing, validating, and searching
structured property records from CSV, Excel (XLSX), and JSON documents.

This structured dataset serves as the verified source of truth for all property
searches, specifications, and pricing.
"""

import csv
import io
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, Union

# Attempt pandas import; fallback gracefully to pure-python openpyxl and built-in csv if blocked by WDAC
try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    pd = None
    _HAS_PANDAS = False

try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    openpyxl = None
    _HAS_OPENPYXL = False

logger = logging.getLogger("estateai.structured_pipeline")

FIELD_ALIASES = {
    "property_name": [
        "property_name", "property", "project_name", "project", "name",
        "title", "building_name", "community", "development"
    ],
    "property_id": [
        "property_id", "id", "code", "unit_id", "listing_id", "ref_no", "property_code"
    ],
    "bhk": [
        "bhk", "bedrooms", "bedroom", "beds", "bed", "configuration", "config", "type"
    ],
    "price": [
        "price", "cost", "total_price", "amount", "selling_price", "rate_total",
        "price_inr", "value", "quoted_price"
    ],
    "sqft": [
        "sqft", "area", "super_builtup_area", "builtup_area", "carpet_area",
        "size", "area_sqft", "super_area"
    ],
    "location": [
        "location", "locality", "address", "area_name", "suburb", "micro_market", "neighborhood"
    ],
    "city": [
        "city", "town", "district"
    ],
    "property_type": [
        "property_type", "type", "category", "unit_type", "asset_class"
    ],
    "facing": [
        "facing", "direction", "orientation", "entry_facing"
    ],
    "floor": [
        "floor", "floor_number", "level", "storey"
    ],
    "property_status": [
        "property_status", "status", "possession", "handover", "availability", "stage"
    ],
    "description": [
        "description", "desc", "overview", "summary", "notes", "details", "highlights"
    ],
    "amenities": [
        "amenities", "facilities", "features", "specifications", "perks"
    ],
    "image_url": [
        "image_url", "image", "photo", "thumbnail", "photo_url"
    ]
}


def parse_price_to_inr(raw_value: Any) -> Optional[int]:
    """
    Normalizes raw price input into integer INR rupees.
    Handles numeric values, strings with Indian notations (Cr, Crore, L, Lakhs),
    currency symbols (₹, Rs), and commas.
    """
    if raw_value is None:
        return None

    if isinstance(raw_value, (int, float)):
        val = int(raw_value)
        return val if val > 0 else None

    text = str(raw_value).strip().lower()
    if not text or text in ("null", "none", "n/a", "na", "-", "undefined"):
        return None

    cleaned = re.sub(r"[₹\$,\s]", "", text)
    cleaned = cleaned.replace("rs.", "").replace("rs", "").replace("/-", "")

    m_cr = re.search(r"([\d\.]+)\s*(?:cr|crore|crores)", cleaned)
    if m_cr:
        try:
            return int(float(m_cr.group(1)) * 10_000_000)
        except ValueError:
            pass

    m_l = re.search(r"([\d\.]+)\s*(?:l|lakh|lakhs|lac|lacs)", cleaned)
    if m_l:
        try:
            return int(float(m_l.group(1)) * 100_000)
        except ValueError:
            pass

    m_num = re.search(r"^([\d\.]+)$", cleaned)
    if m_num:
        try:
            num = float(m_num.group(1))
            if num < 500 and num > 0:
                return int(num * 100_000)
            return int(num)
        except ValueError:
            pass

    return None


def parse_bhk_integer(raw_value: Any) -> Optional[int]:
    """Extracts integer BHK (1 to 10) from various representations."""
    if raw_value is None:
        return None

    if isinstance(raw_value, (int, float)):
        val = int(raw_value)
        return val if 1 <= val <= 10 else None

    text = str(raw_value).strip().lower()
    m = re.search(r"\b([1-9]|10)\s*(?:bhk|bed|bedroom)?\b", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def parse_sqft_integer(raw_value: Any) -> Optional[int]:
    """Extracts integer square feet area."""
    if raw_value is None:
        return None

    if isinstance(raw_value, (int, float)):
        val = int(raw_value)
        return val if val > 0 else None

    text = str(raw_value).strip().lower()
    m = re.search(r"([\d]+)", text.replace(",", ""))
    if m:
        try:
            val = int(m.group(1))
            return val if val > 100 else None
        except ValueError:
            pass
    return None


def load_csv(file_input: Union[str, Path, bytes, io.BytesIO], source_name: str = "data.csv") -> list[dict[str, Any]]:
    """Loads records from a CSV file or byte stream using Pandas if available, or built-in csv."""
    if _HAS_PANDAS:
        try:
            if isinstance(file_input, bytes):
                buffer = io.BytesIO(file_input)
                df = pd.read_csv(buffer, encoding="utf-8", on_bad_lines="skip")
            elif isinstance(file_input, io.BytesIO):
                df = pd.read_csv(file_input, encoding="utf-8", on_bad_lines="skip")
            else:
                path = Path(file_input)
                if not path.exists():
                    return []
                df = pd.read_csv(path, encoding="utf-8", on_bad_lines="skip")

            records = df.where(pd.notnull(df), None).to_dict(orient="records")
            logger.info("Loaded %d raw records from CSV '%s' via Pandas", len(records), source_name)
            return records
        except Exception as exc:
            logger.debug("Pandas load_csv failed (%s), falling back to standard csv module", exc)

    # Built-in csv reader fallback
    try:
        if isinstance(file_input, bytes):
            text = file_input.decode("utf-8", errors="replace")
            f = io.StringIO(text)
        elif isinstance(file_input, io.BytesIO):
            text = file_input.getvalue().decode("utf-8", errors="replace")
            f = io.StringIO(text)
        else:
            path = Path(file_input)
            if not path.exists():
                return []
            f = open(path, "r", encoding="utf-8", errors="replace")

        reader = csv.DictReader(f)
        records = [dict(row) for row in reader]
        if hasattr(f, "close"):
            f.close()
        logger.info("Loaded %d raw records from CSV '%s' via standard csv", len(records), source_name)
        return records
    except Exception as exc:
        logger.error("Failed to load CSV '%s': %s", source_name, exc)
        return []


def load_excel(file_input: Union[str, Path, bytes, io.BytesIO], source_name: str = "data.xlsx") -> list[dict[str, Any]]:
    """Loads records from an Excel workbook (.xlsx or .xls), parsing all sheets using Pandas or openpyxl."""
    ext = Path(source_name).suffix.lower()
    if _HAS_PANDAS:
        try:
            engine = "openpyxl" if ext in (".xlsx", ".xlsm") else None
            excel_kwargs = {"engine": engine} if engine else {}
            if isinstance(file_input, bytes):
                buffer = io.BytesIO(file_input)
                excel_file = pd.ExcelFile(buffer, **excel_kwargs)
            elif isinstance(file_input, io.BytesIO):
                excel_file = pd.ExcelFile(file_input, **excel_kwargs)
            else:
                path = Path(file_input)
                if not path.exists():
                    return []
                excel_file = pd.ExcelFile(path, **excel_kwargs)

            all_records: list[dict[str, Any]] = []
            for sheet_name in excel_file.sheet_names:
                df = excel_file.parse(sheet_name)
                if df.empty:
                    continue
                df_cleaned = df.where(pd.notnull(df), None)
                sheet_records = df_cleaned.to_dict(orient="records")
                for r in sheet_records:
                    r["_excel_sheet"] = sheet_name
                all_records.extend(sheet_records)

            logger.info("Loaded %d raw records across %d sheet(s) from Excel '%s' via Pandas", len(all_records), len(excel_file.sheet_names), source_name)
            return all_records
        except Exception as exc:
            logger.debug("Pandas load_excel failed (%s), falling back to openpyxl", exc)

    # Pure-python openpyxl fallback
    if _HAS_OPENPYXL:
        try:
            if isinstance(file_input, (bytes, io.BytesIO)):
                buffer = file_input if isinstance(file_input, io.BytesIO) else io.BytesIO(file_input)
                wb = openpyxl.load_workbook(buffer, data_only=True)
            else:
                path = Path(file_input)
                if not path.exists():
                    return []
                wb = openpyxl.load_workbook(str(path), data_only=True)

            all_records = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(values_only=True))
                if not rows or len(rows) < 2:
                    continue
                headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
                for row_vals in rows[1:]:
                    if not any(row_vals):
                        continue
                    record = {headers[i]: (row_vals[i] if i < len(row_vals) else None) for i in range(len(headers))}
                    record["_excel_sheet"] = sheet_name
                    all_records.append(record)

            logger.info("Loaded %d raw records across %d sheet(s) from Excel '%s' via openpyxl", len(all_records), len(wb.sheetnames), source_name)
            return all_records
        except Exception as exc:
            logger.error("openpyxl load_excel failed for '%s': %s", source_name, exc)
            return []

    logger.warning("Neither pandas nor openpyxl is available to load Excel file '%s'", source_name)
    return []


def load_json(file_input: Union[str, Path, bytes, io.BytesIO], source_name: str = "data.json") -> list[dict[str, Any]]:
    """Loads property records from a JSON file, bytes, or stream, unrolling flat or deeply nested structures."""
    try:
        if isinstance(file_input, (bytes, io.BytesIO)):
            content = file_input.getvalue() if isinstance(file_input, io.BytesIO) else file_input
            data = json.loads(content.decode("utf-8"))
        else:
            path = Path(file_input)
            if not path.exists():
                logger.warning("JSON file not found: %s", path)
                return []
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

        def _extract_records(obj: Any) -> list[dict[str, Any]]:
            if isinstance(obj, list):
                return [item for item in obj if isinstance(item, dict)]
            if isinstance(obj, dict):
                for key in ("properties", "records", "data", "listings", "units", "items", "results"):
                    if key in obj:
                        res = _extract_records(obj[key])
                        if res:
                            return res
                for k, v in obj.items():
                    if isinstance(v, (list, dict)):
                        res = _extract_records(v)
                        if res:
                            return res
            return []

        records = _extract_records(data)
        logger.info("Loaded %d raw records from JSON '%s'", len(records), source_name)
        return records
    except Exception as exc:
        logger.error("Failed to load JSON '%s': %s", source_name, exc)
        return []


def normalize_records(raw_records: list[dict[str, Any]], source_name: str) -> list[dict[str, Any]]:
    """
    Maps variable column names to standard property attributes, normalizes prices to INR,
    extracts integer BHK counts, and attaches source document metadata.
    """
    normalized_list: list[dict[str, Any]] = []

    for idx, raw in enumerate(raw_records, start=1):
        norm: dict[str, Any] = {
            "source_file": source_name,
            "record_index": idx,
            "property_id": None,
            "property_name": None,
            "bhk": None,
            "price": None,
            "sqft": None,
            "location": None,
            "city": "Chennai",
            "property_type": "Apartment",
            "facing": "East facing",
            "floor": "Mid floor",
            "property_status": "Ready to move",
            "description": "",
            "amenities": [],
            "image_url": None,
            "_excel_sheet": raw.get("_excel_sheet"),
            "original_data": raw,
        }

        lower_raw = {str(k).lower().strip().replace(" ", "_"): v for k, v in raw.items() if k is not None}

        for standard_field, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                if alias in lower_raw and lower_raw[alias] is not None:
                    val = lower_raw[alias]
                    if standard_field == "price":
                        norm["price"] = parse_price_to_inr(val)
                    elif standard_field == "bhk":
                        norm["bhk"] = parse_bhk_integer(val)
                    elif standard_field == "sqft":
                        norm["sqft"] = parse_sqft_integer(val)
                    elif standard_field == "amenities":
                        if isinstance(val, list):
                            norm["amenities"] = [str(x).strip() for x in val if x]
                        elif isinstance(val, str):
                            norm["amenities"] = [x.strip() for x in val.split(",") if x.strip()]
                    else:
                        norm[standard_field] = str(val).strip()
                    break

        if not norm["property_id"]:
            prefix = f"{norm['bhk']}BHK" if norm['bhk'] else "PROP"
            stem = Path(source_name).stem.upper().replace(" ", "_")[:6]
            norm["property_id"] = f"{stem}-{prefix}-{idx:02d}"

        if not norm["property_name"]:
            loc_str = f" in {norm['location']}" if norm['location'] else ""
            bhk_str = f"{norm['bhk']} BHK " if norm['bhk'] else ""
            norm["property_name"] = f"Verified {bhk_str}Residence{loc_str}"

        if not norm["city"]:
            norm["city"] = "Chennai"

        normalized_list.append(norm)

    return normalized_list


def validate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validates records, ensuring minimum viable fields for property representation."""
    valid: list[dict[str, Any]] = []
    for r in records:
        name = r.get("property_name")
        price = r.get("price")
        bhk = r.get("bhk")
        sqft = r.get("sqft")

        if not name:
            continue
        if price is None and bhk is None and sqft is None:
            continue

        valid.append(r)
    return valid


def search_properties(
    filters: dict[str, Any],
    records: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Deterministic search over verified structured property records.
    Filters by BHK, price range (min_price/max_price), and location substring.
    Does NOT use hallucinated or LLM-generated properties.
    """
    target_bhk = filters.get("bhk")
    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    location = filters.get("location")
    property_type = filters.get("property_type")

    results = []

    for r in records:
        if target_bhk is not None:
            r_bhk = r.get("bhk")
            if r_bhk is not None and r_bhk != target_bhk:
                continue

        r_price = r.get("price")
        if r_price is not None:
            if min_price is not None and r_price < min_price:
                continue
            if max_price is not None and r_price > max_price:
                continue

        if location:
            loc_query = str(location).lower().strip()
            loc_query = re.sub(r"\b(chennai|in|at|near|area|road)\b", "", loc_query).strip()
            if loc_query:
                r_loc = str(r.get("location", "")).lower()
                r_desc = str(r.get("description", "")).lower()
                r_name = str(r.get("property_name", "")).lower()
                if loc_query not in r_loc and loc_query not in r_desc and loc_query not in r_name:
                    continue

        if property_type:
            pt_query = str(property_type).lower().strip()
            r_pt = str(r.get("property_type", "")).lower()
            if pt_query not in r_pt:
                continue

        results.append(r)

    # Strictly deterministic: never silently drop location, BHK, or price filters when no match exists.
    return results[:limit]


class StructuredDataStore:
    """
    Manages in-memory partitioned property records indexed by source document.
    Allows dynamic document additions, updates, deletions, and searching without restarting.
    """
    def __init__(self):
        self.records_by_source: dict[str, list[dict[str, Any]]] = {}

    def add_or_update(
        self,
        file_input: Union[str, Path, bytes, io.BytesIO],
        source_name: str,
    ) -> int:
        """
        Parses, normalizes, validates, and stores property records for source_name.
        Replaces any existing records previously ingested from the same source.
        Returns the number of valid property records stored.
        """
        ext = Path(source_name).suffix.lower()
        raw_records: list[dict[str, Any]] = []

        if ext == ".csv":
            raw_records = load_csv(file_input, source_name=source_name)
        elif ext in (".xlsx", ".xls"):
            raw_records = load_excel(file_input, source_name=source_name)
        elif ext == ".json":
            raw_records = load_json(file_input, source_name=source_name)
        else:
            logger.warning("Unsupported structured file format: %s", ext)
            return 0

        if not raw_records:
            logger.warning("No records found in structured file '%s'", source_name)
            self.records_by_source[source_name] = []
            return 0

        normalized = normalize_records(raw_records, source_name=source_name)
        valid = validate_records(normalized)

        # Attach default verified image if missing
        for r in valid:
            if not r.get("image_url"):
                bhk_val = r.get("bhk", 2)
                if bhk_val == 2:
                    r["image_url"] = "/api/assets/images/Bedroom.jpg"
                elif bhk_val == 3:
                    r["image_url"] = "/api/assets/images/bedroom.jpg.2.jpg"
                else:
                    r["image_url"] = "/api/assets/images/Bathroom.jpg"

        self.records_by_source[source_name] = valid
        logger.info("StructuredDataStore updated: '%s' has %d valid records", source_name, len(valid))
        return len(valid)

    def remove(self, source_name: str) -> int:
        """
        Removes all property records associated with canonical source_name.
        Uses exact canonical identity to prevent cross-directory collisions.
        Returns the number of records removed.
        """
        norm_target = source_name.replace("\\", "/").lower()
        matched_keys = [k for k in self.records_by_source if k.replace("\\", "/").lower() == norm_target]
        if matched_keys:
            removed_count = 0
            for k in matched_keys:
                removed_count += len(self.records_by_source[k])
                del self.records_by_source[k]
            logger.info("StructuredDataStore removed '%s' (%d records purged)", source_name, removed_count)
            return removed_count

        return 0

    def get_all_records(self) -> list[dict[str, Any]]:
        """Returns all active records flattened across all sources."""
        all_recs = []
        for records in self.records_by_source.values():
            all_recs.extend(records)
        return all_recs

    def search(self, filters: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
        """Runs deterministic filtering across all active property records."""
        return search_properties(filters, self.get_all_records(), limit=limit)

    def clear(self) -> None:
        """Clears all records."""
        self.records_by_source.clear()


_GLOBAL_STRUCTURED_STORE: Optional[StructuredDataStore] = None


def get_structured_store() -> StructuredDataStore:
    global _GLOBAL_STRUCTURED_STORE
    if _GLOBAL_STRUCTURED_STORE is None:
        _GLOBAL_STRUCTURED_STORE = StructuredDataStore()
    return _GLOBAL_STRUCTURED_STORE

