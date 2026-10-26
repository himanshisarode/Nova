"""Turn pytest's JUnit XML into GitHub annotations, so failing tests are
visible on the run page (and via the public API) without opening logs."""
import sys
import xml.etree.ElementTree as ET


def escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


root = ET.parse(sys.argv[1]).getroot()
for case in root.iter("testcase"):
    for problem in list(case.findall("failure")) + list(case.findall("error")):
        name = f"{case.get('classname')}::{case.get('name')}"
        detail = (problem.get("message") or "") + "\n" + (problem.text or "")[-1500:]
        print(f"::error title={escape(name)}::{escape(detail.strip())}")
