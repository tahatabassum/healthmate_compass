from app.services.flags import resolve_canonical_name, compute_flag, process_extracted_values
from app.llm.schemas import ExtractedValue

tests = [
    ("SODIUM", 134.0, "MMOL/L", 136.0, 146.0),
    ("POTASSIUM", 4.9, "MMOL/L", 3.8, 4.8),
    ("CHLORIDE", 102.0, "MMOL/L", 98.0, 108.0),
    ("TOTAL CO2", 25.4, "MMOL/L", 24.0, 32.0),
    ("GLUCOSE", 151.0, "MG/DL", 70.0, 110.0),
    ("BUN", 30.0, "MG/DL", 7.0, 22.0),
    ("CALC OSMO", 277.0, "MOSM/KG", 275.0, 295.0),
    ("CREATININE", 1.4, "MG/DL", 0.4, 1.5),
    ("B/C RATIO", 21.0, "", 6.0, 20.0),
    ("CALCIUM", 8.9, "MG/DL", 8.7, 10.2),
    ("TOTAL BILI", 0.35, "MG/DL", 0.0, 1.0),
    ("TOTAL PROT", 7.5, "G/DL", 6.5, 8.2),
    ("ALBUMIN", 3.0, "G/DL", 3.4, 4.3),
    ("ALK PHOS", 118.0, "U/L", 50.0, 136.0),
    ("GOT (AST)", 29.0, "U/L", 15.0, 37.0),
    ("GPT (ALT)", 33.0, "U/L", 30.0, 65.0),
    ("MAGNESIUM", 2.1, "MG/DL", 1.7, 2.6),
    ("CHOLESTERO", 138.0, "MG/DL", None, 200.0),
    ("TRIGLYCERI", 58.0, "MG/DL", 30.0, 200.0),
    ("HDL CHOL", 43.0, "MG/DL", 32.0, 72.0),
    ("VLDL CHOL", 12.0, "MG/DL", None, 40.0),
    ("LDL CHOL", 83.0, "MG/DL", None, 130.0),
]

print(f"{'Test':<15} | {'Resolved Canon':<20} | {'Flag':<8} | {'Range':<15}")
print("-" * 65)

items = [
    ExtractedValue(
        test_name=t[0],
        value=t[1],
        unit=t[2],
        ref_low=t[3],
        ref_high=t[4]
    )
    for t in tests
]

processed, specialty = process_extracted_values(items, gender="male")
for p in processed:
    print(f"{p.test_name:<15} | {str(p.canonical_name):<20} | {str(p.flag):<8} | [{p.ref_low}, {p.ref_high}]")

print("\nSpecialty recommended:", specialty)
