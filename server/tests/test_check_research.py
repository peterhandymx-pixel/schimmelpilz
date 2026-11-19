import json
from pathlib import Path

from server import check_research


def test_norm_matching_is_exact():
    sources = [{'title': '§ 30 SGB I · Geltungsbereich'}]
    assert check_research.norm_found('§ 30 SGB I', sources, '')
    assert not check_research.norm_found('§ 30 SGB II', sources, '')
    assert check_research.norm_found('§ 4 KSchG', [], 'binnen drei Wochen (§ 4 KSchG)')
    assert not check_research.norm_found('§ 4 KSchG', [], 'nach § 45 KSchG')


def test_check_file_is_complete():
    for item in json.loads(Path(check_research.CHECKS).read_text(encoding='utf-8')):
        assert {'id', 'area', 'question', 'norms_any', 'answer_all', 'answer_none'} <= set(item)
