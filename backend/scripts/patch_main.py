import re

with open('backend/app/main.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Pattern for fast-path 3
pat1 = r"""            # Build detail items from RAG answer and return property cards
            details = _rag_to_details\(rag_res\.get\("answer", ""\)\)
            props = _fetch_properties_for_bhk\(bhk_num, limit=2\)
            if props:
                for p in props:
                    p\["details"\] = details
                bhk_label = f"\{bhk_num\} BHK" if bhk_num else "matching"
                intro = f"Here are the \{bhk_label\} details from the property documents\."
                return \{
                    "status": "success",
                    "assistant_message": intro,
                    "filters": \{"intent": "document_qa", "bhk": bhk_num\},
                    "properties": props,
                    "result_count": len\(props\),
                    "images": \[\],
                    "image_filter": None,
                \}
            # No properties found[^\n]*"""

rep1 = """            details = _rag_to_details(rag_res.get("answer", ""))
            if bhk_num:
                props = _fetch_properties_for_bhk(bhk_num, limit=2)
                for p in props:
                    p["details"] = details
                bhk_label = f"{bhk_num} BHK"
                intro = f"Here are the {bhk_label} details from the property documents."
                return {
                    "status": "success",
                    "assistant_message": intro,
                    "filters": {"intent": "document_qa", "bhk": bhk_num},
                    "properties": props,
                    "result_count": len(props),
                    "images": [],
                    "image_filter": None,
                }
            else:
                return {
                    "status": "message",
                    "assistant_message": rag_res.get("answer", "Here are the relevant details from the property documents."),
                    "filters": {"intent": "document_qa", "bhk": None},
                    "properties": [],
                }"""

new_text, count1 = re.subn(pat1, rep1, text)
print(f"Substitutions made: {count1}")

if count1 > 0:
    with open('backend/app/main.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("main.py updated successfully.")
else:
    print("Warning: regex pattern did not match.")

