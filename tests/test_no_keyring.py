from pathlib import Path


def test_application_code_never_imports_keyring():
    root = Path(__file__).parents[1] / 'research_copilot'
    offenders = []
    for path in root.rglob('*.py'):
        text = path.read_text()
        if 'keyring' in text or 'KeychainStore' in text:
            offenders.append(str(path.relative_to(root.parent)))
    assert offenders == []
