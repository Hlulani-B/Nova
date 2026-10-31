import io

import pandas as pd
import pytest
from fastapi import HTTPException

from code_runner import run_python_code
from overview import generate_csv_overview
from scan import CSVAnalysisRequest, analyze_csv_data, hard_checks_pass
from scrubber import clean_csv

MESSY_CSV = (
    "id,name,age,city,salary\n"
    "1,  Alice ,25,New York,50000\n"
    "2,Bob,N/A,new york ,62000\n"
    "2,Bob,N/A,new york ,62000\n"
    "3,Carol, 31 ,LONDON,\n"
    "4,,28,London,48000\n"
    "5,Dave,45,Paris,71000\n"
)


# --- Runner only (no AI, free and fast) -------------------------------------
def test_runner_returns_cleaned_csv():
    code = (
        "import pandas as pd\n"
        'df = pd.read_csv("data.csv").drop_duplicates()\n'
        'df.to_csv("cleaned.csv", index=False)\n'
    )
    result = run_python_code(code, "a,b\n1,2\n1,2\n3,4\n")
    assert len(pd.read_csv(io.StringIO(result["cleaned_csv"]))) == 2


def test_runner_reports_crashes():
    with pytest.raises(HTTPException):
        run_python_code('raise ValueError("boom")', "a,b\n1,2\n")


def test_runner_requires_output_file():
    with pytest.raises(HTTPException):
        run_python_code("print('hi')", "a,b\n1,2\n")


# --- Full pipeline (real AI, needs your .env keys) --------------------------
def test_clean_csv_end_to_end():
    scan = analyze_csv_data(CSVAnalysisRequest(csv_data=MESSY_CSV))
    assert scan["ok"] is False

    overview = generate_csv_overview(MESSY_CSV)
    cleaned = clean_csv(scan, overview, MESSY_CSV)

    assert isinstance(cleaned, str)
    df = pd.read_csv(io.StringIO(cleaned))
    original = pd.read_csv(io.StringIO(MESSY_CSV))

    assert 0 < len(df) <= len(original)
    assert list(df.columns) == list(original.columns)
    assert not df.duplicated().any(), "duplicates remain"
    assert not df.isnull().any().any(), "missing values remain"
    assert pd.api.types.is_numeric_dtype(df["age"]), "age is still not numeric"
    for col in df.select_dtypes(include="object").columns:
        s = df[col].astype(str)
        assert (s.str.strip() == s).all(), f"whitespace padding left in '{col}'"
        assert not (s.str.strip() == "").any(), f"blank strings left in '{col}'"

    assert hard_checks_pass(df, skipped_lines=0)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-s"]))