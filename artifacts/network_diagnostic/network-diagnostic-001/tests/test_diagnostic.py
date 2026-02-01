"""Test that network diagnostic was completed successfully."""
import os


def test_diagnostic_script_exists():
    """Verify the diagnostic script was created."""
    assert os.path.exists('/testbed/run_diagnostic.sh'), \
        'Diagnostic script /testbed/run_diagnostic.sh not created'
    assert os.access('/testbed/run_diagnostic.sh', os.X_OK), \
        'Diagnostic script is not executable'


def test_results_file_exists():
    """Verify the results file was created."""
    assert os.path.exists('/testbed/network_diagnostic_results.txt'), \
        'Results file /testbed/network_diagnostic_results.txt not created'


def test_results_content():
    """Verify results contain expected test outputs."""
    with open('/testbed/network_diagnostic_results.txt') as f:
        content = f.read()

    assert len(content) > 100, 'Results file is too short (less than 100 chars)'

    content_lower = content.lower()
    assert 'sourcegraph' in content_lower, 'No sourcegraph tests found in results'

    # Check for key test indicators
    indicators = ['dns', 'curl', 'http', 'resolv.conf']
    found = [ind for ind in indicators if ind in content_lower]
    assert len(found) >= 2, f'Results missing key test indicators. Found: {found}'

    print(f'✓ Network diagnostic completed successfully')
    print(f'  Results file size: {len(content)} bytes')
    print(f'  Test indicators found: {found}')
